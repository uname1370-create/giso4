# -*- coding: utf-8 -*-
"""
bot_admin_utils — سرویس‌های ادمین/کاربر ربات گیسو: پروفایل، آنالیز، داشبورد هوشمند، مشاوره/تیکت، آدرس سایت، خواندن فروشگاه
Phase 2 / U6 extraction from giso/bot.py — NO behavior change; re-exported from giso.bot.
"""
import logging

from giso.base import (
    _fa_num, _get_giso_user, _is_super_admin, _phone_variants,
    _upsert_giso_user, get_giso_db_conn, normalize_phone,
)
from giso.ai_runtime import (
    NO_ACCESS_MESSAGE, PROVIDER_ERROR_MESSAGE, build_admin_task_hints,
    chat_with_managed_ai, get_context_scope, get_display_name,
)

from giso.bot_helpers import _extract_analysis_score, _extract_analysis_topic

logger = logging.getLogger("giso_bot")

DEFAULT_SITE_BASE_URL = "https://gisosadeghi.ir"


SITE_BASE_URL = DEFAULT_SITE_BASE_URL


def _is_special_admin_bot(uid=None, phone: str = "") -> bool:
    """ادمین اختصاصی گیسو (نقش «special») — جدا از سوپرادمین؛ فقط روی شماره تعریف‌شده.

    فیکس موضعی مرحله ۶: در کل bot.py با همین تابع تشخیص داده می‌شود و هیچ جایی
    نقش سوپر به او داده نمی‌شود (تنظیمات/پشتیبان/پروکسی/مدیریت ادمین بسته می‌ماند).
    """
    try:
        from giso.config import is_special_admin
        return bool(is_special_admin(uid=uid, phone=(phone or "")))
    except Exception:
        return False


# برچسب دکمه‌ی دستیار هوشمند اختصاصی «آقا رضا» (فقط برای ادمین اختصاصی)
SPECIAL_ASSISTANT_BTN = "🤖 آقا رضا"
_SPECIAL_ASSISTANT_EXIT_TEXTS = frozenset({"بستن", "بازگشت", "❌ بستن", "خروج", "/exit", "بازگشت به منو"})


def _special_menu_kb():
    """کیبورد ادمین اختصاصی: فقط بخش‌های عملیاتی مجاز + دکمه آقا رضا (بدون تنظیمات/پشتیبان)."""
    try:
        from telegram import KeyboardButton, ReplyKeyboardMarkup
    except ImportError:  # محیط بدون کتابخانه‌ی بله/تلگرام (تست)
        KeyboardButton = globals().get("KeyboardButton")
        ReplyKeyboardMarkup = globals().get("ReplyKeyboardMarkup")
    keyboard = [
        [KeyboardButton("📊 پیشخوان"), KeyboardButton(SPECIAL_ASSISTANT_BTN)],
        [KeyboardButton("💇 خرید مو"), KeyboardButton("🛍 فروشگاه")],
        [KeyboardButton("🏪 بازارچه"), KeyboardButton("🏥 مراکز زیبایی")],
        [KeyboardButton("💬 مدیریت گفتگوها")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def _special_welcome_text() -> str:
    """پیام خوش‌آمد آقا رضا برای ادمین اختصاصی در ربات بله (مشترک با تاریخچه سایت)."""
    try:
        from giso import special_assistant as _sa
        stats = _sa.live_stats()
        blocks = [
            "سلام خانم مهندس صادقی عزیز! 🌸",
            "پنل اختصاصی شما در ربات فعال شد. من «آقا رضا» هستم؛ دستیار هوشمند شما برای مدیریت گیسو.",
            "دکمه‌ی «🤖 آقا رضا» را بزنید تا هر سؤال یا گزارش مدیریتی‌ای خواستید بپرسید. تاریخچه‌ی گفتگو با پنل سایت مشترک است.",
            "",
            "📌 نگاه سریع به الان:",
            f"• درخواست مو در انتظار: {stats.get('hair_orders_pending', 0)}",
            f"• آگهی بازارچه در انتظار: {stats.get('marketplace_pending_listings', 0)}",
            f"• مرکز در انتظار تأیید: {stats.get('centers_pending', 0)}",
            f"• تیکت باز: {stats.get('open_tickets', 0)}",
        ]
        return "\n".join(blocks)
    except Exception as _e:
        logger.debug(f"_special_welcome_text: {_e}")
        return (
            "سلام خانم مهندس صادقی عزیز! 🌸 پنل اختصاصی شما فعال شد.\n"
            "من «آقا رضا» هستم؛ برای گزارش یا سؤال مدیریتی، دکمه‌ی «🤖 آقا رضا» را بزنید."
        )


async def handle_special_assistant_bot_text(msg, context, update, uid: int, phone: str, special_chat_active: set) -> bool:
    """شاخه‌ی گفتگوی «آقا رضا» در ربات برای ادمین اختصاصی.

    فقط وقتی فعال است که: شماره‌ی ادمین اختصاصی باشد، سوپر نباشد و متن یا دکمه‌ی
    «🤖 آقا رضا» یا گفتگوی فعال باشد. در غیر این صورت False برمی‌گرداند تا جریان
    عادی ادمین/کاربر ادامه پیدا کند.
    """
    text = str(getattr(msg, "text", "") or "").strip()
    if not (_is_special_admin_bot(uid, phone) and not _is_super_admin(uid, phone)):
        return False
    if text == SPECIAL_ASSISTANT_BTN:
        special_chat_active.add(uid)
        try:
            from giso.special_assistant import get_history, actor_key_for, live_stats as _sa_stats
            _sa_stats()  # ensure table ready
            hist = get_history(actor_key_for(phone))[-3:]
            recent = "\n".join(
                ("🧑🏻‍💼 " if h.get("role") == "user" else "🤖 ") + (h.get("content", "") or "")[:120]
                for h in hist
            )
            tip = ""
            if recent:
                tip = "\n\n— آخرین گپ مشترک با پنل سایت —\n" + recent
        except Exception:
            tip = ""
        await msg.reply_text(
            "🤖 آقا رضا آماده است خانم مهندس! 🌸\n"
            "هر سؤال یا گزارش مدیریتی درباره گیسو را بنویسید؛ مثلاً «گزارش امروز» یا «درخواست‌های مو را جمع‌بند».\n"
            "برای خروج از گفتگو کافیست یکی از دکمه‌های منو (مثل 📊 پیشخوان) را بزنید." + tip,
            reply_markup=_special_menu_kb(),
        )
        return True
    if text in _SPECIAL_ASSISTANT_EXIT_TEXTS:
        special_chat_active.discard(uid)
    elif uid in special_chat_active:
        if text in {"📊 پیشخوان", "💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "🏥 مراکز زیبایی", "💬 مدیریت گفتگوها"}:
            special_chat_active.discard(uid)
            # به جریان عادی منوی ادمین می‌سپاریم (return نکردن در پایین)
        else:
            try:
                from giso.special_assistant import answer as _sa_answer
                async def _sa_reply():
                    res = await _sa_answer(phone, text, channel="bot", page_path="bot")
                    return res
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                res = await _sa_reply()
                await msg.reply_text(res.get("text") or "برداشت نشد؛ دوباره بپرسید. 🌸",
                                     reply_markup=_special_menu_kb())
            except Exception as _e_sa:
                logger.debug(f"special assistant bot reply: {_e_sa}")
                await msg.reply_text(
                    "خانم مهندس، الان دستیار هوشمند در دسترس نیست؛ کمی بعد دوباره بپرسید. 🌸",
                    reply_markup=_special_menu_kb())
            return True
    return False


def _complete_hair_order_mission(order_id: int) -> None:
    """مأموریت «تکمیل خرید مو» (best-effort؛ اگر مأموریت فعال نباشد هیچ اتفاقی نمی‌افتد)."""
    try:
        with get_giso_db_conn() as _hconn:
            _hrow = _hconn.execute(
                "SELECT w.id FROM giso_web_auth w WHERE w.phone = "
                "(SELECT phone FROM hair_orders WHERE id=?) LIMIT 1",
                (order_id,),
            ).fetchone()
        if _hrow and _hrow["id"]:
            from giso.wallet import complete_mission as _cm_hair
            _cm_hair(int(_hrow["id"]), "hair_completed", event_key=f"hair-done:{order_id}")
    except Exception as _hair_done_e:
        logger.warning("hair_completed mission failed: %s", _hair_done_e)


def is_user_giso_admin(uid, phone="") -> bool:
    if _is_super_admin(uid, phone):
        return True
    # لیست سیاه: ادمینِ حذف‌شده نباید با اشتراک مجدد شماره دوباره ادمین شود
    try:
        from giso.base import is_admin_demoted
        if is_admin_demoted(bale_id=str(uid), phone=phone):
            return False
    except Exception:
        pass
    user_rec = _get_giso_user(uid)
    if user_rec and user_rec.get("is_admin"):
        return True
    try:
        from giso_admin import find_giso_admin
        if find_giso_admin(phone, str(uid)):
            _upsert_giso_user(uid, phone=phone, is_admin=True, pending_request=False)
            return True
    except Exception:
        pass
    return False



def _shop_order_rows(phone: str, limit: int = 5):
    """آخرین سفارش‌های فروشگاه کاربر از giso.db (به تفکیک شماره نرمال‌شده)."""
    try:
        np_ = normalize_phone(phone or "")
    except Exception:
        np_ = (phone or "").strip()
    if not np_:
        return []
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                """SELECT po.id, po.checkout_id, po.invoice_id, po.tracking_code,
                          po.quantity, po.status, po.created_at,
                          COALESCE(p.name, 'محصول حذف‌شده') AS pname,
                          COALESCE(p.price, 0) AS price
                   FROM product_orders po
                   LEFT JOIN products p ON p.id = po.product_id
                   WHERE po.phone=? ORDER BY po.id DESC LIMIT ?""",
                (np_, limit),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"_shop_order_rows: {e}")
        return []



def _group_shop_order_rows(rows):
    """گروه‌بندی اقلام یک checkout برای نمایش یک سفارش/کد پیگیری در ربات."""
    groups = []
    by_key = {}
    for row in rows or []:
        item = dict(row)
        checkout_id = int(item.get("checkout_id") or 0)
        key = ("checkout", checkout_id) if checkout_id else ("legacy", int(item.get("id") or 0))
        group = by_key.get(key)
        if group is None:
            group = {
                "checkout_id": checkout_id,
                "invoice_id": int(item.get("invoice_id") or 0),
                "tracking_code": item.get("tracking_code") or f"#{item.get('id')}",
                "created_at": item.get("created_at") or "",
                "status": item.get("status") or "pending",
                "items": [], "total": 0,
            }
            by_key[key] = group
            groups.append(group)
        group["items"].append(item)
        group["total"] += int(item.get("price") or 0) * int(item.get("quantity") or 1)
    return groups



def _lookup_user_delete_info(target) -> dict:
    """دریافت اطلاعات کامل کاربر برای تأیید حذف (با شناسه یا شماره)."""
    return _lookup_user_info(target)



def _lookup_user_info(target) -> dict:
    """دریافت اطلاعات کامل کاربر سایت/ربات با شناسه، شماره یا نام."""
    try:
        with get_giso_db_conn() as conn:
            row = None
            # جستجو با شناسه بله/تلگرام
            row = conn.execute(
                "SELECT bale_id, phone, first_name, created_at, is_admin FROM giso_users WHERE bale_id=?",
                (str(target),)
            ).fetchone()
            if not row:
                # جستجو با شماره در giso_users (با تمام فرمت‌های شماره)
                for pv in _phone_variants(target):
                    row = conn.execute(
                        "SELECT bale_id, phone, first_name, created_at, is_admin FROM giso_users WHERE phone=?",
                        (pv,)
                    ).fetchone()
                    if row:
                        break
            if row:
                bale_id = str(row["bale_id"] or "")
                phone = row["phone"] or ""
                name = row["first_name"] or "کاربر"
                created = row["created_at"] or "—"
                is_admin = bool(row["is_admin"])
                variants = _phone_variants(phone) if phone else [phone]
                n_hair = n_an = n_shop = 0
                for ph in variants:
                    n_hair += conn.execute("SELECT COUNT(*) FROM hair_orders WHERE phone=?", (ph,)).fetchone()[0]
                    n_an += conn.execute("SELECT COUNT(*) FROM analyses WHERE phone=?", (ph,)).fetchone()[0]
                    n_shop += conn.execute("SELECT COUNT(*) FROM product_orders WHERE phone=?", (ph,)).fetchone()[0]
                return {
                    "bale_id": bale_id, "phone": phone, "name": name,
                    "created_at": created, "is_admin": is_admin,
                    "hair": n_hair, "analysis": n_an, "shop": n_shop,
                }
            # کاربر فقط در سایت (بدون ربات)
            if np := normalize_phone(target):
                w = conn.execute(
                    "SELECT phone, name, created_at FROM giso_web_auth WHERE phone=?", (np,)
                ).fetchone()
                if w:
                    return {
                        "bale_id": "", "phone": np, "name": w["name"] or "کاربر",
                        "created_at": w["created_at"] or "—", "is_admin": False,
                        "hair": 0, "analysis": 0, "shop": 0,
                    }
    except Exception as e:
        logger.error(f"lookup user delete info: {e}")
    return None



def _get_giso_site_url():
    """دریافت آدرس فعلی سایت گیسو از giso_config."""
    from giso.base import get_giso_db_conn

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM giso_config WHERE key='site_base_url'")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).rstrip('/')
        return DEFAULT_SITE_BASE_URL
    except Exception as e:
        logger.error(f"_get_giso_site_url: {e}")
        return DEFAULT_SITE_BASE_URL



def _set_giso_site_url(new_url):
    """ذخیره آدرس جدید سایت گیسو."""
    from giso.base import get_giso_db_conn
    from datetime import datetime

    new_url = (new_url or "").strip().rstrip('/')
    if not new_url:
        return False, "آدرس نمی‌تواند خالی باشد"
    if not (new_url.startswith('http://') or new_url.startswith('https://')):
        return False, "آدرس باید با http:// یا https:// شروع شود"

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS giso_config ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key TEXT UNIQUE NOT NULL, "
            "value TEXT DEFAULT '', "
            "updated_at TEXT DEFAULT '')"
        )
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("SELECT id FROM giso_config WHERE key='site_base_url'")
        exists = cursor.fetchone()
        if exists:
            cursor.execute(
                "UPDATE giso_config SET value=?, updated_at=? WHERE key='site_base_url'",
                (new_url, now)
            )
        else:
            cursor.execute(
                "INSERT INTO giso_config (key, value, updated_at) VALUES ('site_base_url', ?, ?)",
                (new_url, now)
            )
        conn.commit()
        conn.close()
        # 🔄 همگام‌سازی با bot.db: پنل ربات edu (لینک‌های موقت/گزارش سلامت) همین
        # کلید را از bot.db می‌خواند؛ بدون این، مقدار در دو دیتابیس از هم جدا می‌شد.
        try:
            from giso.db_core import sync_site_config_to_bot_db
            sync_site_config_to_bot_db("site_base_url", new_url)
        except Exception as _sync_err:
            logger.warning(f"site_base_url sync to bot.db skipped: {_sync_err}")
        return True, "آدرس با موفقیت ذخیره شد"
    except Exception as e:
        logger.error(f"_set_giso_site_url: {e}")
        return False, f"خطا: {str(e)[:100]}"



def _test_giso_site_url(url):
    """تست دسترسی به آدرس سایت."""
    import time
    try:
        import requests
        start = time.time()
        response = requests.get(url, timeout=10, allow_redirects=True)
        elapsed = int((time.time() - start) * 1000)
        return {
            'success': response.status_code < 500,
            'status_code': response.status_code,
            'time_ms': elapsed,
            'message': 'در دسترس' if response.status_code < 400 else 'در دسترس ولی خطا',
        }
    except ImportError:
        try:
            from urllib.request import urlopen
            start = time.time()
            response = urlopen(url, timeout=10)
            elapsed = int((time.time() - start) * 1000)
            return {
                'success': True,
                'status_code': getattr(response, 'status', 200),
                'time_ms': elapsed,
                'message': 'در دسترس',
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'time_ms': 0,
                'message': f'خطا: {str(e)[:80]}',
            }
    except Exception as e:
        return {
            'success': False,
            'status_code': 0,
            'time_ms': 0,
            'message': f'خطا: {str(e)[:80]}',
        }



def _check_site_user_info(phone):
    """چک اطلاعات کاربر از سایت (giso_web_auth و analyses)."""
    from giso.base import get_giso_db_conn

    info = {
        'has_account': False,
        'name': '',
        'city': '',
        'analyses_count': 0,
        'has_hair_analysis': False,
        'has_skin_analysis': False,
        'last_analysis_type': None,
        'last_analysis_id': None,
        'has_active_checklist': False,
    }

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, city FROM giso_web_auth WHERE phone=?", (phone,))
        user = cursor.fetchone()

        if not user:
            return info

        info['has_account'] = True
        info['name'] = (user[1] or '') if len(user) > 1 else ''
        info['city'] = (user[2] or '') if len(user) > 2 else ''
        user_id = user[0]

        cursor.execute(
            "SELECT id, type, plan_json FROM analyses WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        )
        analyses = cursor.fetchall()

        info['analyses_count'] = len(analyses)

        for a in analyses:
            if a[1] == 'hair':
                info['has_hair_analysis'] = True
            elif a[1] == 'skin':
                info['has_skin_analysis'] = True

        if analyses:
            info['last_analysis_id'] = analyses[0][0]
            info['last_analysis_type'] = analyses[0][1]
            plan_raw = analyses[0][2] or ''
            if plan_raw and plan_raw.strip() not in ('', '{}'):
                info['has_active_checklist'] = True

        conn.close()
    except Exception as e:
        logger.error(f"_check_site_user_info: {e}")

    return info



def _build_welcome_from_site(info, first_name):
    """ساخت پیام خوش‌آمد بر اساس اطلاعات سایت."""
    name = info.get('name') or first_name or 'دوست عزیز'

    parts = [f"🌸 سلام {name} عزیز، به گیسو خوش اومدی!"]
    parts.append("")
    parts.append("✅ اطلاعات شما از سایت گیسو دریافت شد:")

    if info.get('city'):
        parts.append(f"📍 شهر: {info.get('city')}")

    if info.get('analyses_count', 0) > 0:
        parts.append(f"📊 تعداد تحلیل‌های شما: {_fa_num(info.get('analyses_count', 0))}")

        types = []
        if info.get('has_hair_analysis'):
            types.append("💇 مو")
        if info.get('has_skin_analysis'):
            types.append("✨ پوست")

        if types:
            parts.append(f"🔬 نوع تحلیل‌ها: {' و '.join(types)}")

        parts.append("")
        parts.append("از منوی *«🔍 آنالیز هوشمند»* می‌تونی:")
        parts.append("• 📋 تحلیل‌های قبلی رو ببینی")

        if info.get('has_active_checklist'):
            parts.append("• ✅ چک‌لیست پیشرفتت رو دنبال کنی")

        parts.append("• 💬 با مشاور صحبت کنی")
        parts.append("• 🛒 محصولات پیشنهادی رو ببینی")
    else:
        parts.append("")
        parts.append("هنوز تحلیلی انجام ندادی. برای شروع، وارد سایت گیسو شو:")
        parts.append(f"🌐 {_get_giso_site_url()}/analysis")

    parts.append("")
    parts.append("📱 برای شروع، از منوی پایین گزینه مورد نظر رو انتخاب کن.")

    return "\n".join(parts)



def _default_welcome_message(first_name):
    """پیام خوش‌آمد پیش‌فرض."""
    name = first_name or 'دوست عزیز'
    return (
        f"🌸 سلام {name} عزیز!\n\n"
        f"به ربات گیسو خوش اومدی. اینجا می‌تونی:\n"
        f"💇 فروش مو انجام بدی\n"
        f"🔬 تحلیل‌های آنالیز پوست و مو رو دنبال کنی\n"
        f"🛒 محصولات فروشگاه گیسو رو ببینی\n"
        f"💬 با مشاور صحبت کنی\n\n"
        f"📱 برای انجام تحلیل جدید، وارد سایت گیسو شو:\n"
        f"🌐 {_get_giso_site_url()}/analysis\n\n"
        f"از منوی پایین گزینه مورد نظر رو انتخاب کن."
    )



def _get_user_phone(user_id):
    """دریافت شماره تماس کاربر از giso_users."""
    from giso.base import get_giso_db_conn
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT phone FROM giso_users WHERE bale_id=?", (str(user_id),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception as e:
        logger.error(f"_get_user_phone: {e}")
        return None



def _get_user_analyses(phone, limit=10):
    """لیست تحلیل‌های کاربر."""
    from giso.base import get_giso_db_conn
    analyses = []
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM giso_web_auth WHERE phone=?", (phone,))
        user = cursor.fetchone()
        if not user:
            return []

        user_id = user[0]

        cursor.execute(
            "SELECT id, type, created_at, ai_report_json, plan_json "
            "FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )

        for row in cursor.fetchall():
            analyses.append({
                'id': row[0],
                'type': row[1],
                'created_at': row[2] or '',
                'ai_report_json': row[3],
                'plan_json': row[4],
            })

        conn.close()
    except Exception as e:
        logger.error(f"_get_user_analyses: {e}")

    return analyses



def _get_analysis_by_id(analysis_id, phone):
    """دریافت یک تحلیل خاص با چک مالکیت."""
    from giso.base import get_giso_db_conn
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM giso_web_auth WHERE phone=?", (phone,))
        user = cursor.fetchone()
        if not user:
            return None

        cursor.execute(
            "SELECT id, type, created_at, ai_report_json, plan_json, checklist_progress "
            "FROM analyses WHERE id=? AND user_id=?",
            (analysis_id, user[0])
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'type': row[1],
            'created_at': row[2] or '',
            'ai_report_json': row[3],
            'plan_json': row[4],
            'checklist_progress': row[5],
        }
    except Exception as e:
        logger.error(f"_get_analysis_by_id: {e}")
        return None



def _get_latest_analysis(phone):
    """آخرین تحلیل کاربر."""
    analyses = _get_user_analyses(phone, limit=1)
    return analyses[0] if analyses else None



def _get_latest_analysis_with_plan(phone):
    """آخرین تحلیل کاربر که برنامه دارد."""
    from giso.base import get_giso_db_conn
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM giso_web_auth WHERE phone=?", (phone,))
        user = cursor.fetchone()
        if not user:
            return None

        cursor.execute(
            "SELECT id, type, created_at, plan_json, checklist_progress "
            "FROM analyses "
            "WHERE user_id=? AND plan_json IS NOT NULL AND plan_json != '' AND plan_json != '{}' "
            "ORDER BY id DESC LIMIT 1",
            (user[0],)
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'type': row[1],
            'created_at': row[2] or '',
            'plan_json': row[3],
            'checklist_progress': row[4],
        }
    except Exception as e:
        logger.error(f"_get_latest_analysis_with_plan: {e}")
        return None



def _is_giso_admin(user_id):
    """چک ادمین بودن کاربر."""
    try:
        from giso.base import get_giso_db_conn
        conn = get_giso_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM giso_users WHERE bale_id=?", (str(user_id),))
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception:
        return False



def _get_admin_analysis_stats():
    """آمار کلی برای پنل ادمین."""
    from giso.base import get_giso_db_conn
    from datetime import datetime, timedelta

    stats = {
        'total': 0, 'hair_count': 0, 'skin_count': 0,
        'today': 0, 'this_week': 0, 'this_month': 0,
        'total_consultants': 0, 'pending_consultants': 0,
        'total_products': 0, 'pending_products': 0,
        'avg_rating': 0, 'total_reviews': 0,
    }

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM analyses")
        stats['total'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM analyses WHERE type='hair'")
        stats['hair_count'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analyses WHERE type='skin'")
        stats['skin_count'] = cursor.fetchone()[0]

        now = datetime.now()
        today_start = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        cursor.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (today_start,))
        stats['today'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (week_start,))
        stats['this_week'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (month_start,))
        stats['this_month'] = cursor.fetchone()[0]

        try:
            cursor.execute("SELECT COUNT(*) FROM consultant_requests")
            stats['total_consultants'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new', 'reviewing')")
            stats['pending_consultants'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute("SELECT COUNT(*) FROM product_requests")
            stats['total_products'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM product_requests WHERE status='pending'")
            stats['pending_products'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute("SELECT AVG(chat_rating), COUNT(*) FROM analyses WHERE chat_rating > 0")
            row = cursor.fetchone()
            if row and row[0]:
                stats['avg_rating'] = round(row[0], 1)
                stats['total_reviews'] = row[1]
        except Exception:
            pass

        conn.close()
    except Exception as e:
        logger.error(f"_get_admin_analysis_stats: {e}")

    return stats



def _get_recent_analyses(limit=10):
    """آخرین تحلیل‌ها با اطلاعات کامل کاربر."""
    from giso.base import get_giso_db_conn
    analyses = []
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT a.id, a.type, a.created_at, a.chat_rating, "
            "a.ai_report_json, a.plan_json, u.name, u.phone "
            "FROM analyses a LEFT JOIN giso_web_auth u ON a.user_id = u.id "
            "ORDER BY a.id DESC LIMIT ?",
            (limit,)
        )

        for row in cursor.fetchall():
            topic = _extract_analysis_topic(row[4], row[1])
            score = _extract_analysis_score(row[4])
            name = row[6] or 'کاربر بدون نام'
            phone = row[7] or 'ثبت نشده'
            analyses.append({
                'id': row[0],
                'type': row[1] or 'hair',
                'topic': topic,
                'score': score,
                'created_at': row[2] or '',
                'review_rating': row[3] or 0,
                'user_name': name,
                'phone': phone,
                'has_plan': bool(row[5]),
            })

        conn.close()
    except Exception as e:
        logger.error(f"_get_recent_analyses: {e}")

    return analyses



def _get_recent_consultant_requests(limit=10):
    """آخرین درخواست‌های مشاوره."""
    from giso.base import get_giso_db_conn
    requests_list = []
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, customer_name, phone, initial_message, status, created_at "
            "FROM consultant_requests ORDER BY id DESC LIMIT ?",
            (limit,)
        )

        for row in cursor.fetchall():
            requests_list.append({
                'id': row[0],
                'customer_name': row[1] or 'نامشخص',
                'phone': row[2] or 'نامشخص',
                'initial_message': row[3] or '',
                'status': row[4] or 'new',
                'created_at': row[5] or '',
            })

        conn.close()
    except Exception as e:
        logger.error(f"_get_recent_consultant_requests: {e}")

    return requests_list



def _get_recent_product_requests(limit=10):
    """آخرین محصولات درخواستی."""
    from giso.base import get_giso_db_conn
    requests_list = []
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, phone, city, problem_summary, status, created_at "
            "FROM product_requests ORDER BY id DESC LIMIT ?",
            (limit,)
        )

        for row in cursor.fetchall():
            requests_list.append({
                'id': row[0],
                'phone': row[1] or 'نامشخص',
                'city': row[2] or '',
                'problem_summary': row[3] or '',
                'status': row[4] or 'pending',
                'created_at': row[5] or '',
            })

        conn.close()
    except Exception as e:
        logger.error(f"_get_recent_product_requests: {e}")

    return requests_list



def _ensure_bot_consultant_chat_table():
    """اطمینان از وجود جدول چت مشاور در ربات."""
    from giso.base import get_giso_db_conn
    try:
        conn = get_giso_db_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_bot_consultant_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bale_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"_ensure_bot_consultant_chat_table: {e}")



def _save_bot_chat_message(user_bale_id, role, message):
    """ذخیره پیام چت مشاور در ربات."""
    from giso.base import get_giso_db_conn
    from datetime import datetime
    try:
        _ensure_bot_consultant_chat_table()
        conn = get_giso_db_conn()
        conn.execute(
            "INSERT INTO giso_bot_consultant_chat (bale_id, role, message, created_at) "
            "VALUES (?, ?, ?, ?)",
            (str(user_bale_id), role, message,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"_save_bot_chat_message: {e}")



def _get_bot_chat_history(user_bale_id, limit=6):
    """تاریخچه چت مشاور در ربات (جدیدترین‌ها، سپس مرتب شده)."""
    from giso.base import get_giso_db_conn
    history = []
    try:
        _ensure_bot_consultant_chat_table()
        conn = get_giso_db_conn()
        rows = conn.execute(
            "SELECT role, message FROM giso_bot_consultant_chat "
            "WHERE bale_id=? ORDER BY id DESC LIMIT ?",
            (str(user_bale_id), limit)
        ).fetchall()
        conn.close()
        for row in reversed(rows):
            history.append({'role': row[0], 'message': row[1]})
    except Exception as e:
        logger.error(f"_get_bot_chat_history: {e}")
    return history



def _get_user_full_context(phone, user_bale_id):
    """زمینه کامل گزارش‌محور کاربر برای مشاور هوشمند.

    فقط گزارش/پیشنهاد/تحلیل می‌سازد (هیچ اقدام یا تغییر داده‌ای نه). ساخت آن به ماژول
    اختصاصی `giso.consultant_context` وکالت شده تا این فایل بزرگ نشود و منطق تکراری نباشد.
    """
    try:
        from giso.consultant_context import build_user_consultant_context
        return build_user_consultant_context(phone, user_bale_id)
    except Exception as e:
        logger.error(f"_get_user_full_context: {e}")
        return {
            "user_name": "دوست عزیز", "user_phone": phone or "", "user_city": "",
            "last_analysis_info": "خطا در دریافت اطلاعات", "active_plan_info": "برنامه فعالی نیست",
            "checklist_info": "چک‌لیست فعالی نیست", "product_requests_info": "درخواست محصولی نیست",
            "hair_orders_info": "سفارش فروش مو ثبت نشده", "shop_orders_info": "خریدی از فروشگاه نیست",
            "wallet_info": "", "marketplace_info": "", "center_info": "",
            "tickets_info": "", "notifications_info": "", "key_notes": "گفتگوی جدید",
            "inactive_guidance": "",
        }
def _get_admin_ai_context(user_bale_id, phone, role: str):
    stats = _get_admin_dashboard_stats()
    role = (role or "admin").strip().lower()
    first_name = "مدیر"
    try:
        user_rec = _get_giso_user(user_bale_id) or {}
        first_name = (user_rec.get("first_name") or "").strip() or first_name
    except Exception:
        pass
    context = {
        "admin_name": first_name,
        "admin_phone": phone or "",
        "admin_role": "سوپرادمین" if role == "super" else "ادمین",
        "today_analyses": stats.get('today_analyses', 0),
        "today_hair_sales": stats.get('today_hair_sales', 0),
        "today_shop_orders": stats.get('today_shop_orders', 0),
        "today_new_users": stats.get('today_new_users', 0),
        "pending_hair_reviews": stats.get('pending_hair_reviews', 0),
        "pending_shop_orders": stats.get('pending_shop_orders', 0),
        "pending_tickets": stats.get('pending_tickets', 0),
        "pending_consultations": stats.get('pending_consultations', 0),
        "pending_product_requests": stats.get('pending_product_requests', 0),
        "new_reviews": stats.get('new_reviews', 0),
        "priorities": stats.get('priorities', []) or [],
    }
    context["stats_summary"] = (
        f"کاربر جدید امروز: {context['today_new_users']} | "
        f"آنالیز امروز: {context['today_analyses']} | "
        f"سفارش فروشگاه امروز: {context['today_shop_orders']} | "
        f"درخواست فروش مو امروز: {context['today_hair_sales']} | "
        f"تیکت‌های در انتظار: {context['pending_tickets']} | "
        f"درخواست‌های مشاوره در انتظار: {context['pending_consultations']}"
    )
    context["priority_text"] = "\n".join(context["priorities"]) if context["priorities"] else "مورد بحرانی ثبت نشده است."
    context["task_hints"] = build_admin_task_hints(stats, role=role)
    return context



def _build_admin_consultant_prompt(role: str, context: dict, history_text: str, user_message: str) -> str:
    role_title = "سوپرادمین" if role == "super" else "ادمین"
    admin_name = context.get('admin_name', 'مدیر')
    guidance = (
        "می‌توانی درباره آمار، گزارش‌های امروز، کاربران جدید، سفارش‌ها، تیکت‌های باز، "
        "درخواست‌های مشاوره، فروش مو، سلامت عملیاتی و اولویت‌های رسیدگی پاسخ بده. "
        "اگر سوال کلی بود، جمع‌بندی مدیریتی بده و در پایان یک پیشنهاد اقدام بعدی هم مطرح کن."
    )
    extra = (
        "با او مثل یک همکار نزدیک، صمیمی، مهربان و خوش‌فکر حرف بزن و اگر سوالش مبهم بود، "
        "به‌جای رد خشک، از خودش توضیح دقیق‌تر بخواه."
        if role == "super" else
        "با او مثل یک دستیار مهربان و حرفه‌ای حرف بزن و تمرکزت روی گزارش و جمع‌بندی باشد."
    )
    hints = context.get('task_hints') or []
    hints_text = "\n".join(f"- {x}" for x in hints[:3]) if hints else "- فعلاً موردی برای اولویت‌بندی پیدا نشد"
    return (
        f"تو {get_display_name()} هستی و الان با {role_title} گیسو صحبت می‌کنی.\n"
        f"اسم طرف مقابل: {admin_name}\n"
        f"شماره: {context.get('admin_phone', '')}\n"
        f"سمت: {context.get('admin_role', role_title)}\n\n"
        f"خلاصه وضعیت امروز:\n{context.get('stats_summary', '')}\n\n"
        f"اولویت‌های مهم:\n{context.get('priority_text', '')}\n\n"
        f"تعداد تیکت‌های در انتظار: {context.get('pending_tickets', 0)}\n"
        f"تعداد درخواست‌های مشاوره در انتظار: {context.get('pending_consultations', 0)}\n"
        f"تعداد سفارش‌های در انتظار: {context.get('pending_shop_orders', 0)}\n"
        f"تعداد فروش مو در انتظار بررسی: {context.get('pending_hair_reviews', 0)}\n"
        f"محصولات درخواستی معطل: {context.get('pending_product_requests', 0)}\n\n"
        f"قابلیت‌های مورد انتظار:\n{guidance}\n\n"
        f"پیشنهادهای اولویت‌دار برای این نقش:\n{hints_text}\n\n"
        f"تاریخچه این جلسه:\n{history_text or 'شروع گفتگو'}\n\n"
        f"پیام جدید {admin_name}:\n{user_message}\n\n"
        "در جواب‌ها تا جای ممکن او را با اسمش خطاب کن. "
        f"{extra} "
        "اگر لازم بود پاسخ را در قالب: جمع‌بندی، نکات مهم، و پیشنهاد اقدام بعدی بنویس."
    )



def _user_asked_to_buy(text):
    """فقط وقتی کاربر صریحاً خرید/سفارش می‌خواهد کارت محصول در ربات برود."""
    t = (text or "").replace("ي", "ی").replace("ك", "ک")
    keys = (
        "خرید", "بخرم", "بخری", "بخر", "می‌خرم", "ميخرم", "میخرم",
        "سفارش", "لینک خرید", "چی بخرم", "میخوام بخرم", "می‌خوام بخرم",
    )
    return any(k in t for k in keys)


async def _send_consultant_product_cards(bot, chat_id, phone):
    """ارسال کارت محصول (آرایشی: عکس+دکمه) و آیتم خوراکی (متن+دکمه سفارش) برای مشاور ربات.

    Capability C — حداکثر ۳ کارت؛ اگر چیزی مرتبط نبود هیچ پیام اضافه‌ای نمی‌فرستد.
    هر خطا فقط لاگ می‌شود و به پاسخ متنی مشاور آسیب نمی‌زند.
    """
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        InlineKeyboardButton = None
        InlineKeyboardMarkup = None
    try:
        from giso.consultant_cards import build_cards_for_user
        from giso.recommendation_service import get_nutrition_recommendations
    except Exception:
        return
    try:
        site = _get_giso_site_url() or DEFAULT_SITE_BASE_URL
        cards = build_cards_for_user(phone)[:3]
        foods = get_nutrition_recommendations(phone, limit=3)
    except Exception as e:
        logger.warning(f"_send_consultant_product_cards build: {e}")
        return
    try:
        for c in cards:
            if not c.sell_url:
                continue
            kb = None
            if InlineKeyboardButton and InlineKeyboardMarkup:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("مشاهده و خرید ←", url=c.sell_url)
                ]])
            img = c.image_url or ""
            if img and not img.startswith("http"):
                img = site + img
            caption = f"{c.name}\n{_fa_num(c.price or 0)} تومان"
            if c.reason:
                caption += f"\n💡 {c.reason}"
            try:
                if InlineKeyboardButton and img:
                    await bot.send_photo(chat_id=chat_id, photo=img, caption=caption, reply_markup=kb)
                else:
                    await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb)
            except Exception as e:
                logger.debug(f"send product card photo failed: {e}")
                await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb)
        if foods:
            lines = ["📦 برای تکمیل برنامهٔ تغذیه‌ات، این‌ها کمک‌کننده‌اند:"]
            for i in foods:
                lines.append(f"• {i.name}{f' — {_fa_num(i.price or 0)} تومان' if i.price else ''}")
            kb = None
            if InlineKeyboardButton and InlineKeyboardMarkup:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 سفارش اقلام", url=(_get_giso_site_url() or DEFAULT_SITE_BASE_URL) + "/analysis/plan")
                ]])
            await bot.send_message(chat_id=chat_id, text="\n".join(lines), reply_markup=kb)
    except Exception as e:
        logger.warning(f"_send_consultant_product_cards: {e}")


async def _ask_consultant_bot(user_bale_id, phone, user_message, role="user", bot=None, chat_id=None):
    """فراخوانی هوشمند مشاور گیسو در ربات با نقش و context متناسب."""
    try:
        from giso.analysis import _load_prompt
    except Exception:
        _load_prompt = None

    role = (role or "user").strip().lower()
    if role not in ("user", "admin", "super"):
        role = "user"

    scope = get_context_scope(role, section="consultant_chat")
    if not scope.get("allowed"):
        return scope.get("message") or NO_ACCESS_MESSAGE

    history = _get_bot_chat_history(user_bale_id, limit=6)
    history_text = ""
    for msg in history:
        role_name = "کاربر" if msg.get('role') == 'user' else "مشاور"
        history_text += f"{role_name}: {msg.get('message','')}\n"

    if role in ("admin", "super"):
        context = _get_admin_ai_context(user_bale_id, phone, role)
        prompt = _build_admin_consultant_prompt(role, context, history_text, user_message)
    else:
        context = _get_user_full_context(phone, user_bale_id)
        if not scope.get("include_analysis"):
            context["last_analysis_info"] = "در این سطح، اطلاعات تحلیل در دسترس نیست"
            context["key_notes"] = "در این سطح، خلاصه گفتگو در دسترس نیست"
        if not scope.get("include_plan"):
            context["active_plan_info"] = "در این سطح، برنامه فعال در دسترس نیست"
            context["checklist_info"] = "در این سطح، چک‌لیست در دسترس نیست"
        if not scope.get("include_orders"):
            context["product_requests_info"] = "در این سطح، اطلاعات درخواست‌ها در دسترس نیست"
            context["hair_orders_info"] = "در این سطح، اطلاعات سفارش‌ها در دسترس نیست"
            context["shop_orders_info"] = "در این سطح، اطلاعات خریدها در دسترس نیست"

        template = _load_prompt("consultant_bot.txt") if _load_prompt else ""
        if not template:
            return PROVIDER_ERROR_MESSAGE
        prompt = template
        for key, val in context.items():
            prompt = prompt.replace('{' + key + '}', str(val))
        prompt = prompt.replace('{user_message}', user_message)
        if history_text.strip():
            prompt = prompt.replace(
                'پیام جدید کاربر:',
                f'گفتگوی این جلسه:\n{history_text}\n\nپیام جدید کاربر:'
            )

    credit_request_key = ""
    if role == "user":
        import uuid
        from giso.ai_credits import reserve_ai_credit
        credit_request_key = uuid.uuid4().hex
        credit_ok, credit_message, _credit = reserve_ai_credit(phone, credit_request_key, channel="bale_bot")
        if not credit_ok:
            return credit_message + "\n\n💰 برای شارژ کیف پول از سایت گیسو وارد بخش «کیف پول» شو."
    try:
        result = await chat_with_managed_ai(
            [{"role": "user", "content": prompt}],
            actor_key=f"bot:{user_bale_id}",
            role=role,
            channel="bot",
            section="consultant_chat",
            question_text=user_message,
            max_tokens=750 if role == "super" else 600,
        )
        if result and result.get("ok"):
            text = (result.get("text", "") or "").strip()
            if text:
                if (
                    role == "user"
                    and bot is not None
                    and chat_id is not None
                    and _user_asked_to_buy(user_message)
                ):
                    await _send_consultant_product_cards(bot, chat_id, phone)
                return text
        if credit_request_key:
            from giso.ai_credits import refund_ai_credit
            refund_ai_credit(phone, credit_request_key, channel="bale_bot")
        return (result or {}).get("text") or PROVIDER_ERROR_MESSAGE
    except Exception as e:
        if credit_request_key:
            from giso.ai_credits import refund_ai_credit
            refund_ai_credit(phone, credit_request_key, channel="bale_bot")
        logger.error(f"_ask_consultant_bot: {e}")

    return PROVIDER_ERROR_MESSAGE



def _ensure_support_tickets_table():
    """اطمینان از وجود جدول تیکت‌های پشتیبانی."""
    from giso.base import get_giso_db_conn
    try:
        conn = get_giso_db_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_bale_id TEXT NOT NULL,
                user_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                message TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                admin_reply TEXT DEFAULT '',
                admin_bale_id TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                replied_at TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"_ensure_support_tickets_table: {e}")



def _create_support_ticket(user_bale_id, user_name, phone, message):
    """ثبت تیکت جدید پشتیبانی."""
    from giso.base import get_giso_db_conn
    from datetime import datetime
    _ensure_support_tickets_table()
    try:
        conn = get_giso_db_conn()
        cur = conn.execute(
            "INSERT INTO giso_support_tickets "
            "(user_bale_id, user_name, phone, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(user_bale_id), user_name, phone,
             message, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        ticket_id = cur.lastrowid
        conn.commit()
        # مأموریت idempotent «ثبت تیکت پشتیبانی» — نیازمند حساب سایت (user_id از روی شماره)
        try:
            with get_giso_db_conn() as _tconn:
                from giso.base import normalize_phone as _nphone
                _trow = _tconn.execute(
                    "SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (_nphone(phone or ""),),
                ).fetchone()
            if _trow and _trow["id"]:
                from giso.wallet import complete_mission as _cm_sup
                _cm_sup(int(_trow["id"]), "support_ticket", event_key=f"ticket:{ticket_id}")
        except Exception as _sup_e:
            logger.debug(f"support_ticket mission failed: {_sup_e}")
        # مرکز اعلان: تیکت جدید پشتیبانی (زنگوله پنل + بله طبق تنظیمات دسته)
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("bot", "ticket", "تیکت جدید پشتیبانی",
                     f"تیکت #{ticket_id} — کاربر {user_name} ({phone or 'بدون شماره'}): {str(message or '')[:200]}",
                     source_type="support_ticket_new", source_id=int(ticket_id))
        except Exception:
            pass
        conn.close()
        return ticket_id
    except Exception as e:
        logger.error(f"_create_support_ticket: {e}")
        return None



def _get_bale_id_by_phone(phone):
    """پیدا کردن bale_id از روی شماره تلفن."""
    from giso.base import get_giso_db_conn
    try:
        if not phone:
            return None
        conn = get_giso_db_conn()
        row = conn.execute("SELECT bale_id FROM giso_users WHERE phone=?", (phone,)).fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception as e:
        logger.error(f"_get_bale_id_by_phone: {e}")
        return None



def _get_user_dashboard_info(phone, user_bale_id):
    """جمع‌آوری اطلاعات کاربر برای پیام ورود هوشمند."""
    from giso.base import get_giso_db_conn
    import json

    info = {
        'user_name': 'دوست عزیز',
        'has_account': False,
        'last_analysis': None,
        'active_plan': None,
        'checklist_progress': None,
        'pending_consultants': 0,
        'pending_products': 0,
        'pending_tickets': 0,
        'unread_replies': 0,
        'has_new_activity': False,
    }

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM giso_web_auth WHERE phone=?", (phone,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return info

        user_id = user[0]
        info['has_account'] = True
        info['user_name'] = (user[1] or '').strip() or 'دوست عزیز'

        cursor.execute(
            "SELECT id, type, created_at, ai_report_json, plan_json, checklist_progress "
            "FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        analysis = cursor.fetchone()

        if analysis:
            type_fa = 'مو' if analysis[1] == 'hair' else 'پوست'
            date_str = (analysis[2] or '').split('T')[0] if analysis[2] else ''
            info['last_analysis'] = {'id': analysis[0], 'type': type_fa, 'date': date_str}

            try:
                report = json.loads(analysis[3] or '{}')
                score = report.get('overall_score') or report.get('score')
                if score:
                    info['last_analysis']['score'] = score
            except Exception:
                pass

            if analysis[4]:
                try:
                    plan = json.loads(analysis[4])
                    weeks = plan.get('duration_weeks', 4) if isinstance(plan, dict) else 4
                    info['active_plan'] = {'weeks': weeks, 'current_week': 1}

                    if analysis[5]:
                        try:
                            progress = json.loads(analysis[5])
                            checklist_data = plan.get('checklist') if isinstance(plan, dict) else {}
                            if isinstance(checklist_data, dict):
                                total = len(checklist_data.get('weeks') or [])
                            elif isinstance(checklist_data, list):
                                total = len(checklist_data)
                            else:
                                total = 0
                            done = sum(1 for v in progress.values() if v) if isinstance(progress, dict) else 0
                            info['checklist_progress'] = {
                                'done': done, 'total': total,
                                'percent': int((done / total) * 100) if total > 0 else 0
                            }
                        except Exception:
                            pass
                except Exception:
                    pass

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM consultant_requests "
                "WHERE (user_id=? OR phone=?) AND status IN ('new', 'reviewing', 'chatting')",
                (user_id, phone)
            )
            info['pending_consultants'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM product_requests "
                "WHERE (user_id=? OR phone=?) AND status='pending'",
                (user_id, phone)
            )
            info['pending_products'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM giso_support_tickets "
                "WHERE user_bale_id=? AND status='replied'",
                (str(user_bale_id),)
            )
            info['unread_replies'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM giso_support_tickets "
                "WHERE user_bale_id=? AND status IN ('new', 'reviewing')",
                (str(user_bale_id),)
            )
            info['pending_tickets'] = cursor.fetchone()[0]
        except Exception:
            pass

        info['has_new_activity'] = (
            info['pending_consultants'] > 0 or
            info['pending_products'] > 0 or
            info['unread_replies'] > 0
        )

        conn.close()
    except Exception as e:
        logger.error(f"_get_user_dashboard_info: {e}")

    return info



def _build_smart_welcome_user(info, first_name):
    """ساخت پیام ورود هوشمند برای کاربر."""
    name = info.get('user_name') or first_name or 'دوست عزیز'
    parts = [f"🌸 سلام {name} عزیز!", ""]

    if info.get('has_account'):
        parts.append("📊 *خلاصه وضعیت شما:*")
        parts.append("━━━━━━━━━━━━━━━━━━━━━")
        la = info.get('last_analysis')
        if la:
            parts.append(f"🔬 آخرین تحلیل: {la['type']} ({la['date']})")
            if la.get('score'):
                parts.append(f"📊 امتیاز: {la['score']}/100")
        ap = info.get('active_plan')
        if ap:
            parts.append(f"📋 برنامه فعال: {ap['weeks']} هفته‌ای")
        cp = info.get('checklist_progress')
        if cp:
            parts.append(f"✅ چک‌لیست: {cp['done']}/{cp['total']} ({cp['percent']}%)")
        parts.append("━━━━━━━━━━━━━━━━━━━━━")

        if info.get('has_new_activity'):
            parts.append("")
            parts.append("📬 *چیزهای جدید:*")
            if info.get('unread_replies', 0) > 0:
                parts.append(f"🔴 {info['unread_replies']} پاسخ جدید از پشتیبانی")
            if info.get('pending_consultants', 0) > 0:
                parts.append(f"💬 {info['pending_consultants']} درخواست مشاوره در حال بررسی")
            if info.get('pending_products', 0) > 0:
                parts.append(f"🛒 {info['pending_products']} درخواست محصول در انتظار")
            if info.get('pending_tickets', 0) > 0:
                parts.append(f"🎫 {info['pending_tickets']} تیکت در انتظار پاسخ")
            parts.append("━━━━━━━━━━━━━━━━━━━━━")

        parts.append("")
        parts.append("از منوی پایین گزینه مورد نظرت رو انتخاب کن.")
    else:
        parts.append("به ربات گیسو خوش اومدی!")
        parts.append("")
        parts.append("اینجا می‌تونی:")
        parts.append("💇 فروش مو انجام بدی")
        parts.append("🔬 نتیجه تحلیل‌های سایت رو ببینی")
        parts.append("🛒 محصولات فروشگاه رو ببینی")
        parts.append("💬 با پشتیبانی صحبت کنی")
        parts.append("")
        parts.append("برای شروع تحلیل، به سایت گیسو برو:")
        parts.append(f"🌐 {_get_giso_site_url()}/analysis")

    return "\n".join(parts)



def _get_admin_dashboard_stats():
    """جمع‌آوری آمار برای پیام خوش‌آمد ادمین (از دیتابیس واقعی)."""
    from giso.base import get_giso_db_conn
    from datetime import datetime

    stats = {
        'today_analyses': 0, 'today_hair_sales': 0, 'today_shop_orders': 0,
        'today_new_users': 0,
        'pending_hair_reviews': 0, 'pending_shop_orders': 0, 'pending_tickets': 0,
        'pending_consultations': 0, 'pending_product_requests': 0,
        'new_reviews': 0,
        'priorities': [],
    }

    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (today,))
        stats['today_analyses'] = cursor.fetchone()[0]

        try:
            cursor.execute("SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?", (today,))
            stats['today_hair_sales'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM product_orders WHERE created_at >= ?", (today,))
            stats['today_shop_orders'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (today,))
            stats['today_new_users'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute("SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending', 'reviewing')")
            stats['pending_hair_reviews'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM product_orders WHERE status IN ('pending', 'processing')")
            stats['pending_shop_orders'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new', 'reviewing')")
            stats['pending_tickets'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new', 'reviewing')")
            stats['pending_consultations'] = cursor.fetchone()[0]
        except Exception:
            pass
        try:
            cursor.execute("SELECT COUNT(*) FROM product_requests WHERE status='pending'")
            stats['pending_product_requests'] = cursor.fetchone()[0]
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM analyses WHERE chat_rating > 0 AND created_at >= ?", (today,))
            stats['new_reviews'] = cursor.fetchone()[0]
        except Exception:
            pass

        if stats['pending_tickets'] > 0:
            stats['priorities'].append(f"🎫 {stats['pending_tickets']} تیکت پشتیبانی منتظر پاسخ")
        if stats['pending_consultations'] > 0:
            stats['priorities'].append(f"💬 {stats['pending_consultations']} درخواست مشاوره جدید")
        if stats['pending_hair_reviews'] > 0:
            stats['priorities'].append(f"💇 {stats['pending_hair_reviews']} درخواست فروش مو منتظر بررسی")
        if stats['pending_product_requests'] > 0:
            stats['priorities'].append(f"🛒 {stats['pending_product_requests']} درخواست محصول جدید")
        if stats['pending_shop_orders'] > 0:
            stats['priorities'].append(f"📦 {stats['pending_shop_orders']} سفارش فروشگاه در انتظار")

        conn.close()
    except Exception as e:
        logger.error(f"_get_admin_dashboard_stats: {e}")

    return stats



def _build_smart_welcome_admin(stats, first_name, is_super=False):
    """ساخت پیام ورود هوشمند برای ادمین."""
    role = "مدیر" if is_super else "ادمین"
    name = first_name or role
    parts = [f"👑 خوش‌آمدی {role} عزیز، {name}!", ""]
    parts.append("📊 *وضعیت امروز گیسو:*")
    parts.append("━━━━━━━━━━━━━━━━━━━━━━━")

    parts.append("🔬 *آنالیز:*")
    parts.append(f"  • جدید امروز: {_fa_num(stats['today_analyses'])}")
    parts.append("")

    if stats['today_hair_sales'] > 0 or stats['pending_hair_reviews'] > 0:
        parts.append("💇 *فروش مو:*")
        if stats['today_hair_sales'] > 0:
            parts.append(f"  • درخواست جدید امروز: {_fa_num(stats['today_hair_sales'])}")
        if stats['pending_hair_reviews'] > 0:
            parts.append(f"  • در انتظار بررسی: {_fa_num(stats['pending_hair_reviews'])}")
        parts.append("")

    if stats['today_shop_orders'] > 0 or stats['pending_shop_orders'] > 0:
        parts.append("🛒 *فروشگاه:*")
        if stats['today_shop_orders'] > 0:
            parts.append(f"  • سفارش جدید امروز: {_fa_num(stats['today_shop_orders'])}")
        if stats['pending_shop_orders'] > 0:
            parts.append(f"  • در انتظار ارسال: {_fa_num(stats['pending_shop_orders'])}")
        parts.append("")

    if stats['pending_consultations'] > 0 or stats['pending_tickets'] > 0:
        parts.append("💬 *مشاوره و پشتیبانی:*")
        if stats['pending_consultations'] > 0:
            parts.append(f"  • درخواست مشاوره جدید: {_fa_num(stats['pending_consultations'])} 🔴")
        if stats['pending_tickets'] > 0:
            parts.append(f"  • تیکت پشتیبانی: {_fa_num(stats['pending_tickets'])} 🔴")
        parts.append("")

    if stats['pending_product_requests'] > 0:
        parts.append(f"🛒 *محصولات درخواستی:* {_fa_num(stats['pending_product_requests'])} 🔴")
        parts.append("")

    if stats['new_reviews'] > 0:
        parts.append(f"⭐ *نظرات جدید امروز:* {_fa_num(stats['new_reviews'])}")
        parts.append("")

    if stats['today_new_users'] > 0:
        parts.append(f"👥 *کاربر جدید امروز:* {_fa_num(stats['today_new_users'])}")
        parts.append("")

    parts.append("━━━━━━━━━━━━━━━━━━━━━━━")

    if stats['priorities']:
        parts.append("")
        parts.append("🎯 *اولویت‌های شما:*")
        for i, priority in enumerate(stats['priorities'][:5], 1):
            parts.append(f"{i}. {priority}")
        parts.append("━━━━━━━━━━━━━━━━━━━━━━━")
    else:
        parts.append("")
        parts.append("✨ همه چیز مرتبه! خبر جدیدی نیست.")
        parts.append("━━━━━━━━━━━━━━━━━━━━━━━")

    parts.append("")
    parts.append("از منوی پایین گزینه مورد نظر رو انتخاب کن.")
    return "\n".join(parts)



def _get_chat_summaries(filter_type='all', limit=10):
    """دریافت خلاصه گفتگوهای مشاور با فیلتر زمانی."""
    from giso.base import get_giso_db_conn
    from datetime import datetime, timedelta
    import json

    summaries = []
    try:
        conn = get_giso_db_conn()
        cursor = conn.cursor()

        date_filter = ""
        params = []
        if filter_type == 'today':
            date_filter = "AND a.created_at >= ?"
            params.append(datetime.now().strftime('%Y-%m-%d'))
        elif filter_type == 'week':
            date_filter = "AND a.created_at >= ?"
            params.append((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        elif filter_type == 'month':
            date_filter = "AND a.created_at >= ?"
            params.append((datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

        query = f"""
            SELECT a.id, a.created_at, a.consultant_chat_history,
                   a.consultant_key_notes, a.chat_rating,
                   COALESCE(u.name, w.name, 'کاربر ناشناس') as user_name,
                   COALESCE(u.phone, w.phone, '') as phone
            FROM analyses a
            LEFT JOIN giso_web_auth u ON a.user_id = u.id
            LEFT JOIN giso_web_auth w ON a.phone = w.phone
            WHERE (a.consultant_chat_history IS NOT NULL
                   AND a.consultant_chat_history != ''
                   AND a.consultant_chat_history != '[]')
            {date_filter}
            ORDER BY a.id DESC
            LIMIT ?
        """
        params.append(limit)
        cursor.execute(query, params)

        for row in cursor.fetchall():
            date_str = 'نامشخص'
            if row[1]:
                try:
                    raw = row[1].split('T')[0] if 'T' in row[1] else row[1].split(' ')[0]
                    dt = datetime.strptime(raw, '%Y-%m-%d')
                    diff = (datetime.now() - dt).days
                    if diff == 0:
                        date_str = 'امروز'
                    elif diff == 1:
                        date_str = 'دیروز'
                    elif diff < 7:
                        date_str = f'{diff} روز پیش'
                    else:
                        date_str = raw
                except Exception:
                    date_str = row[1][:10]

            message_count = 0
            try:
                history = json.loads(row[2] or '[]')
                if isinstance(history, list):
                    message_count = len(history)
            except Exception:
                pass

            summaries.append({
                'id': row[0], 'date': date_str,
                'message_count': message_count,
                'summary': row[3] or '',
                'rating': row[4],
                'user_name': row[5] or 'کاربر ناشناس',
                'phone': row[6] or '',
            })

        conn.close()
    except Exception as e:
        logger.error(f"_get_chat_summaries: {e}")

    return summaries

