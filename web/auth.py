# -*- coding: utf-8 -*-
"""
auth.py — احراز هویت وب‌سایت اصلی

قواعد:
  - ورود با شماره موبایل + رمز عبور
  - ثبت‌نام با شماره موبایل + رمز + یکی از ۴ سوال امنیتی + پاسخ امنیتی
  - رمز و پاسخ امنیتی فقط به‌شکل hash نگهداری می‌شوند
  - شماره موبایل همیشه از phoneutil مشترک نرمال می‌شود → +989xxxxxxxxx
  - در صورت وجود کاربر در جدول users (مثلاً از ربات) به همان هویت لینک می‌شود
  - در غیر این صورت یک ردیف پایه در users توسط mentor_service.get_or_create_user_by_phone
    ساخته می‌شود تا هویت مشترک حفظ شود
  - «فراموشی رمز» از طریق شماره + سوال امنیتی + پاسخ درست
"""
import re
import json
import sys
from pathlib import Path

# افزودن bot_edu و web به sys.path
_WEB_DIR = Path(__file__).resolve().parent
_BOT_EDU = _WEB_DIR.parent / 'bot_edu'
if str(_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_WEB_DIR))
if str(_BOT_EDU) not in sys.path:
    sys.path.append(str(_BOT_EDU))

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, WebIdentityAuth, WebIdentityCareerState
from config import SECURITY_QUESTIONS, SECURITY_QUESTIONS_MAP
from phoneutil import normalize_phone as _norm_phone, phone_display as _phone_display

auth_bp = Blueprint('auth', __name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'برای دسترسی به این بخش ابتدا وارد حساب شوید.'
login_manager.login_message_category = 'warning'


def _hash_answer(raw: str) -> str:
    t = (raw or '').strip().lower()
    t = re.sub(r"\s+", " ", t)
    return generate_password_hash(t, method='pbkdf2:sha256')


def _check_answer_hash(h: str, raw: str) -> bool:
    t = (raw or '').strip().lower()
    t = re.sub(r"\s+", " ", t)
    try:
        return check_password_hash(h, t)
    except Exception:
        return False


def _get_or_create_user(phone_norm: str, first_name: str = 'کاربر سایت') -> User:
    """گرفتن یا ساختن رکورد کاربر در جدول مشترک users (canonical)."""
    # از سرویس مشترک استفاده می‌کنیم تا منطق کپی نشود
    from mentor_service import get_or_create_user_by_phone
    data = get_or_create_user_by_phone(phone_norm, first_name=first_name)
    uid = int(data["user_id"])
    user = User.query.get(uid)
    if user is None:
        db.session.commit()  # اطمینان از flushing
        user = User.query.get(uid)
    return user


def _auth_extract_first_int(value, default=0) -> int:
    try:
        trans = str(value or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        m = re.search(r'\d+', trans)
        return int(m.group(0)) if m else int(default)
    except Exception:
        return int(default)


def _sync_guest_analysis_to_bot(user_id: int, guest_analysis: dict) -> bool:
    """Safe idempotent sync from web guest analysis into bot ai_mentor tables."""
    if not guest_analysis:
        return False
    try:
        from datetime import datetime
        profile = guest_analysis.get('profile') or guest_analysis.get('user_profile') or {}
        routes = guest_analysis.get('routes') or guest_analysis.get('paths') or []
        first_route = routes[0] if routes else {}
        if not first_route:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        first_name = (profile.get('name') or '').strip()[:100]
        city = (profile.get('city') or '').strip()[:100]
        age = _auth_extract_first_int(profile.get('age'), 0)
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
            for idx, step in enumerate(first_route.get('sprint_plan') or [], start=1):
                if not isinstance(step, dict):
                    continue
                title = (step.get('day_range') or f'گام {idx}')[:200]
                task = (step.get('task') or '')[:2000]
                content = {'description': task, 'task': task, 'source': 'web_guest_try'}
                payload = json.dumps(content, ensure_ascii=False)
                status = 'active' if idx == 1 else 'locked'
                conn.exec_driver_sql(
                    "INSERT INTO path_steps (path_id, step_number, step_type, title, content, status, ai_feedback, completed_at, content_json) VALUES (?, ?, 'resource', ?, ?, ?, '{}', '', ?)",
                    (path_id, idx, title, payload, status, payload)
                )
        return True
    except Exception:
        return False


def _ensure_career_state(phone_norm: str, user_id: int) -> WebIdentityCareerState:
    st = WebIdentityCareerState.query.filter_by(user_id=int(user_id)).first()
    if st is None:
        from datetime import datetime
        st = WebIdentityCareerState(phone=phone_norm, user_id=int(user_id),
                                    updated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        db.session.add(st)
        db.session.flush()
    return st


@login_manager.user_loader
def load_user(uid):
    if not uid:
        return None
    # با phone
    if str(uid).startswith('+98') or str(uid).startswith('0'):
        phone = _norm_phone(uid)
        if phone:
            u = User.query.filter_by(phone=phone).first()
            if u:
                return u
    # عددی id
    try:
        return User.query.get(int(uid))
    except Exception:
        return None


def _post_login_redirect():
    """مسیر مقصد پس از ورود موفق: ادمین به پنل ادمین، بقیه به داشبورد منتور."""
    from flask_login import current_user as _cu
    try:
        if _cu.is_authenticated and getattr(_cu, 'is_main_admin', False):
            return url_for('admin_dashboard')
    except Exception:
        pass
    return url_for('mentor_dashboard')


@login_manager.unauthorized_handler
def unauthorized():
    flash('برای دسترسی به این بخش باید ابتدا وارد شوید.', 'warning')
    return redirect(url_for('auth.login'))


# ---------- LOGIN ----------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())
    if request.method == 'POST':
        phone_raw = (request.form.get('phone') or '').strip()
        password = request.form.get('password') or ''
        phone = _norm_phone(phone_raw)
        if not phone:
            flash('شماره موبایل نامعتبر است. فرمت‌های مجاز: 09xxxxxxxxx / 9xxxxxxxxx / +989xxxxxxxxx', 'danger')
            return render_template('login.html', phone=phone_raw, questions=SECURITY_QUESTIONS)
        auth = WebIdentityAuth.query.filter_by(phone=phone).first()
        user = User.query.filter_by(phone=phone).first()
        if not auth or not user or not check_password_hash(auth.password_hash, password):
            flash('شماره موبایل یا رمز عبور اشتباه است.', 'danger')
            return render_template('login.html', phone=phone_raw, questions=SECURITY_QUESTIONS)
        if user.is_banned:
            flash('حساب شما مسدود شده است.', 'danger')
            return render_template('login.html', phone=phone_raw, questions=SECURITY_QUESTIONS)
        from datetime import datetime
        auth.last_login = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user.touch_login()
        db.session.commit()
        login_user(user, remember=bool(request.form.get('remember')))
        session.permanent = True
        flash('خوش آمدید!', 'success')
        return redirect(_post_login_redirect())
    return render_template('login.html', questions=SECURITY_QUESTIONS)


# ---------- REGISTER ----------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())
    if request.method == 'POST':
        phone_raw = (request.form.get('phone') or '').strip()
        password = request.form.get('password') or ''
        password2 = request.form.get('password2') or ''
        q_key = request.form.get('security_q') or ''
        q_ans = (request.form.get('security_a') or '').strip()

        phone = _norm_phone(phone_raw)
        if not phone:
            flash('شماره موبایل نامعتبر است. فرمت‌های مجاز: 09xxxxxxxxx / 9xxxxxxxxx / +989xxxxxxxxx', 'danger')
            return render_template('register.html', phone=phone_raw, questions=SECURITY_QUESTIONS, selected_q=q_key)
        if len(password) < 4:
            flash('رمز عبور باید حداقل ۴ کاراکتر باشد.', 'danger')
            return render_template('register.html', phone=phone_raw, questions=SECURITY_QUESTIONS, selected_q=q_key)
        if password != password2:
            flash('رمزهای عبور با هم مطابقت ندارند.', 'danger')
            return render_template('register.html', phone=phone_raw, questions=SECURITY_QUESTIONS, selected_q=q_key)
        if q_key not in SECURITY_QUESTIONS_MAP:
            flash('لطفاً یکی از سوال‌های امنیتی را انتخاب کنید.', 'danger')
            return render_template('register.html', phone=phone_raw, questions=SECURITY_QUESTIONS, selected_q=q_key)
        if len(q_ans) < 1:
            flash('لطفاً پاسخ سوال امنیتی را وارد کنید.', 'danger')
            return render_template('register.html', phone=phone_raw, questions=SECURITY_QUESTIONS, selected_q=q_key)

        existing = WebIdentityAuth.query.filter_by(phone=phone).first()
        if existing:
            flash('این شماره قبلاً ثبت‌نام شده است. لطفاً وارد شوید.', 'warning')
            return redirect(url_for('auth.login'))

        user = _get_or_create_user(phone, first_name='کاربر سایت')
        from datetime import datetime
        auth = WebIdentityAuth(
            phone=phone,
            user_id=user.id,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            security_q_key=q_key,
            security_answer_hash=_hash_answer(q_ans),
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
        db.session.add(auth)
        _ensure_career_state(phone, user.id)
        db.session.commit()

        guest_analysis = session.pop("guest_mentor_analysis", None)
        if guest_analysis and not user.is_main_admin:
            try:
                st = _ensure_career_state(phone, user.id)
                try:
                    mentor_data = json.loads(st.mentor_data or "{}")
                    if not isinstance(mentor_data, dict):
                        mentor_data = {}
                except Exception:
                    mentor_data = {}
                mentor_data["guest_try_analysis"] = guest_analysis
                mentor_data["guest_try_imported_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.onboarding_completed = True
                st.mentor_data = json.dumps(mentor_data, ensure_ascii=False)
                st.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                db.session.add(st)
                db.session.commit()
                _sync_guest_analysis_to_bot(user.id, guest_analysis)
            except Exception:
                session["guest_mentor_analysis"] = guest_analysis
                session.modified = True
                db.session.rollback()

        # ادغام نتایج عارضه‌یابی و مصاحبهٔ مهمان با پروفایل کاربری جدید
        guest_data = session.pop('guest_mentor_data', None)
        if guest_data and not user.is_main_admin:
            try:
                import mentor_service as _ms
                _ms.save_mentor_step(user.id, 1, guest_data.get("goal") or "مسیر شغلی اختصاصی")
                _ms.save_mentor_step(user.id, 2, guest_data.get("level") or "متوسط")
                _ms.save_mentor_step(user.id, 3, str(guest_data.get("hours") or 2))
                _ms.save_mentor_step(user.id, 4, "استخدام و کسب درآمد از تخصص")
            except Exception as e:
                pass

        login_user(user, remember=False)
        session.permanent = True
        flash('ثبت‌نام با موفقیت انجام شد! خوش آمدید.', 'success')
        # ادمین سایت نیازی به onboarding منتور ندارد
        if user.is_main_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('mentor_onboarding'))

    return render_template('register.html', questions=SECURITY_QUESTIONS)


# ---------- FORGOT PASSWORD ----------

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())
    step = int(request.args.get('step', 1))
    if request.method == 'POST':
        form_step = int(request.form.get('step', 1))
        if form_step == 1:
            phone_raw = (request.form.get('phone') or '').strip()
            phone = _norm_phone(phone_raw)
            if not phone:
                flash('شماره موبایل نامعتبر است.', 'danger')
                return render_template('forgot_password.html', step=1, questions=SECURITY_QUESTIONS)
            auth = WebIdentityAuth.query.filter_by(phone=phone).first()
            if not auth:
                flash('کاربری با این شماره پیدا نشد.', 'danger')
                return render_template('forgot_password.html', step=1, questions=SECURITY_QUESTIONS)
            q_key = auth.security_q_key
            q_text = SECURITY_QUESTIONS_MAP.get(q_key, '—')
            session['fp_phone'] = phone
            return render_template('forgot_password.html', step=2, phone=_phone_display(phone),
                                   q_key=q_key, q_text=q_text, questions=SECURITY_QUESTIONS)
        if form_step == 2:
            phone = session.get('fp_phone', '')
            ans = (request.form.get('answer') or '').strip()
            new_pw = request.form.get('password') or ''
            new_pw2 = request.form.get('password2') or ''
            auth = WebIdentityAuth.query.filter_by(phone=phone).first()
            if not auth:
                flash('جلسه منقضی شد، دوباره تلاش کنید.', 'warning')
                return redirect(url_for('auth.forgot_password'))
            if not _check_answer_hash(auth.security_answer_hash, ans):
                flash('پاسخ سوال امنیتی صحیح نیست.', 'danger')
                q_text = SECURITY_QUESTIONS_MAP.get(auth.security_q_key, '—')
                return render_template('forgot_password.html', step=2,
                                       phone=_phone_display(phone),
                                       q_key=auth.security_q_key, q_text=q_text,
                                       questions=SECURITY_QUESTIONS)
            if len(new_pw) < 4:
                flash('رمز جدید باید حداقل ۴ کاراکتر باشد.', 'danger')
                q_text = SECURITY_QUESTIONS_MAP.get(auth.security_q_key, '—')
                return render_template('forgot_password.html', step=2,
                                       phone=_phone_display(phone),
                                       q_key=auth.security_q_key, q_text=q_text,
                                       questions=SECURITY_QUESTIONS)
            if new_pw != new_pw2:
                flash('رمزهای جدید تطابق ندارند.', 'danger')
                q_text = SECURITY_QUESTIONS_MAP.get(auth.security_q_key, '—')
                return render_template('forgot_password.html', step=2,
                                       phone=_phone_display(phone),
                                       q_key=auth.security_q_key, q_text=q_text,
                                       questions=SECURITY_QUESTIONS)
            auth.password_hash = generate_password_hash(new_pw, method='pbkdf2:sha256')
            db.session.commit()
            session.pop('fp_phone', None)
            flash('رمز عبور با موفقیت به‌روز شد. حالا می‌توانید وارد شوید.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', step=step, questions=SECURITY_QUESTIONS)


# ---------- LOGOUT ----------

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('با موفقیت خارج شدید.', 'info')
    return redirect(url_for('index'))
