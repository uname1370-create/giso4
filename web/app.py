# -*- coding: utf-8 -*-
"""
app.py — فایل اصلی Flask وب‌سایت آموزشی sadeghiai

معماری:
  - وب‌سایت و ربات bot_edu یک سیستم آموزشی یکپارچه هستند.
  - دیتابیس مشترک bot_edu/data/bot.db.
  - جدول‌های web_identity_* مخصوص احراز هویت وب.
  - منطق کسب‌وکار از طریق mentor_service و panel_service (مشترک با ربات) مصرف می‌شود.
  - گیسو کاملاً جدا است و هیچ منطق نقشی از آن در وب‌سایت آموزشی استفاده نمی‌شود.
  - سه ناحیهٔ مجزا:
      • پنل ادمین (/admin/*)        — فقط برای ادمین سایت (SITE_ADMIN_PHONES)
      • پنل کاربری (/dashboard/...)  — همه کاربران واردشده (غیرادمین)
      • یار همراه من (/mentor/*)    — حوزه منتور/مسیر شغلی هوشمند
"""
import os
import sys
import json
import html
import hmac
import hashlib
import sqlite3
import logging
import re
import secrets
import time as _time
from pathlib import Path
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort)
from flask_login import login_required, current_user

# اول web محلی، بعد bot_edu (جلوگیری از تداخل config)
_WEB_DIR = Path(__file__).resolve().parent
_BOT_EDU = _WEB_DIR.parent / 'bot_edu'
_ROOT = _WEB_DIR.parent
if str(_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_WEB_DIR))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BOT_EDU) not in sys.path:
    sys.path.append(str(_BOT_EDU))

# لود زودهنگام env از ریشه (اگر هنوز لود نشده)
try:
    from env_loader import load_project_env
    load_project_env()
except ImportError:
    pass

# حالا می‌توانیم از bot_edu import کنیم
import panel_service  # noqa: F401,E402  # façade services/panel_service
from config import Config, SECURITY_QUESTIONS  # noqa: E402
from phoneutil import normalize_phone as _norm_phone  # noqa: E402
from models import (db, User, WebIdentityAuth, WebIdentityCareerState,
                    ConsultantRequest, ConsultantMessage)  # noqa: E402
from auth import auth_bp, login_manager  # noqa: E402
import mentor_service as MS  # noqa: E402 — façade روی services/*
from web_ai import (  # noqa: E402 — پکیج اختصاصی هوش مصنوعی سایت
    check_ai_status, interviewer_chat, analyze_guest_paths, ask as web_ai_ask,
)
from panel_service import (  # noqa: E402 — façade
    public_items, user_panel_items, mentor_items, site_admin_items,
)
PS = sys.modules.get('panel_service')  # shorthand

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('web-main')


# ---------------------------------------------------------------------------
# helpers

def _ensure_dirs(app):
    os.makedirs(os.path.join(Config.BASE_DIR, 'web', 'data'), exist_ok=True)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


def _init_web_tables(app):
    """اطمینان از وجود جدول‌های هسته (بات) + جدول‌های web_identity_*."""
    try:
        import db as _bot_db
        _saved_cwd = os.getcwd()
        os.chdir(str(_BOT_EDU))
        try:
            _bot_db.init_db()
        finally:
            os.chdir(_saved_cwd)
        logger.info("✅ جدول‌های هستهٔ مشترک bot.db آماده شدند.")
    except Exception as e:
        logger.warning(f"init core db: {e}")
    with app.app_context():
        try:
            db.create_all()
            _ensure_consultant_schema_columns()
            logger.info("✅ جدول‌های وب آماده هستند (web_identity_* در bot.db).")
        except Exception as e:
            logger.warning(f"init web tables: {e}")


def _is_site_admin() -> bool:
    try:
        return bool(current_user.is_authenticated and current_user.is_main_admin)
    except Exception:
        return False


def _gate_onboarding():
    """اگر کاربر عادی است و هنوز آنبوردینگ منتور را کامل نکرده، به /mentor/onboarding بفرست.
    برای ادمین‌ها اعمال نمی‌شود."""
    if not current_user.is_authenticated:
        return None
    if _is_site_admin():
        return None  # ادمین هیچ‌گاه در جریان onboarding منتور نمی‌افتد
    st = MS.get_mentor_state(current_user.id)
    if not st.get('onboarding_completed'):
        flash('برای دسترسی به پنل کاربری، ابتدا «یار همراه من» را تکمیل کنید.', 'warning')
        return redirect(url_for('mentor_onboarding'))
    return None


def _admin_required():
    """اگر کاربر ادمین سایت نیست، 403 / redirect به خانه."""
    if not current_user.is_authenticated:
        flash('برای دسترسی به این بخش ابتدا وارد شوید.', 'warning')
        return redirect(url_for('auth.login'))
    if not _is_site_admin():
        flash('دستررسی به پنل مدیریت فقط برای ادمین سایت مجاز است.', 'danger')
        return redirect(url_for('index'))
    return None


def _in_admin() -> bool:
    return (request.path or '').startswith('/admin')


def _consultant_admin_ids() -> list[int]:
    raw = (os.getenv('ADMIN_IDS') or '1191639507').replace('،', ',')
    out = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            logger.warning('ADMIN_IDS invalid item ignored: %r', part)
    return out


def _consultant_bot_keyboard(req_id: int):
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('✅ تأیید و شروع چت', callback_data=f'cons_approve|{req_id}'),
                InlineKeyboardButton('❌ رد درخواست', callback_data=f'cons_reject|{req_id}'),
            ],
            [InlineKeyboardButton('👁 مشاهده در پنل مشاور ربات', callback_data=f'cons_view|{req_id}')],
        ])
    except Exception as e:
        logger.warning('consultant keyboard build failed: %s', e)
        return None


def _consultant_bot_control_keyboard(req_id: int):
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('⏸ توقف موقت', callback_data=f'cons_pause|{req_id}'),
                InlineKeyboardButton('▶️ ادامه گفتگو', callback_data=f'cons_resume|{req_id}'),
            ],
            [InlineKeyboardButton('🛑 پایان چت', callback_data=f'cons_close|{req_id}')],
            [InlineKeyboardButton('👁 مشاهده در پنل مشاور ربات', callback_data=f'cons_view|{req_id}')],
        ])
    except Exception as e:
        logger.warning('consultant control keyboard build failed: %s', e)
        return None


def _h(value, limit=800) -> str:
    text = str(value or '—')[:limit]
    return html.escape(text)


def _build_consultant_notification(item: ConsultantRequest, analysis: dict, first_route: dict) -> str:
    profile = analysis.get('profile') or analysis.get('user_profile') or {}
    diagnosis = analysis.get('diagnosis') or {}
    strengths = analysis.get('strengths') or []
    challenges = analysis.get('challenges') or []
    tools = first_route.get('ai_tools') or []

    def _list(items, limit=4):
        vals = [f"- {_h(x, 180)}" for x in (items or [])[:limit]]
        return "\n".join(vals) if vals else "- —"

    tool_lines = []
    for t in tools[:4]:
        if isinstance(t, dict):
            tool_lines.append(f"- {_h(t.get('name'), 100)}: {_h(t.get('how_helps') or t.get('why'), 180)}")
        else:
            tool_lines.append(f"- {_h(t, 160)}")
    return (
        "📩 <b>درخواست جدید مشاور</b>\n\n"
        "👤 <b>مشخصات کاربر</b>\n"
        f"- نام: {_h(profile.get('name') or item.name, 120)}\n"
        f"- سن: {_h(profile.get('age'), 40)}\n"
        f"- شهر: {_h(profile.get('city') or item.city, 120)}\n"
        f"- شماره: {_h(item.phone, 40)}\n\n"
        "🎯 <b>تحلیل هوشمند</b>\n"
        f"- مشکل اصلی: {_h(diagnosis.get('main_problem') or item.main_problem, 700)}\n"
        f"- چرا این مشکل: {_h(diagnosis.get('why_this_problem'), 700)}\n"
        f"- آمادگی: {_h(diagnosis.get('readiness_level'), 80)}\n\n"
        "⚠️ <b>چالش‌ها</b>\n"
        f"{_list(challenges)}\n\n"
        "✅ <b>نقاط قوت</b>\n"
        f"{_list(strengths)}\n\n"
        "🎯 <b>علاقه‌مندی</b>\n"
        f"- {_h(profile.get('interest_direction'), 220)}\n\n"
        "⏱ <b>زمان روزانه</b>\n"
        f"- {_h(profile.get('time_available'), 120)}\n\n"
        "🧭 <b>مسیر پیشنهادی</b>\n"
        f"- {_h(item.selected_route_title, 240)}\n"
        f"- اولین خروجی: {_h(first_route.get('first_result_type'), 220)}\n"
        f"- بازه اولین نتیجه: {_h(first_route.get('first_result_window_days'), 60)} روزه\n\n"
        "🤖 <b>ابزارهای AI پیشنهادی</b>\n"
        f"{chr(10).join(tool_lines) if tool_lines else '- —'}\n\n"
        "💬 <b>پیام اولیه کاربر</b>\n"
        f"- {_h(item.intro_message, 700)}"
    )


def _notify_consultant_admins(text: str, req_id: int, controls: bool = False, admin_chat_id: str = '') -> None:
    token = (os.getenv('BOT_TOKEN') or '').strip()
    if not token:
        logger.warning('consultant notify skipped: BOT_TOKEN missing')
        return
    try:
        import asyncio
        from telegram import Bot
        bot = Bot(token=token, base_url="https://tapi.bale.ai/bot", base_file_url="https://tapi.bale.ai/file/bot")
        keyboard = (_consultant_bot_control_keyboard(req_id) if controls
                    else _consultant_bot_keyboard(req_id))
        targets = [int(admin_chat_id)] if str(admin_chat_id or '').isdigit() else _consultant_admin_ids()

        async def _send_all():
            for admin_id in targets:
                try:
                    await bot.send_message(admin_id, text, reply_markup=keyboard, parse_mode="HTML")
                except Exception as e:
                    logger.warning('consultant notify failed for %s: %s', admin_id, e)
        asyncio.run(_send_all())
    except Exception as e:
        logger.warning('consultant notify failed: %s', e)


def _ensure_consultant_schema_columns() -> None:
    try:
        with db.engine.connect() as conn:
            rows = conn.exec_driver_sql('PRAGMA table_info(consultant_requests)').fetchall()
            existing = {r[1] for r in rows}
            additions = {
                'last_turn': "ALTER TABLE consultant_requests ADD COLUMN last_turn TEXT DEFAULT ''",
                'free_user_messages_used': 'ALTER TABLE consultant_requests ADD COLUMN free_user_messages_used INTEGER DEFAULT 0',
                'paused_at': "ALTER TABLE consultant_requests ADD COLUMN paused_at TEXT DEFAULT ''",
                'resumed_at': "ALTER TABLE consultant_requests ADD COLUMN resumed_at TEXT DEFAULT ''",
                'admin_chat_id': "ALTER TABLE consultant_requests ADD COLUMN admin_chat_id TEXT DEFAULT ''",
            }
            for col, sql in additions.items():
                if col not in existing:
                    conn.exec_driver_sql(sql)
            conn.commit()
    except Exception as e:
        logger.warning('ensure consultant schema columns: %s', e)


def _extract_first_int(value, default=0) -> int:
    try:
        trans = str(value or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        import re as _re
        m = _re.search(r'\d+', trans)
        return int(m.group(0)) if m else int(default)
    except Exception:
        return int(default)


def _sync_guest_analysis_to_bot(user_id: int, phone: str, guest_analysis: dict) -> bool:
    """Create bot ai_mentor path from website analysis, safely and idempotently."""
    if not guest_analysis:
        return False
    try:
        profile = guest_analysis.get('profile') or guest_analysis.get('user_profile') or {}
        routes = guest_analysis.get('routes') or guest_analysis.get('paths') or []
        first_route = routes[0] if routes else {}
        if not first_route:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        first_name = (profile.get('name') or '').strip()[:100]
        city = (profile.get('city') or '').strip()[:100]
        age = _extract_first_int(profile.get('age'), 0)
        target_job = (first_route.get('title') or 'مسیر اختصاصی سایت')[:300]
        roadmap = {
            'source': 'web_guest_try',
            'route': first_route,
            'sprint_plan': first_route.get('sprint_plan') or [],
            'ai_tools': first_route.get('ai_tools') or [],
            'first_result_window_days': first_route.get('first_result_window_days') or '',
            'first_result_type': first_route.get('first_result_type') or '',
        }
        with db.engine.begin() as conn:
            # If there is already an active bot path, never overwrite it.
            active = conn.exec_driver_sql(
                "SELECT id FROM career_paths WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (int(user_id),)
            ).fetchone()
            if active:
                return False
            conn.exec_driver_sql(
                "INSERT OR REPLACE INTO user_profiles (user_id, first_name, last_name, age, city, updated_at) VALUES (?, ?, COALESCE((SELECT last_name FROM user_profiles WHERE user_id=?), ''), ?, ?, ?)",
                (int(user_id), first_name, int(user_id), age, city, now)
            )
            cur = conn.exec_driver_sql(
                "INSERT INTO career_paths (user_id, target_job, interview_data, status, created_at, completed_at, interview_data_json, roadmap_json) VALUES (?, ?, ?, 'active', ?, '', ?, ?)",
                (
                    int(user_id), target_job,
                    json.dumps(guest_analysis, ensure_ascii=False), now,
                    json.dumps(guest_analysis, ensure_ascii=False),
                    json.dumps(roadmap, ensure_ascii=False),
                )
            )
            path_id = int(cur.lastrowid or 0)
            sprint_steps = first_route.get('sprint_plan') or []
            for idx, step in enumerate(sprint_steps, start=1):
                if not isinstance(step, dict):
                    continue
                title = (step.get('day_range') or f'گام {idx}')[:200]
                task = (step.get('task') or '')[:2000]
                content = {'description': task, 'task': task, 'source': 'web_guest_try'}
                status = 'active' if idx == 1 else 'locked'
                payload = json.dumps(content, ensure_ascii=False)
                conn.exec_driver_sql(
                    "INSERT INTO path_steps (path_id, step_number, step_type, title, content, status, ai_feedback, completed_at, content_json) VALUES (?, ?, 'resource', ?, ?, ?, '{}', '', ?)",
                    (path_id, idx, title, payload, status, payload)
                )
        logger.info('guest analysis synced to bot ai_mentor path for user_id=%s', user_id)
        return True
    except Exception as e:
        logger.warning('sync guest analysis to bot failed: %s', e, exc_info=True)
        return False


def _in_user_panel() -> bool:
    p = request.path or ''
    return any(p.startswith(x) for x in
               ('/dashboard', '/courses', '/missions', '/shop', '/profile',
                '/support', '/tools')) and not _in_admin()


def _in_mentor() -> bool:
    return (request.path or '').startswith('/mentor')


# ---------------------------------------------------------------------------
# app factory

def _format_delete_counts(counts: dict, limit: int = 40) -> str:
    """نمایش خلاصه ردیف‌های تحت تاثیر حذف کاربر برای flash."""
    items = [(k, int(v or 0)) for k, v in (counts or {}).items() if int(v or 0) > 0]
    if not items:
        return 'بدون ردیف وابسته'
    parts = [f"{k}: {v}" for k, v in items[:limit]]
    if len(items) > limit:
        parts.append(f"... +{len(items) - limit} جدول دیگر")
    return '، '.join(parts)


def _current_admin_delete_identity() -> dict:
    try:
        return {'user_id': int(current_user.id), 'phone': current_user.phone or ''}
    except Exception:
        return {'user_id': 0, 'phone': ''}


def _maintenance_setting(key: str, default: str = '') -> str:
    try:
        db_path = Path(Config.BOT_EDU_DIR) / 'data' / 'bot.db'
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return str((row[0] if row else default) or default)
        finally:
            conn.close()
    except Exception:
        return default


def _maintenance_flag(key: str) -> bool:
    """خواندن live فلگ maintenance از settings در bot.db. خطا = off."""
    return _maintenance_setting(key, '').strip().lower() == 'on'


def _maintenance_bypass_token(secret: str) -> str:
    try:
        return hmac.new(str(Config.SECRET_KEY).encode(), str(secret).encode(), hashlib.sha256).hexdigest()
    except Exception:
        return ''


def _clean_admin_key_url():
    try:
        from urllib.parse import urlencode
        args = request.args.to_dict(flat=True)
        args.pop('admin_key', None)
        qs = urlencode(args)
        return request.path + ((f'?{qs}') if qs else '')
    except Exception:
        return '/'




# ─── CSRF (هم‌الگوی giso/security.py) — توکن سشن + گیت POST + تزریق به HTML ───
_WEB_CSRF_KEY = "web_csrf_token"
_WEB_CSRF_FORM_RE = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
_WEB_CSRF_SCRIPT = (
    "<script>(function(){"
    "var m=document.querySelector('meta[name=\"web-csrf-token\"]');"
    "if(!m)return;var t=m.content||'';if(!t)return;"
    "function sameOrigin(u){try{if(typeof u==='string'&&/^https?:/i.test(u)){"
    "var a=document.createElement('a');a.href=u;return a.origin===location.origin}"
    "return true}catch(e){return false}}"
    "var of=window.fetch;if(of){window.fetch=function(u,o){o=o||{};"
    "var mt=String(o.method||'GET').toUpperCase();"
    "if(mt!=='GET'&&mt!=='HEAD'&&sameOrigin(u)){o.headers=o.headers||{};"
    "if(!o.headers['X-CSRF-Token']&&!o.headers['X-GISO-CSRF'])o.headers['X-CSRF-Token']=t;}"
    "return of.call(this,u,o)};}"
    "var oo=XMLHttpRequest.prototype.open;"
    "XMLHttpRequest.prototype.open=function(mt,u){"
    "var m=String(mt||'GET').toUpperCase();"
    "if(m!=='GET'&&m!=='HEAD'&&sameOrigin(u)){"
    "try{this.setRequestHeader('X-CSRF-Token',t)}catch(e){}}"
    "return oo.apply(this,arguments)};})();</script>"
)


def _web_csrf_token() -> str:
    """توکن پایدار سشن (مانند giso.security.csrf_token)."""
    token = session.get(_WEB_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_WEB_CSRF_KEY] = token
        session.modified = True
    return token


def _botdb_conn():
    conn = sqlite3.connect(str(Path(Config.BOT_EDU_DIR) / 'data' / 'bot.db'))
    conn.row_factory = sqlite3.Row
    return conn


def _safe_json_loads(value, default=None):
    if default is None:
        default = {}
    if isinstance(value, dict):
        return value
    try:
        out = json.loads(value or '{}')
        return out if isinstance(out, dict) else default
    except Exception:
        return default


def _mentor_growth_context(user_id: int) -> dict:
    summary = {}
    rank = 0
    streak = {"current_streak": 0, "longest_streak": 0}
    try:
        summary = MS.user_progress_summary(user_id)
    except Exception:
        summary = {}
    try:
        rank = MS.get_user_rank(user_id)
    except Exception:
        rank = 0
    try:
        streak = MS.get_streak_info(user_id) if hasattr(MS, 'get_streak_info') else streak
    except Exception:
        pass
    return {
        "name": getattr(current_user, 'first_name', '') or summary.get('first_name') or 'کاربر عزیز',
        "xp": int(summary.get('xp') or getattr(current_user, 'xp', 0) or 0),
        "credits": int(summary.get('credits') or getattr(current_user, 'credits', 0) or 0),
        "rank": rank,
        "streak": streak,
    }


def _path_steps_for(path_id: int) -> list:
    if not path_id:
        return []
    try:
        with _botdb_conn() as conn:
            rows = conn.execute('SELECT * FROM path_steps WHERE path_id=? ORDER BY step_number ASC', (int(path_id),)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d['content'] = _safe_json_loads(d.get('content'), {})
                d['content_json'] = _safe_json_loads(d.get('content_json'), {})
                out.append(d)
            return out
    except Exception:
        return []


def _path_progress_info(path: dict) -> dict:
    steps = _path_steps_for(int(path.get('id') or 0)) if path else []
    total = len(steps)
    done = len([s for s in steps if s.get('status') == 'completed'])
    percent = int(done * 100 / total) if total else 0
    return {"steps": steps, "total": total, "done": done, "percent": percent, "finished": bool(total and done >= total)}


def _path_data(path: dict) -> dict:
    if not path:
        return {}
    data = path.get('interview_data_json') or path.get('interview_data') or {}
    return data if isinstance(data, dict) else _safe_json_loads(data, {})


def _milestones(path: dict) -> list:
    ms = (_path_data(path).get('milestones') or []) if path else []
    return ms if isinstance(ms, list) else []


def _append_milestone(path_id: int, milestone: dict) -> None:
    if not path_id or not milestone or not milestone.get('badge'):
        return
    try:
        with _botdb_conn() as conn:
            row = conn.execute('SELECT interview_data_json FROM career_paths WHERE id=?', (int(path_id),)).fetchone()
            data = _safe_json_loads(row['interview_data_json'] if row else '{}', {})
            items = data.get('milestones') or []
            if not isinstance(items, list):
                items = []
            key = f"{milestone.get('type')}:{milestone.get('completed_count')}"
            if not any(isinstance(x, dict) and f"{x.get('type')}:{x.get('completed_count')}" == key for x in items):
                items.append(milestone)
            data['milestones'] = items
            conn.execute('UPDATE career_paths SET interview_data_json=? WHERE id=?', (json.dumps(data, ensure_ascii=False), int(path_id)))
            conn.commit()
    except Exception as e:
        logger.warning('append milestone skipped: %s', e)


def _ensure_steps_for_user(user_id: int) -> list:
    try:
        path = MS.get_active_path(user_id) if hasattr(MS, 'get_active_path') else None
        if not path:
            return []
        steps = _path_steps_for(int(path.get('id') or 0))
        if steps:
            return steps
        try:
            from services.daily_content_ai import ensure_personalized_steps
            return ensure_personalized_steps(user_id) or []
        except Exception as e:
            logger.warning('ensure personalized steps skipped: %s', e)
            return _path_steps_for(int(path.get('id') or 0))
    except Exception:
        return []

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    _ensure_dirs(app)

    db.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(auth_bp, url_prefix='')

    @app.context_processor
    def inject_nav():
        is_admin = _is_site_admin()
        return {
            'in_user_panel': _in_user_panel(),
            'in_mentor': _in_mentor(),
            'in_admin': _in_admin(),
            'is_site_admin': is_admin,
            # منوها از panel_service (منبع واحد با ربات)
            'public_menu': PS.public_items(),
            'user_menu': PS.user_panel_items(),
            'mentor_menu': PS.mentor_items(),
            'admin_menu': PS.site_admin_items(),
        }

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    @app.route('/maintenance-access/<token>')
    def main_maintenance_token_entry(token):
        from maintenance_access import consume
        if not _maintenance_flag('site_maintenance') or not consume('main',token):
            return ('لینک منقضی یا استفاده شده است.',410)
        session['main_maintenance_entry_until']=int(time.time())+600
        return redirect(url_for('auth.login'))

    # مسیر خصوصی Maintenance سایت آموزشی؛ فقط یک bypass کوتاه‌مدت می‌سازد.
    _main_private_admin_path = (os.getenv("MAIN_MAINTENANCE_ADMIN_PATH") or "").strip().strip("/")
    if _main_private_admin_path and "/" not in _main_private_admin_path:
        def _main_maintenance_admin_entry():
            token = _maintenance_bypass_token(_main_private_admin_path)
            resp = redirect('/')
            resp.set_cookie('site_admin_bypass', token, max_age=900, httponly=True,
                            samesite='Lax', secure=request.is_secure)
            return resp
        app.add_url_rule(f"/{_main_private_admin_path}", endpoint="main_maintenance_admin_entry",
                         view_func=_main_maintenance_admin_entry, methods=["GET"])

    @app.before_request
    def site_maintenance_gate():
        try:
            if (request.endpoint or '').startswith('static') or (request.path or '').startswith('/static/'):
                return None
            admin_key = (request.args.get('admin_key') or '').strip()
            if admin_key == 'logout':
                resp = redirect('/')
                resp.delete_cookie('site_admin_bypass')
                return resp
            secret = _maintenance_setting('site_secret_key', '').strip()
            expected_token = _maintenance_bypass_token(secret) if secret else ''
            private_token = _maintenance_bypass_token(_main_private_admin_path) if _main_private_admin_path else ''
            if admin_key and secret and hmac.compare_digest(admin_key, secret):
                resp = redirect(_clean_admin_key_url())
                resp.set_cookie('site_admin_bypass', expected_token, max_age=30 * 24 * 3600,
                                httponly=True, samesite='Lax', secure=request.is_secure)
                return resp
            if not _maintenance_flag('site_maintenance'):
                return None
            if request.path.startswith('/maintenance-access/'):
                return None
            pending=int(session.get('main_maintenance_entry_until') or 0)>=int(time.time())
            if pending and ((request.endpoint or '').startswith('auth.') or _is_site_admin()):
                return None
            cookie_token = request.cookies.get('site_admin_bypass', '')
            if ((expected_token and hmac.compare_digest(cookie_token, expected_token)) or
                    (private_token and hmac.compare_digest(cookie_token, private_token))):
                return None
            return render_template('maintenance.html', maintenance_image_version=_maintenance_setting('site_maintenance_image_version','0')), 503
        except Exception:
            return None

    # ======================================================================
    # صفحه اصلی
    # ======================================================================
    @app.route('/')
    def index():
        return render_template('index.html')

    # ======================================================================
    # پنل مدیریت سایت (/admin/*)
    # ======================================================================
    @app.route('/admin')
    @login_required
    def admin_dashboard():
        if _r := _admin_required():
            return _r
        # آمار پایه
        summary = MS.admin_stats() if hasattr(MS, 'admin_stats') else {}
        try:
            all_users = MS.list_all_users()
        except Exception:
            all_users = []
        try:
            courses = MS.list_courses()
        except Exception:
            courses = []
        try:
            missions = MS.list_missions()
        except Exception:
            missions = []
        try:
            shop_items = MS.list_shop_items()
        except Exception:
            shop_items = []
        try:
            cash_pending = MS.list_pending_cash_requests()
        except Exception:
            cash_pending = []
        try:
            open_tickets = MS.count_open_tickets()
        except Exception:
            open_tickets = 0

        return render_template(
            'admin/dashboard.html',
            user=current_user,
            stats={
                'users_count': len(all_users),
                'courses_count': len(courses),
                'missions_count': len(missions),
                'shop_count': len(shop_items),
                'cash_pending': len(cash_pending or []),
                'open_tickets': open_tickets,
            },
        )

    @app.route('/admin/courses')
    @login_required
    def admin_courses():
        if _r := _admin_required():
            return _r
        return render_template('admin/courses.html', courses=MS.list_courses(),
                               user=current_user)

    @app.route('/admin/missions')
    @login_required
    def admin_missions():
        if _r := _admin_required():
            return _r
        return render_template('admin/missions.html', missions=MS.list_missions(),
                               user=current_user)

    @app.route('/admin/shop')
    @login_required
    def admin_shop():
        if _r := _admin_required():
            return _r
        return render_template('admin/shop.html', items=MS.list_shop_items(),
                               user=current_user)

    @app.route('/admin/users')
    @login_required
    def admin_users():
        if _r := _admin_required():
            return _r
        q_user_id = (request.args.get('user_id') or '').strip()
        q_phone_raw = (request.args.get('phone') or '').strip()
        q_phone = _norm_phone(q_phone_raw) if q_phone_raw else ''
        users = MS.list_all_users()
        if q_user_id:
            try:
                users = [u for u in users if int(u.get('id') or 0) == int(q_user_id)]
            except Exception:
                users = []
        if q_phone:
            users = [u for u in users if (u.get('phone') or '') == q_phone]
        return render_template(
            'admin/users.html', users=users, user=current_user,
            q_user_id=q_user_id, q_phone=q_phone_raw,
        )

    @app.route('/admin/users/delete')
    @login_required
    def admin_users_delete_menu():
        if _r := _admin_required():
            return _r
        return render_template('admin/users_delete.html', user=current_user)

    @app.route('/admin/users/delete-from-list')
    @login_required
    def admin_users_delete_from_list():
        if _r := _admin_required():
            return _r
        q_user_id = (request.args.get('user_id') or '').strip()
        q_phone_raw = (request.args.get('phone') or '').strip()
        q_phone = _norm_phone(q_phone_raw) if q_phone_raw else ''
        users = [u for u in MS.list_all_users() if not u.get('is_protected_admin')]
        if q_user_id:
            try:
                users = [u for u in users if int(u.get('id') or 0) == int(q_user_id)]
            except Exception:
                users = []
        if q_phone:
            users = [u for u in users if (u.get('phone') or '') == q_phone]
        return render_template(
            'admin/users_delete_from_list.html', users=users, user=current_user,
            q_user_id=q_user_id, q_phone=q_phone_raw,
        )

    def _resolve_delete_phone_candidate(phone_norm: str):
        if not phone_norm:
            return None
        u = User.query.filter_by(phone=phone_norm).first()
        if u:
            return u
        auth = WebIdentityAuth.query.filter_by(phone=phone_norm).first()
        if auth and auth.user_id:
            u = User.query.get(int(auth.user_id))
            if u:
                return u
        st = WebIdentityCareerState.query.filter_by(phone=phone_norm).first()
        if st and st.user_id:
            u = User.query.get(int(st.user_id))
            if u:
                return u
        return None

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    def admin_user_delete(user_id):
        if _r := _admin_required():
            return _r
        target = User.query.get(int(user_id))
        if not target:
            flash('کاربر مورد نظر پیدا نشد.', 'danger')
            return redirect(url_for('admin_users'))
        result = MS.delete_user_everywhere(
            int(user_id), target.phone or '', _current_admin_delete_identity(), mode='single_user_id'
        )
        if not result.get('ok'):
            if result.get('protected'):
                flash('این کاربر ادمین اصلی است و قابل حذف نیست.', 'warning')
            else:
                flash(f"حذف کاربر انجام نشد: {result.get('error')}", 'danger')
            return redirect(url_for('admin_users'))
        deleted = result.get('user') or {}
        flash(
            f"کاربر حذف شد: #{deleted.get('user_id') or user_id} — {deleted.get('phone') or 'بدون شماره'} | "
            f"جزئیات ردیف‌ها: {_format_delete_counts(result.get('affected_counts'))}",
            'success'
        )
        flash('حذف در دیتابیس اعمال شد و sync حافظه به‌صورت زنده/best-effort اجرا شد.', 'info')
        return redirect(url_for('admin_users'))

    @app.route('/admin/users/delete-by-phone', methods=['GET', 'POST'])
    @login_required
    def admin_user_delete_by_phone():
        if _r := _admin_required():
            return _r
        phone_raw = (request.values.get('phone') or '').strip()
        phone_norm = _norm_phone(phone_raw) if phone_raw else ''
        if not phone_norm:
            if request.method == 'POST':
                flash('شماره موبایل معتبر وارد کنید.', 'danger')
            return render_template(
                'admin/users_delete_by_phone.html', user=current_user,
                phone_delete_raw=phone_raw, phone_delete_norm='',
            )
        target = _resolve_delete_phone_candidate(phone_norm)
        if not target:
            flash('برای این شماره کاربری در سیستم آموزشی پیدا نشد.', 'danger')
            return render_template(
                'admin/users_delete_by_phone.html', user=current_user,
                phone_delete_raw=phone_raw, phone_delete_norm=phone_norm,
            )
        if request.method == 'GET':
            return render_template(
                'admin/users_delete_by_phone.html', user=current_user,
                phone_delete_candidate=target, phone_delete_raw=phone_raw,
                phone_delete_norm=phone_norm,
            )
        result = MS.delete_user_everywhere(
            int(target.id), phone_norm, _current_admin_delete_identity(), mode='single_phone'
        )
        if not result.get('ok'):
            if result.get('protected'):
                flash('این کاربر ادمین اصلی است و قابل حذف نیست.', 'warning')
            else:
                flash(f"حذف با شماره انجام نشد: {result.get('error')}", 'danger')
            return redirect(url_for('admin_users'))
        deleted = result.get('user') or {}
        flash(
            f"کاربر با شماره حذف شد: #{deleted.get('user_id') or target.id} — {phone_norm} | "
            f"جزئیات ردیف‌ها: {_format_delete_counts(result.get('affected_counts'))}",
            'success'
        )
        flash('حذف در دیتابیس اعمال شد و sync حافظه به‌صورت زنده/best-effort اجرا شد.', 'info')
        return redirect(url_for('admin_users'))

    @app.route('/admin/users/delete-all')
    @app.route('/admin/users/delete-all/confirm')
    @login_required
    def admin_users_delete_all_confirm():
        if _r := _admin_required():
            return _r
        return render_template('admin/users_delete_all.html', user=current_user)

    @app.route('/admin/users/delete-all', methods=['POST'])
    @login_required
    def admin_users_delete_all():
        if _r := _admin_required():
            return _r
        result = MS.delete_all_users(_current_admin_delete_identity(), include_admins=True)
        if not result.get('ok'):
            flash(f"حذف همه کاربران انجام نشد: {result.get('error')}", 'danger')
            return redirect(url_for('admin_users_delete_all_confirm'))
        flash(
            f"همه کاربران حذف شدند. تعداد کاربران حذف‌شده: {result.get('deleted_count', 0)} | "
            f"ادمین‌های اصلی محافظت‌شده: {result.get('skipped_protected_count', 0)} | "
            f"جزئیات ردیف‌ها: {_format_delete_counts(result.get('affected_counts'))}",
            'success'
        )
        flash('حذف در دیتابیس اعمال شد و sync حافظه به‌صورت زنده/best-effort اجرا شد.', 'info')
        return redirect(url_for('admin_users'))

    @app.route('/admin/cash')
    @login_required
    def admin_cash():
        if _r := _admin_required():
            return _r
        pending = MS.list_pending_cash_requests()
        return render_template('admin/cash.html', requests=pending, user=current_user)

    @app.route('/admin/reports')
    @login_required
    def admin_reports():
        if _r := _admin_required():
            return _r
        try:
            stats = MS.admin_stats()
        except Exception:
            stats = {}
        return render_template('admin/reports.html', stats=stats, user=current_user)

    @app.route('/admin/messaging')
    @login_required
    def admin_messaging():
        if _r := _admin_required():
            return _r
        return render_template('admin/messaging.html', user=current_user)

    @app.route('/admin/consultant')
    @login_required
    def admin_consultant():
        if _r := _admin_required():
            return _r
        status = (request.args.get('status') or '').strip()
        q = ConsultantRequest.query.order_by(ConsultantRequest.id.desc())
        if status:
            q = q.filter_by(status=status)
        requests_list = q.limit(200).all()
        return render_template('admin/consultant.html',
                               requests=requests_list, selected_status=status,
                               item=None, messages=[], user=current_user)

    @app.route('/admin/consultant/<int:req_id>')
    @login_required
    def admin_consultant_detail(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        messages = (ConsultantMessage.query
                    .filter_by(request_id=item.id)
                    .order_by(ConsultantMessage.id.asc()).all())
        return render_template('admin/consultant.html',
                               requests=[], selected_status='',
                               item=item, messages=messages, user=current_user)

    @app.route('/admin/consultant/<int:req_id>/approve', methods=['POST'])
    @login_required
    def admin_consultant_approve(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        item.status = 'active'
        item.last_turn = 'admin'
        item.approved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(item)
        db.session.commit()
        flash('درخواست مشاوره تأیید شد.', 'success')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/consultant/<int:req_id>/reject', methods=['POST'])
    @login_required
    def admin_consultant_reject(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        item.status = 'rejected'
        item.closed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(item)
        db.session.commit()
        flash('درخواست مشاوره رد شد.', 'warning')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/consultant/<int:req_id>/pause', methods=['POST'])
    @login_required
    def admin_consultant_pause(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        item.status = 'paused'
        item.paused_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(item)
        db.session.commit()
        flash('گفتگو موقتاً متوقف شد.', 'info')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/consultant/<int:req_id>/resume', methods=['POST'])
    @login_required
    def admin_consultant_resume(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        item.status = 'active'
        item.resumed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(item)
        db.session.commit()
        flash('گفتگو دوباره فعال شد.', 'success')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/consultant/<int:req_id>/close', methods=['POST'])
    @login_required
    def admin_consultant_close(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        item.status = 'closed'
        item.closed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(item)
        db.session.commit()
        flash('پرونده مشاوره بسته شد.', 'info')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/consultant/<int:req_id>/reply', methods=['POST'])
    @login_required
    def admin_consultant_reply(req_id):
        if _r := _admin_required():
            return _r
        item = ConsultantRequest.query.get_or_404(req_id)
        text = (request.form.get('text') or '').strip()
        if text and item.status in ('active', 'approved'):
            msg = ConsultantMessage(request_id=item.id, sender='admin', text=text[:2000])
            item.status = 'active'
            item.last_turn = 'admin'
            db.session.add(msg)
            db.session.add(item)
            db.session.commit()
            flash('پاسخ مشاور ثبت شد.', 'success')
        elif item.status not in ('active', 'approved'):
            flash('برای پاسخ، درخواست باید فعال باشد.', 'warning')
        return redirect(url_for('admin_consultant_detail', req_id=item.id))

    @app.route('/admin/features')
    @login_required
    def admin_features():
        if _r := _admin_required():
            return _r
        return render_template('admin/bot_only.html',
                               feature_name="دسترسی بخش‌ها",
                               bot_path="پنل مدیریت ← 🔑 دسترسی بخش‌ها",
                               user=current_user)

    @app.route('/admin/ai')
    @login_required
    def admin_ai():
        if _r := _admin_required():
            return _r
        return render_template('admin/bot_only.html',
                               feature_name="مدیریت یار هوشمند",
                               bot_path="پنل مدیریت ← 🤖 مدیریت یار هوشمند",
                               user=current_user)

    @app.route('/admin/settings')
    @login_required
    def admin_settings():
        if _r := _admin_required():
            return _r
        return render_template('admin/bot_only.html',
                               feature_name="تنظیمات عمومی",
                               bot_path="پنل مدیریت ← ⚙️ تنظیمات عمومی",
                               user=current_user)

    @app.route('/admin/giso')
    @login_required
    def admin_giso():
        if _r := _admin_required():
            return _r
        return render_template('admin/bot_only.html',
                               feature_name="مدیریت ربات گیسو",
                               bot_path="پنل مدیریت ← 🎀 مدیریت ربات گیسو",
                               user=current_user)

    # ======================================================================
    # عارضه‌یابی و تست رایگان قبل از ثبت‌نام (Value-First Hook)
    # ======================================================================
    @app.route('/mentor/try')
    def mentor_try():
        if current_user.is_authenticated:
            if _is_site_admin():
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('mentor_dashboard'))
        ai_stat = check_ai_status()
        initial_turn = interviewer_chat([])
        return render_template('mentor_try.html', ai_status=ai_stat, initial_turn=initial_turn)

    @app.route('/api/mentor/try/chat', methods=['POST'])
    def api_mentor_try_chat():
        data = request.get_json(silent=True) or {}
        messages = data.get('messages', [])
        result = interviewer_chat(messages)
        return jsonify(result)

    @app.route('/api/mentor/try/analyze', methods=['POST'])
    def api_mentor_try_analyze():
        data = request.get_json(silent=True) or {}
        conversation = data.get('conversation', [])
        result = analyze_guest_paths(conversation)

        if result and result.get("success") is True:
            user_answers = [
                (m.get('text') or m.get('content') or '').strip()
                for m in conversation if m.get('role') == 'user'
            ]

            def _short_text(value, limit=700):
                return str(value or '')[:limit]

            compact_routes = []
            for r in (result.get("routes") or [])[:3]:
                compact_tools = [
                    {
                        "name": _short_text(t.get("name"), 100),
                        "why": _short_text(t.get("why"), 220),
                        "how_helps": _short_text(t.get("how_helps"), 260),
                    }
                    for t in (r.get("ai_tools") or [])[:3]
                    if isinstance(t, dict)
                ]
                compact_sprint = [
                    {
                        "day_range": _short_text(step.get("day_range"), 40),
                        "task": _short_text(step.get("task"), 260),
                    }
                    for step in (r.get("sprint_plan") or [])[:4]
                    if isinstance(step, dict)
                ]
                compact_routes.append({
                    "title": _short_text(r.get("title"), 160),
                    "fit_percent": r.get("fit_percent", 0),
                    "why_fit": _short_text(r.get("why_fit"), 500),
                    "first_result_window_days": _short_text(r.get("first_result_window_days"), 40),
                    "first_result_type": _short_text(r.get("first_result_type"), 220),
                    "effort_level": _short_text(r.get("effort_level"), 80),
                    "salary_note": _short_text(r.get("salary_note"), 260),
                    "ai_tools": compact_tools,
                    "sprint_plan": compact_sprint,
                    "cautions": [_short_text(x, 180) for x in (r.get("cautions") or [])[:3]],
                })

            profile_payload = result.get("user_profile") or {}
            diagnosis_payload = result.get("diagnosis") or {}
            cta_payload = result.get("cta") or {}
            metrics_payload = [
                {"label": _short_text(m.get("label"), 120), "score": m.get("score", 0)}
                for m in (result.get("metrics") or [])[:6]
                if isinstance(m, dict)
            ]

            session["guest_mentor_analysis"] = {
                "source": "mentor_try",
                "version": 2,
                "profile": {
                    "name": _short_text(profile_payload.get("name"), 80),
                    "age": _short_text(profile_payload.get("age"), 40),
                    "city": _short_text(profile_payload.get("city"), 80),
                    "current_status": _short_text(profile_payload.get("current_status"), 200),
                    "interest_direction": _short_text(profile_payload.get("interest_direction"), 200),
                    "time_available": _short_text(profile_payload.get("time_available"), 120),
                },
                "diagnosis": {
                    "main_problem": _short_text(diagnosis_payload.get("main_problem"), 700),
                    "why_this_problem": _short_text(diagnosis_payload.get("why_this_problem"), 700),
                    "readiness_level": _short_text(diagnosis_payload.get("readiness_level"), 80),
                    "contradictions": [_short_text(x, 220) for x in (diagnosis_payload.get("contradictions") or [])[:4]],
                },
                "strengths": [_short_text(x, 180) for x in (result.get("strengths") or [])[:4]],
                "challenges": [_short_text(x, 180) for x in (result.get("challenges") or [])[:4]],
                "routes": compact_routes,
                "metrics": metrics_payload,
                "cta": {
                    "title": _short_text(cta_payload.get("title"), 180),
                    "body": _short_text(cta_payload.get("body"), 500),
                    "button_text": _short_text(cta_payload.get("button_text"), 80),
                },
                "raw_answers": [_short_text(x, 500) for x in user_answers[:8]],
            }
            session.modified = True
            try:
                if current_user.is_authenticated and not _is_site_admin():
                    _sync_guest_analysis_to_bot(current_user.id, current_user.phone or '', session["guest_mentor_analysis"])
            except Exception as e:
                logger.warning('post-analysis bot sync skipped: %s', e)

            profile = result.get("user_profile", {})
            logger.info(
                "guest_mentor_analysis ذخیره شد برای: %s",
                profile.get("name", "کاربر مهمان"),
            )

        return jsonify(result)

 

    # ======================================================================
    # یار همراه من (/mentor/*) — فقط کاربران عادی
    # ادمین‌ها به‌طور خودکار به /admin هدایت می‌شوند
    # ======================================================================
    @app.route('/mentor')
    @login_required
    def mentor_dashboard():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        st = MS.get_mentor_state(current_user.id)
        if not st.get('onboarding_completed'):
            return redirect(url_for('mentor_onboarding'))
        try:
            history = json.loads(st.get('chat_history') or '[]')
        except Exception:
            history = []
        try:
            mentor_raw = st.get('mentor_data') or '{}'
            mentor_data = json.loads(mentor_raw) if isinstance(mentor_raw, str) else (mentor_raw or {})
        except Exception:
            mentor_data = {}
        guest_analysis = mentor_data.get('guest_try_analysis') or mentor_data.get('guest_mentor_analysis') or None
        latest_consultant = _latest_consultant_request(current_user.id)
        latest_consultant_payload = _consultant_request_payload(latest_consultant) if latest_consultant else None
        flags = MS.mentor_feature_flags(current_user.id)
        summary = MS.user_progress_summary(current_user.id)
        growth = _mentor_growth_context(current_user.id)
        active_path = None
        steps = []
        progress = {"total": 0, "done": 0, "percent": 0, "finished": False, "steps": []}
        milestones = []
        try:
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
            if active_path:
                steps = _ensure_steps_for_user(current_user.id)
                progress = _path_progress_info(active_path)
                if steps and not progress.get('steps'):
                    progress['steps'] = steps
                    progress['total'] = len(steps)
                milestones = _milestones(active_path)
        except Exception as e:
            logger.warning('mentor dashboard path context failed: %s', e)
        return render_template('mentor/dashboard.html',
                               user=current_user, state=st, history=history,
                               flags=flags, summary=summary,
                               growth=growth,
                               active_path=active_path,
                               steps=progress.get('steps') or steps,
                               progress=progress,
                               milestones=milestones,
                               guest_analysis=guest_analysis,
                               consultant_request=latest_consultant_payload)

    @app.route('/mentor/welcome')
    @login_required
    def mentor_welcome():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        try:
            st = WebIdentityCareerState.query.filter_by(user_id=current_user.id).first()
            mentor_data = _safe_json_loads(st.mentor_data if st else '{}', {})
            guest_analysis = mentor_data.get('guest_try_analysis')
            if not guest_analysis:
                return redirect(url_for('mentor_dashboard'))
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
            steps = _ensure_steps_for_user(current_user.id)
            progress = _path_progress_info(active_path) if active_path else {"done": 0, "total": len(steps), "percent": 0, "finished": False, "steps": steps}
            if progress.get('done', 0) > 0:
                return redirect(url_for('mentor_dashboard'))
            growth = _mentor_growth_context(current_user.id)
            return render_template('mentor/welcome.html', guest_analysis=guest_analysis, active_path=active_path,
                                   steps=steps or progress.get('steps', []), progress=progress, growth=growth)
        except Exception as e:
            logger.warning('mentor welcome failed: %s', e, exc_info=True)
            return render_template('mentor/welcome.html', guest_analysis={}, active_path=None, steps=[],
                                   progress={"done": 0, "total": 0, "percent": 0}, growth=_mentor_growth_context(current_user.id))

    @app.route('/mentor/action')
    @login_required
    def mentor_action_plan():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        st = WebIdentityCareerState.query.filter_by(user_id=current_user.id).first()
        if st is None:
            return redirect(url_for('mentor_dashboard'))
        try:
            mentor_data = json.loads(st.mentor_data or '{}')
            if not isinstance(mentor_data, dict):
                mentor_data = {}
        except Exception:
            mentor_data = {}
        guest_analysis = mentor_data.get('guest_try_analysis')
        if not guest_analysis:
            return redirect(url_for('mentor_dashboard'))
        try:
            _sync_guest_analysis_to_bot(current_user.id, current_user.phone or '', guest_analysis)
        except Exception as e:
            logger.warning('action-plan bot sync skipped: %s', e)

        active_path = None
        today_step = None
        streak_info = {"current_streak": 0, "longest_streak": 0}
        motivation_message = None
        percent_progress = 0
        path_steps_total = 0
        path_steps_done = 0
        day_number = 1
        summary = {}
        user_rank = 0
        consultant_exists = False
        try:
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
        except Exception as e:
            logger.warning('daily active path load failed: %s', e)
        try:
            today_step = MS.get_today_step(current_user.id) if hasattr(MS, 'get_today_step') else None
            if today_step and today_step.get('step_number'):
                day_number = int(today_step.get('step_number') or 1)
        except Exception as e:
            logger.warning('daily today step load failed: %s', e)
        try:
            if today_step and hasattr(MS, 'generate_daily_content'):
                content = today_step.get('content_json') or today_step.get('content') or {}
                if not (isinstance(content, dict) and content.get('lesson_text') and content.get('action_task')):
                    generated_content = MS.generate_daily_content(current_user.id, day_number)
                    if generated_content:
                        today_step = MS.get_today_step(current_user.id) if hasattr(MS, 'get_today_step') else today_step
        except Exception as e:
            logger.warning('daily content generation skipped: %s', e)
        try:
            streak_info = MS.get_streak_info(current_user.id) if hasattr(MS, 'get_streak_info') else streak_info
        except Exception as e:
            logger.warning('daily streak load failed: %s', e)
        try:
            if hasattr(MS, 'generate_daily_motivation'):
                motivation_text = MS.generate_daily_motivation(current_user.id, day_number)
                motivation_message = {"message": motivation_text}
            else:
                motivation_message = MS.get_motivation_message(current_user.id, day_number) if hasattr(MS, 'get_motivation_message') else None
        except Exception as e:
            logger.warning('daily motivation generation failed: %s', e)
            try:
                motivation_message = MS.get_motivation_message(current_user.id, day_number) if hasattr(MS, 'get_motivation_message') else None
            except Exception:
                motivation_message = None
        try:
            summary = MS.user_progress_summary(current_user.id)
        except Exception:
            summary = {"xp": getattr(current_user, 'xp', 0) or 0, "credits": getattr(current_user, 'credits', 0) or 0}
        try:
            user_rank = MS.get_user_rank(current_user.id)
        except Exception:
            user_rank = 0
        try:
            consultant_exists = bool(_latest_consultant_request(current_user.id))
        except Exception:
            consultant_exists = False
        try:
            if active_path and active_path.get('id'):
                db_path = Path(Config.BOT_EDU_DIR) / 'data' / 'bot.db'
                conn = sqlite3.connect(str(db_path))
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) AS total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS done FROM path_steps WHERE path_id=?",
                        (int(active_path.get('id')),)
                    ).fetchone()
                    path_steps_total = int((row[0] if row else 0) or 0)
                    path_steps_done = int((row[1] if row else 0) or 0)
                    percent_progress = int(path_steps_done * 100 / path_steps_total) if path_steps_total else 0
                finally:
                    conn.close()
        except Exception as e:
            logger.warning('daily progress calc failed: %s', e)
        return render_template(
            'mentor/action_plan.html',
            guest_analysis=guest_analysis,
            active_path=active_path,
            today_step=today_step,
            streak_info=streak_info,
            summary=summary,
            user_rank=user_rank,
            motivation_message=motivation_message,
            percent_progress=percent_progress,
            path_steps_total=path_steps_total,
            path_steps_done=path_steps_done,
            consultant_request_exists=consultant_exists,
        )

    @app.route('/mentor/action/done', methods=['POST'])
    @login_required
    def mentor_action_done():
        if _is_site_admin():
            return jsonify({"ok": False, "error": "admin_not_allowed"}), 403
        try:
            step_id = (request.get_json(silent=True) or {}).get('step_id')
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
            progress_before = _path_progress_info(active_path) if active_path else {"total": 0, "done": 0, "finished": False}
            if progress_before.get('finished'):
                return jsonify({"ok": True, "program_finished": True, "message": "🎉 تبریک! مسیرت تکمیل شد. آماده مرحله بعدی هستی."})
            if step_id:
                with _botdb_conn() as conn:
                    row = conn.execute(
                        """SELECT ps.status FROM path_steps ps JOIN career_paths cp ON cp.id = ps.path_id
                           WHERE ps.id=? AND cp.user_id=?""",
                        (int(step_id), int(current_user.id))
                    ).fetchone()
                    if row and row['status'] == 'completed':
                        return jsonify({"ok": True, "already_done": True, "message": "این قدم رو قبلاً انجام دادی ✅"})
            result = MS.mark_today_complete(current_user.id) if hasattr(MS, 'mark_today_complete') else {"ok": False, "error": "helper_missing"}
            if result.get('already_completed'):
                return jsonify({"ok": True, "already_done": True, "message": "این قدم رو قبلاً انجام دادی ✅"})
            if not result.get('ok'):
                return jsonify({"ok": False, "error": result.get('error') or 'step_not_completed'}), 400
            progress_after = _path_progress_info(active_path) if active_path else progress_before
            completed_count = int(progress_after.get('done') or 0)
            total = int(progress_after.get('total') or 0)
            is_final = bool(total and completed_count >= total)
            if is_final:
                xp_earned, credits_earned, mtype, badge = 50, 15, 'final', 'پایان مسیر'
                msg = '🎉 تبریک! مسیرت تکمیل شد. آماده مرحله بعدی هستی.'
            elif completed_count and completed_count % 3 == 0:
                xp_earned, credits_earned, mtype, badge = 20, 5, 'middle', 'قدم میانی'
                msg = 'آفرین! به یک نقطه میانی مهم رسیدی.'
            else:
                xp_earned, credits_earned, mtype, badge = 10, 2, 'normal', None
                msg = 'قدم امروز ثبت شد؛ بریم سراغ قدم بعدی.'
            milestone = {"type": mtype, "badge": badge, "message": msg, "completed_count": completed_count}
            if active_path:
                _append_milestone(int(active_path.get('id') or 0), milestone)
            streak = MS.update_streak(current_user.id) if hasattr(MS, 'update_streak') else result.get('streak', {})
            xp_result = MS.award_xp_from_web(current_user.id, xp=xp_earned, credits=credits_earned, reason=f"daily_step_{mtype}") if hasattr(MS, 'award_xp_from_web') else {"ok": False}
            try:
                if hasattr(MS, 'sync_progress_from_web'):
                    MS.sync_progress_from_web(current_user.id)
            except Exception as e:
                logger.debug('sync_progress_from_web skipped: %s', e)
            next_step = MS.get_today_step(current_user.id) if hasattr(MS, 'get_today_step') else None
            return jsonify({
                "ok": True,
                "new_xp": xp_result.get('new_xp', 0),
                "new_credits": xp_result.get('new_credits', 0),
                "streak": streak,
                "level_up": bool(xp_result.get('level_up')),
                "already_done": False,
                "program_finished": is_final,
                "next_step_available": bool(next_step),
                "milestone": milestone,
                "xp_earned": xp_earned,
                "credits_earned": credits_earned,
            })
        except Exception as e:
            logger.warning('mentor action done failed: %s', e, exc_info=True)
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route('/mentor/analysis')
    @login_required
    def mentor_analysis_live():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        try:
            st = WebIdentityCareerState.query.filter_by(user_id=current_user.id).first()
            mentor_data = _safe_json_loads(st.mentor_data if st else '{}', {})
            guest_analysis = mentor_data.get('guest_try_analysis') or {}
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
            progress = _path_progress_info(active_path) if active_path else {"steps": [], "done": 0, "total": 0, "percent": 0}
            growth = _mentor_growth_context(current_user.id)
            milestones = _milestones(active_path)
            remaining = [s for s in progress.get('steps', []) if s.get('status') != 'completed'][:5]
            note = 'رشد واقعی از همین قدم‌های کوچک و پیوسته ساخته می‌شود؛ مسیرت را ادامه بده.'
            try:
                prompt = f"یک یادداشت رشد کوتاه و فارسی برای کاربر بنویس. مشکل اصلی: {guest_analysis.get('diagnosis',{}).get('main_problem','')} درصد پیشرفت: {progress.get('percent',0)}. فقط ۲ جمله."
                note = web_ai_ask(prompt, max_tokens=180) or note
            except Exception:
                pass
            return render_template('mentor/analysis_live.html', guest_analysis=guest_analysis, active_path=active_path,
                                   progress=progress, growth=growth, milestones=milestones,
                                   remaining_steps=remaining, growth_note=note)
        except Exception as e:
            logger.warning('mentor analysis live failed: %s', e, exc_info=True)
            return render_template('mentor/analysis_live.html', guest_analysis={}, active_path=None,
                                   progress={"steps": [], "done": 0, "total": 0, "percent": 0},
                                   growth=_mentor_growth_context(current_user.id), milestones=[], remaining_steps=[],
                                   growth_note='فعلاً تحلیل زنده کامل نشد، اما مسیرت محفوظ است.')

    @app.route('/mentor/change-path')
    @login_required
    def mentor_change_path():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
        growth = _mentor_growth_context(current_user.id)
        return render_template('mentor/change_path.html', active_path=active_path, growth=growth)

    @app.route('/mentor/change-path/ai-suggest', methods=['POST'])
    @login_required
    def mentor_change_path_ai_suggest():
        if _is_site_admin():
            return jsonify({"ok": False, "error": "admin_not_allowed"}), 403
        try:
            data = request.get_json(silent=True) or {}
            active_path = MS.get_active_path(current_user.id) if hasattr(MS, 'get_active_path') else None
            if not active_path:
                return jsonify({"ok": False, "error": "no_active_path"}), 400
            if data.get('accept'):
                title = (data.get('title') or 'مسیر جدید پیشنهادی')[:180]
                with _botdb_conn() as conn:
                    path_id = int(active_path.get('id'))
                    row = conn.execute('SELECT interview_data_json FROM career_paths WHERE id=?', (path_id,)).fetchone()
                    j = _safe_json_loads(row['interview_data_json'] if row else '{}', {})
                    j['selected_route'] = {"title": title}
                    j['milestones'] = []
                    conn.execute('UPDATE career_paths SET target_job=?, interview_data_json=? WHERE id=?', (title, json.dumps(j, ensure_ascii=False), path_id))
                    conn.execute('DELETE FROM path_steps WHERE path_id=?', (path_id,))
                    conn.commit()
                _ensure_steps_for_user(current_user.id)
                return jsonify({"ok": True, "redirect": url_for('mentor_welcome')})
            prompt = f"با توجه به مسیر فعلی {active_path.get('target_job','')} فقط یک مسیر جایگزین فارسی و عملی برای بازار ایران پیشنهاد بده. خروجی JSON: {{\"title\":\"...\",\"why\":\"...\"}}"
            raw = web_ai_ask(prompt, max_tokens=350)
            suggestion = _safe_json_loads(raw, {})
            if not suggestion.get('title'):
                suggestion = {"title": "مسیر جایگزین عملی‌تر", "why": "این مسیر می‌تواند با زمان و شرایط فعلی شما ساده‌تر اجرا شود."}
            return jsonify({"ok": True, "suggestion": suggestion})
        except Exception as e:
            logger.warning('change path suggest failed: %s', e, exc_info=True)
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route('/mentor/live-consultant', methods=['GET'])
    @login_required
    def mentor_live_consultant_placeholder():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('mentor_action_plan'))

    @app.route('/mentor/consultant-chat')
    @login_required
    def mentor_consultant_chat():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        req_id = request.args.get('request_id', type=int)
        try:
            if req_id:
                item = ConsultantRequest.query.filter_by(id=req_id, user_id=current_user.id).first()
            else:
                item = _latest_consultant_request(current_user.id)
            if not item:
                flash('هنوز درخواست مشاوره‌ای ثبت نکرده‌اید.', 'warning')
                return redirect(url_for('mentor_dashboard'))
            messages = (ConsultantMessage.query
                        .filter_by(request_id=item.id)
                        .order_by(ConsultantMessage.id.asc()).all())
            remaining = max(0, 5 - int(item.free_user_messages_used or 0))
            return render_template('mentor/consultant_chat.html',
                                   item=item, messages=messages, remaining=remaining)
        except Exception as e:
            logger.warning('consultant chat page failed: %s', e, exc_info=True)
            flash('نمایش گفتگوی مشاور با خطا مواجه شد.', 'danger')
            return redirect(url_for('mentor_dashboard'))

    @app.route('/mentor/consultant/history')
    @login_required
    def mentor_consultant_history():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        try:
            items = (ConsultantRequest.query
                     .filter_by(user_id=current_user.id)
                     .order_by(ConsultantRequest.id.desc()).all())
            return render_template('mentor/consultant_history.html', items=items)
        except Exception as e:
            logger.warning('consultant history failed: %s', e, exc_info=True)
            flash('نمایش سوابق مشاوره با خطا مواجه شد.', 'danger')
            return redirect(url_for('mentor_dashboard'))

    @app.route('/mentor/consultant/summary/<int:request_id>')
    @login_required
    def mentor_consultant_summary(request_id):
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        try:
            item = ConsultantRequest.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()
            if item.status != 'closed':
                flash('خلاصه گفتگو فقط بعد از بسته شدن پرونده قابل نمایش است.', 'warning')
                return redirect(url_for('mentor_consultant_chat', request_id=item.id))
            messages = (ConsultantMessage.query
                        .filter_by(request_id=item.id)
                        .order_by(ConsultantMessage.id.asc()).all())
            user_messages = [m for m in messages if m.sender == 'user']
            admin_messages = [m for m in messages if m.sender == 'admin']
            return render_template('mentor/consultant_summary.html',
                                   item=item, messages=messages,
                                   user_messages=user_messages,
                                   admin_messages=admin_messages)
        except Exception as e:
            logger.warning('consultant summary failed: %s', e, exc_info=True)
            flash('نمایش خلاصه گفتگو با خطا مواجه شد.', 'danger')
            return redirect(url_for('mentor_consultant_history'))

    def _consultant_request_payload(item):
        if not item:
            return {"exists": False}
        messages = (ConsultantMessage.query
                    .filter_by(request_id=item.id)
                    .order_by(ConsultantMessage.id.asc()).all())
        remaining = max(0, 5 - int(item.free_user_messages_used or 0))
        last_msg = messages[-1] if messages else None
        return {
            "exists": True,
            "id": item.id,
            "status": item.status,
            "created_at": item.created_at or '',
            "closed_at": item.closed_at or '',
            "last_turn": item.last_turn or '',
            "remaining_free_messages": remaining,
            "free_user_messages_used": int(item.free_user_messages_used or 0),
            "can_user_send": bool(item.status == 'active' and remaining > 0 and (item.last_turn or '') != 'user'),
            "intro_message": item.intro_message,
            "last_message_id": last_msg.id if last_msg else 0,
            "last_message_sender": last_msg.sender if last_msg else '',
            "messages": [
                {"id": m.id, "sender": m.sender, "text": m.text, "created_at": m.created_at}
                for m in messages
            ],
        }

    def _latest_consultant_request(user_id):
        return (ConsultantRequest.query
                .filter_by(user_id=int(user_id))
                .order_by(ConsultantRequest.id.desc()).first())

    @app.route('/api/consultant/request', methods=['POST'])
    @login_required
    def api_consultant_request():
        data = request.get_json(silent=True) or {}
        intro = (data.get('intro_message') or '').strip()[:2000]
        if not intro:
            return jsonify({"success": False, "error": "پیام اولیه را بنویسید."}), 400
        existing = _latest_consultant_request(current_user.id)
        if existing and existing.status in ('pending', 'active', 'paused'):
            return jsonify({"success": True, "request": _consultant_request_payload(existing)})

        st = WebIdentityCareerState.query.filter_by(user_id=current_user.id).first()
        try:
            mentor_data = json.loads(st.mentor_data or '{}') if st else {}
            if not isinstance(mentor_data, dict):
                mentor_data = {}
        except Exception:
            mentor_data = {}
        analysis = mentor_data.get('guest_try_analysis') or {}
        profile = analysis.get('profile') or analysis.get('user_profile') or {}
        diagnosis = analysis.get('diagnosis') or {}
        routes = analysis.get('routes') or analysis.get('paths') or []
        first_route = routes[0] if routes else {}

        item = ConsultantRequest(
            user_id=current_user.id,
            name=(profile.get('name') or current_user.first_name or '')[:120],
            phone=(current_user.phone or '')[:30],
            city=(profile.get('city') or '')[:120],
            main_problem=(diagnosis.get('main_problem') or analysis.get('main_problem') or '')[:3000],
            selected_route_title=(first_route.get('title') or '')[:300],
            intro_message=intro,
            status='pending',
            last_turn='',
            free_user_messages_used=0,
        )
        db.session.add(item)
        db.session.commit()
        notify_text = _build_consultant_notification(item, analysis, first_route)
        _notify_consultant_admins(notify_text, item.id)
        return jsonify({"success": True, "request": _consultant_request_payload(item)})

    @app.route('/api/consultant/<int:req_id>/message', methods=['POST'])
    @login_required
    def api_consultant_message(req_id):
        item = ConsultantRequest.query.filter_by(id=req_id, user_id=current_user.id).first()
        if not item:
            return jsonify({"success": False, "error": "درخواست پیدا نشد."}), 404
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()[:2000]
        if item.status == 'rejected':
            return jsonify({"success": False, "error": "درخواست مشاوره رد شده است."}), 403
        if item.status != 'active':
            return jsonify({"success": False, "error": "درخواست هنوز فعال نشده است."}), 403
        if not text:
            return jsonify({"success": False, "error": "پیام خالی است."}), 400
        if int(item.free_user_messages_used or 0) >= 5:
            return jsonify({"success": False, "error": "سقف پیام رایگان تمام شد."}), 403
        if (item.last_turn or '') == 'user':
            return jsonify({"success": False, "error": "لطفاً منتظر پاسخ مشاور بمانید."}), 409
        msg = ConsultantMessage(request_id=item.id, sender='user', text=text)
        item.free_user_messages_used = int(item.free_user_messages_used or 0) + 1
        item.last_turn = 'user'
        db.session.add(msg)
        db.session.add(item)
        db.session.commit()
        notify_text = f"💬 پیام جدید از {_h(item.name or 'کاربر', 120)}:\n\n{_h(text, 1200)}"
        _notify_consultant_admins(notify_text, item.id, controls=True, admin_chat_id=item.admin_chat_id)
        return jsonify({"success": True, "request": _consultant_request_payload(item)})

    @app.route('/api/consultant/status')
    @login_required
    def api_consultant_status():
        item = _latest_consultant_request(current_user.id)
        return jsonify({"success": True, "request": _consultant_request_payload(item)})

    @app.route('/mentor/onboarding')
    @login_required
    def mentor_onboarding():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        st = MS.get_mentor_state(current_user.id)
        if st.get('onboarding_completed'):
            return redirect(url_for('mentor_dashboard'))
        step = int(st.get('current_step') or 1)
        return render_template('mentor/onboarding.html',
                               user=current_user, step=step, state=st,
                               questions=MS.MENTOR_ONBOARDING_QUESTIONS)

    @app.route('/mentor/save-step', methods=['POST'])
    @login_required
    def mentor_save_step():
        if _is_site_admin():
            return jsonify({'success': False, 'redirect': url_for('admin_dashboard')})
        data = request.get_json(silent=True) or request.form
        step = int(data.get('step', 1) or 1)
        answer = (data.get('answer') or '').strip()
        _digits = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
        answer = answer.translate(_digits)
        res = MS.save_mentor_step(current_user.id, step, answer)
        return jsonify({
            'success': True,
            'completed': bool(res.get('completed')),
            'next_step': int(res.get('next_step') or step + 1),
            'reply': res.get('reply', ''),
            'redirect': url_for('mentor_dashboard') if res.get('completed') else None,
        })

    @app.route('/mentor/chat', methods=['POST'])
    @login_required
    def mentor_chat():
        if _is_site_admin():
            return jsonify({'success': False, 'redirect': url_for('admin_dashboard')})
        st = MS.get_mentor_state(current_user.id)
        if not st.get('onboarding_completed'):
            return jsonify({'success': False, 'redirect': url_for('mentor_onboarding')})
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        if not msg:
            return jsonify({'success': False})
        reply = MS.mentor_chat(current_user.id, msg)
        return jsonify({'success': True, 'reply': reply})

    @app.route('/mentor/profile')
    @login_required
    def mentor_profile():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        prof = MS.mentor_profile(current_user.id)
        return render_template('mentor/profile.html', user=current_user, profile=prof,
                               state=MS.get_mentor_state(current_user.id))

    @app.route('/mentor/path')
    @login_required
    def mentor_path():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        flash('نقشه راه توسط ایجنت AI تولید می‌شود. با تنظیم کلید AI، مسیر اختصاصی شما از اینجا ساخته می‌شود. فعلاً می‌توانی از «دوره‌ها» شروع کنی.', 'info')
        return redirect(url_for('mentor_dashboard'))

    @app.route('/mentor/trends')
    @login_required
    def mentor_trends():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        if not MS._ai_ready():
            flash('ترندهای بازار نیاز به پرووایدر AI فعال دارند. با ادمین هماهنگ کنید.', 'info')
            return redirect(url_for('mentor_dashboard'))
        return render_template('mentor/trends.html')

    @app.route('/mentor/interview')
    @login_required
    def mentor_interview():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        if not MS._ai_ready():
            flash('شبیه‌ساز مصاحبه نیاز به پرووایدر AI فعال دارد.', 'info')
            return redirect(url_for('mentor_dashboard'))
        return render_template('mentor/interview.html')

    @app.route('/mentor/certs')
    @login_required
    def mentor_certs():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        prof = MS.mentor_profile(current_user.id)
        if not prof.get("certificates"):
            flash('هنوز گواهی‌ای برای شما صادر نشده است.', 'info')
            return redirect(url_for('mentor_dashboard'))
        return render_template('mentor/certs.html', certs=prof["certificates"])

    @app.route('/mentor/wallet')
    @login_required
    def mentor_wallet():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        return redirect(url_for('shop'))

    @app.route('/mentor/public')
    @login_required
    def mentor_public():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        return redirect(url_for('mentor_profile'))

    @app.route('/mentor/team')
    @login_required
    def mentor_team():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        flash('یادگیری تیمی در حال حاضر فقط از داخل ربات فعال است.', 'info')
        return redirect(url_for('mentor_dashboard'))

    # ======================================================================
    # پنل کاربری عادی (/dashboard, /courses, ...)
    # ======================================================================
    @app.route('/dashboard')
    @login_required
    def dashboard():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        summary = MS.user_progress_summary(current_user.id)
        rank = MS.get_user_rank(current_user.id)
        joined_fmt = (datetime.fromtimestamp(current_user.joined or _time.time())
                      .strftime('%Y/%m/%d')) if current_user.joined else '—'
        return render_template('dashboard.html',
                               user=current_user,
                               xp=summary.get('xp', 0),
                               credits=summary.get('credits', 0),
                               courses_count=len(MS.list_courses()),
                               missions_done=summary.get('missions_done', 0),
                               lessons_done=summary.get('lessons_done', 0),
                               paths_count=summary.get('paths_count', 0),
                               open_tickets=summary.get('open_tickets', 0),
                               rank=rank, joined_fmt=joined_fmt)

    @app.route('/courses')
    @login_required
    def courses():
        if _is_site_admin():
            return redirect(url_for('admin_courses'))
        if _r := _gate_onboarding():
            return _r
        return render_template('courses.html', user=current_user, courses=MS.list_courses())

    @app.route('/missions')
    @login_required
    def missions():
        if _is_site_admin():
            return redirect(url_for('admin_missions'))
        if _r := _gate_onboarding():
            return _r
        return render_template('missions.html', user=current_user,
                               missions=MS.list_missions(), done_ids=set())

    @app.route('/shop')
    @login_required
    def shop():
        if _is_site_admin():
            return redirect(url_for('admin_shop'))
        if _r := _gate_onboarding():
            return _r
        return render_template('shop.html', user=current_user,
                               items=MS.list_shop_items())

    @app.route('/profile')
    @login_required
    def profile():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        summary = MS.user_progress_summary(current_user.id)
        st = MS.get_mentor_state(current_user.id)
        return render_template('profile.html', user=current_user, state=st,
                               summary=summary,
                               phone_display=(('0' + current_user.phone[3:])
                                              if (current_user.phone or '').startswith('+98')
                                              else (current_user.phone or '')))

    @app.route('/support')
    @login_required
    def support():
        if _is_site_admin():
            return redirect(url_for('admin_dashboard'))
        if _r := _gate_onboarding():
            return _r
        return render_template('support.html', user=current_user,
                               open_tickets=MS.user_progress_summary(current_user.id)
                               .get('open_tickets', 0))

    @app.route('/tools')
    def tools():
        return render_template('tools.html')

    @app.route('/career-path')
    def career_path():
        if current_user.is_authenticated:
            if _is_site_admin():
                return redirect(url_for('admin_dashboard'))
            st = MS.get_mentor_state(current_user.id)
            return redirect(url_for('mentor_dashboard'
                                   if st.get('onboarding_completed')
                                   else 'mentor_onboarding'))
        return redirect(url_for('mentor_try'))

    @app.errorhandler(404)
    def _404(e):
        return render_template('404.html'), 404

    _init_web_tables(app)

    # ─── CSRF gate + injection: همهٔ POST ها؛ ساختار روت‌ها تغییر نمی‌کند ───
    @app.before_request
    def _web_csrf_gate():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        if (request.path or "").startswith("/static/"):
            return None
        supplied = (
            request.form.get("csrf_token", "")
            or request.headers.get("X-CSRF-Token", "")
            or request.headers.get("X-GISO-CSRF", "")
        )
        expected = session.get(_WEB_CSRF_KEY, "")
        if not (expected and supplied and hmac.compare_digest(str(expected), str(supplied))):
            if request.is_json or (request.path or "").startswith("/api/"):
                return jsonify({"ok": False, "error": "csrf_invalid",
                                "message": "CSRF token missing or invalid"}), 400
            abort(400, description="درخواست امنیتی نامعتبر است؛ صفحه را تازه‌سازی کنید.")

    @app.after_request
    def _web_csrf_inject(response):
        try:
            if "text/html" not in (response.content_type or ""):
                return response
            body = response.get_data(as_text=True)
            if not body:
                return response
            token = _web_csrf_token()
            changed = False
            head_meta = '<meta name="web-csrf-token" content="%s">' % token
            if head_meta not in body and "</head>" in body:
                body = body.replace("</head>", head_meta + "</head>", 1)
                changed = True
            hidden = '<input type="hidden" name="csrf_token" value="%s">' % token
            if 'name="csrf_token"' not in body:
                body, n = _WEB_CSRF_FORM_RE.subn(lambda m: m.group(0) + hidden, body)
                changed = changed or bool(n)
            if _WEB_CSRF_SCRIPT not in body and "</body>" in body:
                body = body.replace("</body>", _WEB_CSRF_SCRIPT + "</body>", 1)
                changed = True
            if changed:
                response.set_data(body)
        except Exception:
            pass
        return response

    return app


if __name__ == '__main__':
    app = create_app()
    print('=' * 60)
    print('  سایت آموزشی sadeghiai در حال اجرا...')
    print('  آدرس: http://127.0.0.1:5000')
    print('=' * 60)
    try:
        # سرویس production-ready: waitress (threaded) — پرهیز از گلوگاه تک‌نخی Flask dev
        from waitress import serve
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except ImportError:
        # fallback امن: اگر waitress در محیط نصب نبود، رفتار قبلی حفظ می‌شود
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
