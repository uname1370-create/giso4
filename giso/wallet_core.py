# -*- coding: utf-8 -*-
"""
giso/wallet_core.py — ثابت‌ها، تنظیمات مالی و مجوز سوپرادمین مالی کیف پول (Phase 2, Unit U5)
استخراج‌شده از giso/wallet.py بدون تغییر رفتار؛ همه نام‌ها در giso.wallet re-export می‌شوند.
"""
# -*- coding: utf-8 -*-
"""دفترکل واحد کیف پول گیسو، مأموریت‌ها، شارژ و checkout اتمیک.

قاعده مانده:
- cash برای خرید داخل سایت و تسویه قابل استفاده است.
- spend فقط برای خرید داخل سایت قابل استفاده است.
- همه credit/debitهای posted در یک دفترکل محاسبه می‌شوند؛ تغییر status به ``used``
  باعث ناپدیدشدن debit از محاسبه نمی‌شود.
"""
import logging
import re
import sqlite3
from datetime import datetime, timedelta

from giso.base import get_giso_db_conn, normalize_phone
from giso.money import format_toman

logger = logging.getLogger("giso_wallet")
POSTED_STATUSES = ("available", "used", "pending", "paid")
SCOPES = ("cash", "spend")
MISSION_EVENTS = {
    "registration": ("ثبت‌نام موفق", 10),
    "profile_complete": ("تکمیل پروفایل", 20),
    "first_purchase": ("اولین خرید موفق فروشگاه", 30),
    "shop_order": ("ثبت سفارش فروشگاه", 40),
    "hair_request": ("ثبت درخواست خرید مو", 50),
    "hair_completed": ("تکمیل خرید مو", 60),
    "analysis_complete": ("اتمام آنالیز هوشمند", 70),
    "marketplace_listing": ("ثبت آگهی بازارچه مو", 80),
    "marketplace_offer": ("ثبت پیشنهاد بازارچه مو", 90),
    "support_ticket": ("ثبت تیکت پشتیبانی", 100),
    "review_submit": ("ثبت نظر و امتیاز", 110),
    "beauty_center_published": ("انتشار اولین مرکز زیبایی", 120),
    "product_explorer": ("مشاهده واقعی محصولات", 130),
    "bale_connected": ("اتصال معتبر حساب بله", 140),
    "bug_report_approved": ("گزارش باگ تأییدشده", 150),
}
SERVICE_FEE_KEYS = {
    "marketplace": ("wallet_fee_marketplace", 0),
    "analysis": ("wallet_fee_analysis", 0),
    "hair": ("wallet_fee_hair", 0),
    "shop": ("wallet_fee_shop", 0),
}
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

SETTINGS_DEFAULTS = {
    "wallet_topup_enabled": "1",
    "wallet_withdrawal_enabled": "1",
    "wallet_min_topup": "10000",
    "wallet_min_withdrawal": "100000",
    "wallet_card_holder": "",
    "wallet_topup_method": "both",
    "wallet_card_number": "",
    "wallet_sheba": "",
    "wallet_invoice_seller_name": "گیسو صادقی",
    "wallet_invoice_seller_phone": "",
    "wallet_invoice_seller_address": "مشهد",
}


class WalletCheckoutError(RuntimeError):
    """خطای قابل نمایش checkout که قبل از commit کل تراکنش را rollback می‌کند."""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _setting(key: str) -> str:
    default = SETTINGS_DEFAULTS.get(key, "")
    try:
        from giso_admin import get_giso_config
        value = get_giso_config(key, default)
        # سازگاری با حداقل تسویه قدیمی بدون وابستگی دوباره به referral.
        if key == "wallet_min_withdrawal" and (value is None or str(value).strip() == ""):
            value = get_giso_config("referral_min_withdrawal", default)
        return str(value if value is not None else default).strip()
    except Exception:
        return default


def _bool_setting(key: str) -> bool:
    return _setting(key).lower() in ("1", "true", "on", "yes")


def _positive_int(value, default=0) -> int:
    try:
        return max(0, int(str(value or "0").translate(_DIGIT_MAP)))
    except (TypeError, ValueError):
        return max(0, int(default or 0))


def get_financial_settings() -> dict:
    return {
        "topup_enabled": _bool_setting("wallet_topup_enabled"),
        "withdrawal_enabled": _bool_setting("wallet_withdrawal_enabled"),
        "min_topup": _positive_int(_setting("wallet_min_topup"), 10000),
        "min_withdrawal": _positive_int(_setting("wallet_min_withdrawal"), 100000),
        "card_holder": _setting("wallet_card_holder")[:150],
        "topup_method": _setting("wallet_topup_method") if _setting("wallet_topup_method") in ("receipt", "bale", "both") else "both",
        "card_number": re.sub(r"\D", "", _setting("wallet_card_number"))[:16],
        "sheba": _setting("wallet_sheba").upper()[:26],
        "invoice_seller_name": _setting("wallet_invoice_seller_name")[:160] or "گیسو صادقی",
        "invoice_seller_phone": _setting("wallet_invoice_seller_phone")[:30],
        "invoice_seller_address": _setting("wallet_invoice_seller_address")[:500] or "مشهد",
        "initial_spend_credit": _positive_int(_setting("wallet_initial_spend_credit"), 0),
    }


def is_financial_superadmin() -> bool:
    """مجوز صریح عملیات مالی؛ permission ادمین عادی هرگز کافی نیست."""
    try:
        from flask_login import current_user
        from giso.config import is_super_admin
        if not getattr(current_user, "is_authenticated", False):
            return False
        phone = normalize_phone(getattr(current_user, "phone", "") or "")
        return bool(phone and is_super_admin(phone=phone))
    except Exception:
        return False


def save_financial_settings(values: dict) -> tuple:
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند تنظیمات مالی را تغییر دهد."
    try:
        from giso_admin import set_giso_config
        min_topup = _positive_int(values.get("min_topup"), 10000)
        min_withdrawal = _positive_int(values.get("min_withdrawal"), 100000)
        holder = str(values.get("card_holder") or "").strip()[:150]
        card = re.sub(r"\D", "", str(values.get("card_number") or ""))[:16]
        sheba = str(values.get("sheba") or "").strip().upper().replace(" ", "")[:26]
        invoice_seller_name = str(values.get("invoice_seller_name") or "گیسو صادقی").strip()[:160]
        invoice_seller_phone = str(values.get("invoice_seller_phone") or "").strip()[:30]
        invoice_seller_address = str(values.get("invoice_seller_address") or "مشهد").strip()[:500]
        if card and len(card) != 16:
            return False, "شماره کارت باید ۱۶ رقم باشد."
        if sheba and not re.fullmatch(r"IR\d{24}", sheba):
            return False, "شماره شبا باید با IR شروع شود و ۲۶ کاراکتر باشد."
        topup_method = str(values.get("topup_method") or "").strip().lower()
        if topup_method and topup_method not in ("receipt", "bale", "both"):
            return False, "روش افزایش موجودی نامعتبر است."
        pairs = {
            "wallet_topup_enabled": "1" if values.get("topup_enabled") else "0",
            "wallet_withdrawal_enabled": "1" if values.get("withdrawal_enabled") else "0",
            "wallet_min_topup": str(min_topup),
            "wallet_initial_spend_credit": str(_positive_int(values.get("initial_spend_credit"), 0)),
            **({"wallet_topup_method": topup_method} if topup_method else {}),
            "wallet_min_withdrawal": str(min_withdrawal),
            "wallet_card_holder": holder,
            "wallet_card_number": card,
            "wallet_sheba": sheba,
            "wallet_invoice_seller_name": invoice_seller_name or "گیسو صادقی",
            "wallet_invoice_seller_phone": invoice_seller_phone,
            "wallet_invoice_seller_address": invoice_seller_address or "مشهد",
        }
        for key, value in pairs.items():
            set_giso_config(key, value)
        return True, "تنظیمات مالی ذخیره شد."
    except Exception as exc:
        logger.exception("save financial settings failed: %s", exc)
        return False, "ذخیره تنظیمات مالی ناموفق بود."




# ═══════════ موتور رتبه (فقط خواندنی) — از برنچ قدیم، بدون تغییر رفتار ═══════════
# آستانه‌ها و اعتبار روزانه از giso_config خوانده می‌شوند؛ مقادیر زیر فقط fallback ایمن
# هستند و هیچ مقداری برای محاسبه‌ی اجباری hardcode نیست (سوپرادمین می‌تواند عوض کند).
_RANK_LEVELS_DEFAULT = (
    # (level, name, emoji, points_threshold_key, daily_credit_key, default_threshold, default_daily)
    (1, "الماسی", "👑", "rank_threshold_1", "rank_daily_credit_1", 2000, 100000),
    (2, "طلایی", "🥇", "rank_threshold_2", "rank_daily_credit_2", 500, 50000),
    (3, "نقره‌ای", "🥈", "rank_threshold_3", "rank_daily_credit_3", 100, 30000),
    (4, "برنزی", "🥉", "rank_threshold_4", "rank_daily_credit_4", 0, 10000),
)


def _rank_int_setting(key: str, default: int) -> int:
    """خواندن یک تنظیم عددی رتبه؛ اگر کلید نبود/خالی بود، مقدار پیش‌فرض برمی‌گردد (نه ۰)."""
    raw = _setting(key)
    if raw is None or str(raw).strip().lower() in ("", "none", "null"):
        return int(default)
    return _positive_int(raw, default)


def _rank_levels_config() -> list:
    """سطح‌های رتبه با آستانه/اعتبار روزانه از تنظیمات؛ مرتب‌شده از بیشترین به کمترین امتیاز."""
    try:
        levels = []
        for level, name, emoji, th_key, credit_key, def_th, def_credit in _RANK_LEVELS_DEFAULT:
            th = _rank_int_setting(th_key, def_th)
            credit = _rank_int_setting(credit_key, def_credit)
            levels.append({"level": level, "name": name, "emoji": emoji,
                           "threshold": th, "daily_credit": credit})
        levels.sort(key=lambda x: x["threshold"], reverse=True)
        return levels
    except Exception as exc:  # pragma: no cover - مسیر ایمن
        logger.warning("rank config failed: %s", exc)
        return [{"level": l, "name": n, "emoji": e, "threshold": t, "daily_credit": c}
                for l, n, e, _, _, t, c in sorted(_RANK_LEVELS_DEFAULT, key=lambda x: x[5], reverse=True)]


# کلید فعال‌سازی واریز روزانه‌ی اعتبار مصرفی بر اساس رتبه (مرحله ۴/۵).
RANK_DAILY_CREDIT_ENABLED_KEY = "rank_daily_credit_enabled"


def rank_daily_credit_enabled() -> bool:
    """آیا واریز روزانه‌ی اعتبار رتبه فعال است؟ پیش‌فرض فعال (فقط از giso_config)."""
    try:
        return _bool_setting(RANK_DAILY_CREDIT_ENABLED_KEY) if _setting(RANK_DAILY_CREDIT_ENABLED_KEY) else True
    except Exception:
        return True


def get_rank_settings() -> dict:
    """تنظیمات رتبه‌ها برای پنل سوپرادمین: سطوح به‌ترتیب level (۱=الماس … ۴=برنز)."""
    try:
        by_level = {lv["level"]: lv for lv in _rank_levels_config()}
        levels = []
        for level, name, emoji, th_key, credit_key, def_th, def_credit in _RANK_LEVELS_DEFAULT:
            lv = by_level.get(level) or {"threshold": def_th, "daily_credit": def_credit}
            levels.append({
                "level": level, "name": name, "emoji": emoji,
                "threshold": int(lv.get("threshold", def_th)),
                "daily_credit": int(lv.get("daily_credit", def_credit)),
            })
        return {"daily_credit_enabled": rank_daily_credit_enabled(), "levels": levels}
    except Exception as exc:
        logger.warning("get_rank_settings failed: %s", exc)
        return {"daily_credit_enabled": True, "levels": [
            {"level": l, "name": n, "emoji": e, "threshold": t, "daily_credit": c}
            for l, n, e, _, _, t, c in _RANK_LEVELS_DEFAULT]}


def save_rank_settings(values: dict) -> tuple:
    """ذخیره‌ی آستانه‌ها، اعتبار روزانه‌ی هر رتبه و کلید فعال‌سازی — فقط سوپرادمین مالی.

    اعتبارسنجی: آستانه‌ها باید از الماس به برنز اکیداً نزولی باشند (آستانه‌ی برنز می‌تواند ۰
    باشد) تا موتور رتبه همیشه یک سطح یکتا برگرداند.
    """
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند تنظیمات رتبه‌ها را تغییر دهد."
    try:
        from giso_admin import set_giso_config
        parsed = {}
        for level, name, emoji, th_key, credit_key, def_th, def_credit in _RANK_LEVELS_DEFAULT:
            th = _positive_int(values.get(f"threshold_{level}"), def_th)
            credit = _positive_int(values.get(f"daily_credit_{level}"), def_credit)
            parsed[level] = {"th_key": th_key, "credit_key": credit_key,
                             "threshold": th, "daily_credit": credit, "name": name}
        # اعتبارسنجی نزولی‌بودن آستانه‌ها: level 1 (الماس) بالاترین … level 4 (برنز) پایین‌ترین.
        order = sorted(parsed.keys())  # 1,2,3,4
        for a, b in zip(order, order[1:]):
            if parsed[a]["threshold"] <= parsed[b]["threshold"]:
                return False, (f"آستانه‌ی رتبه‌ی {parsed[a]['name']} باید بزرگ‌تر از "
                               f"رتبه‌ی {parsed[b]['name']} باشد.")
        enabled = bool(values.get("daily_credit_enabled"))
        pairs = {RANK_DAILY_CREDIT_ENABLED_KEY: "1" if enabled else "0"}
        for level in order:
            p = parsed[level]
            pairs[p["th_key"]] = str(p["threshold"])
            pairs[p["credit_key"]] = str(p["daily_credit"])
        for key, value in pairs.items():
            set_giso_config(key, value)
        return True, "تنظیمات رتبه‌ها ذخیره شد."
    except Exception as exc:
        logger.exception("save rank settings failed: %s", exc)
        return False, "ذخیره تنظیمات رتبه‌ها ناموفق بود."


def _resolve_site_user_id(phone: str, conn=None) -> int | None:
    """رسیدن به شناسه‌ی حساب سایت از روی شماره موبایل نرمال‌شده (منبع امتیاز)."""
    try:
        np = normalize_phone(phone or "")
        if not np:
            return None
        owns = conn is None
        c = conn if conn is not None else get_giso_db_conn()
        try:
            row = c.execute("SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (np,)).fetchone()
            return int(row[0]) if row and row[0] is not None else None
        finally:
            if owns:
                c.close()
    except Exception as exc:
        logger.warning("resolve user_id failed: %s", exc)
        return None


def _user_total_points(user_id: int, conn) -> int:
    """مجموع امتیاز کاربر از مأموریت‌های تکمیل‌شده.

    امتیاز از ``wallet_missions.reward_points`` خوانده می‌شود (ستون مرحله ۲)؛ اگر برای
    مأموریتی هنوز مقدار نداشته باشد (داده‌ی قدیمی)، ۰ لحاظ می‌شود تا محاسبه فقط بر اساس
    دیتای واقعی باشد.
    """
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(m.reward_points,0)),0) "
            "FROM wallet_mission_completions c "
            "JOIN wallet_missions m ON m.id=c.mission_id "
            "WHERE c.user_id=? AND COALESCE(m.is_deleted,0)=0",
            (int(user_id),),
        ).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as exc:
        logger.warning("user points failed: %s", exc)
        return 0


def get_user_rank(phone: str) -> dict:
    """محاسبه‌ی رتبه‌ی کاربر (فقط خواندنی).

    خروجی شامل rank(level 1..4)، name، emoji، score، daily_credit، next_rank_score و
    next_rank_name است. آستانه‌ها از giso_config با fallback تأمین می‌شوند.
    """
    empty = {"rank": 4, "name": "برنزی", "emoji": "🥉", "score": 0,
             "daily_credit": 0, "next_rank_score": None, "next_rank_name": None,
             "user_id": None}
    try:
        levels = _rank_levels_config()
        with get_giso_db_conn() as conn:
            uid = _resolve_site_user_id(phone, conn)
            if uid is None:
                # کاربر بدون حساب سایت: پایین‌ترین رتبه با همان پیش‌فرض‌ها
                base = levels[-1]
                return {**empty, "rank": base["level"], "name": base["name"],
                        "emoji": base["emoji"], "daily_credit": base["daily_credit"],
                        "next_rank_score": _next_threshold(levels, base["level"])}
            score = _user_total_points(uid, conn)
        current = levels[-1]  # پایین‌ترین
        for lv in levels:  # مرتب از بیشترین آستانه به کمترین
            if score >= lv["threshold"]:
                current = lv
                break
        next_th = _next_threshold(levels, current["level"])
        next_name = None
        if next_th is not None:
            for lv in levels:
                if lv["threshold"] == next_th:
                    next_name = lv["name"]
                    break
        return {
            "rank": current["level"], "name": current["name"], "emoji": current["emoji"],
            "score": score, "daily_credit": current["daily_credit"],
            "next_rank_score": next_th, "next_rank_name": next_name, "user_id": uid,
        }
    except Exception as exc:
        logger.warning("get_user_rank failed: %s", exc)
        return empty


def _next_threshold(levels: list, current_level: int):
    """آستانه‌ی رتبه‌ی بعدیِ بالاتر (level عددی کوچک‌تر = بالاتر). برای بالاترین رتبه None."""
    try:
        higher = [lv["threshold"] for lv in levels if lv["level"] < current_level]
        return min(higher) if higher else None
    except Exception:
        return None


def get_weekly_leaderboard(limit: int = 10) -> list:
    """۱۰ کاربر برترِ هفته بر اساس امتیاز مأموریت‌های تکمیل‌شده (فقط خواندنی).

    ابتدای هفته = شنبه ۰۰:۰۰ (تقویم محلی). خروجی لیست دیکشنری با rank, name, score.
    """
    try:
        limit = max(1, min(50, int(limit or 10)))
        now = datetime.now()
        # weekday(): دوشنبه=0 ... شنبه=5 (پایتون). ابتدای هفته شنبه است.
        days_since_saturday = (now.weekday() - 5) % 7
        start = (now - timedelta(days=days_since_saturday)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        start_str = start.strftime("%Y-%m-%d %H:%M:%S")
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT c.user_id AS user_id, "
                "COALESCE(MAX(a.name),'') AS name, "
                "COALESCE(SUM(COALESCE(m.reward_points,0)),0) AS score "
                "FROM wallet_mission_completions c "
                "JOIN wallet_missions m ON m.id=c.mission_id AND COALESCE(m.is_deleted,0)=0 "
                "LEFT JOIN giso_web_auth a ON a.id=c.user_id "
                "WHERE c.completed_at>=? "
                "GROUP BY c.user_id ORDER BY score DESC LIMIT ?",
                (start_str, limit),
            ).fetchall()
        out = []
        for i, r in enumerate(rows, start=1):
            out.append({"rank": i, "user_id": int(r["user_id"]),
                        "name": str(r["name"] or f"کاربر #{r['user_id']}")[:40],
                        "score": int(r["score"] or 0)})
        return out
    except Exception as exc:
        logger.warning("weekly leaderboard failed: %s", exc)
        return []


# ═══════════ اعتبار خدمات پولی (آنالیز/گزارش سریع/مشاوره) — سبک و ضدتکرار ═══════════
# سرویس‌های قابل‌شارژ از کیف پول (spend → cash). پیش‌فرض همه غیرفعال (هزینه ۰ = رایگان).
SERVICE_CREDIT_DEFS = (
    # key, label, config-enabled key, config-amount key, default amount
    ("analysis", "🔬 آنالیز هوشمند (هر تحلیل کامل)", "svc_credit_analysis_enabled", "svc_credit_analysis_fee", 0),
    ("quick_report", "⚡ گزارش سریع/کامل", "svc_credit_quick_report_enabled", "svc_credit_quick_report_fee", 0),
    ("consultation", "💬 مشاوره آنلاین (هر جلسه/گزارش)", "svc_credit_consultation_enabled", "svc_credit_consultation_fee", 0),
)


def _svc_setting_bool(key: str, default: bool = False) -> bool:
    try:
        raw = _setting(key)
        if raw is None or str(raw).strip().lower() in ("", "none", "null"):
            return default
        return str(raw).strip().lower() in ("1", "true", "on", "yes")
    except Exception:
        return default


def get_service_credit_settings() -> dict:
    """تنظیمات اعتبار خدمات برای پنل سوپرادمین (پیش‌فرض همه غیرفعال/رایگان)."""
    items = []
    for key, label, en_key, fee_key, def_fee in SERVICE_CREDIT_DEFS:
        items.append({
            "key": key, "label": label,
            "enabled": _svc_setting_bool(en_key, False),
            "fee": _rank_int_setting(fee_key, def_fee),
        })
    return {"items": items}


def save_service_credit_settings(values: dict) -> tuple:
    """ذخیره‌ی فعال/غیرفعال و هزینه‌ی هر خدمت — فقط سوپرادمین مالی."""
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند تنظیمات اعتبار خدمات را تغییر دهد."
    try:
        from giso_admin import set_giso_config
        pairs = {}
        for key, label, en_key, fee_key, def_fee in SERVICE_CREDIT_DEFS:
            fee = _positive_int(values.get(f"fee_{key}"), def_fee)
            enabled = bool(values.get(f"enabled_{key}")) and fee > 0
            pairs[en_key] = "1" if enabled else "0"
            pairs[fee_key] = str(fee)
        for k, v in pairs.items():
            set_giso_config(k, v)
        return True, "تنظیمات اعتبار خدمات ذخیره شد."
    except Exception as exc:
        logger.exception("save service credit settings failed: %s", exc)
        return False, "ذخیره تنظیمات اعتبار خدمات ناموفق بود."


def _service_credit_rule(service: str) -> dict | None:
    for key, label, en_key, fee_key, def_fee in SERVICE_CREDIT_DEFS:
        if key == str(service or "").strip().lower():
            return {"key": key, "label": label, "en_key": en_key, "fee_key": fee_key,
                    "enabled": _svc_setting_bool(en_key, False),
                    "fee": _rank_int_setting(fee_key, def_fee)}
    return None


def charge_service_credit(user_id: int, service: str, ref_id, reason: str = "") -> dict:
    """کسر اتمیک هزینه‌ی یک خدمت از کیف پول (اول spend سپس cash).

    - اگر خدمت غیرفعال یا هزینه صفر باشد: کسر انجام نمی‌شود و ok=True با charged=False.
    - اگر اعتبار کافی نباشد: هیچ کسری ثبت نمی‌شود و ok=False (سرویس باید بلاک شود).
    - کلید یکتایی به‌صورت ``service_<service>:<ref_id>`` ساخته می‌شود تا با retry دوبار
      کسر نشود و گزارش بتواند شمارش تکرار هر خدمت را استخراج کند.
    خروجی: {ok, charged, fee, reason(short_fa), balance_spend, balance_cash, missing}.
    """
    empty = {"ok": False, "charged": False, "fee": 0, "reason": "",
             "balance_spend": 0, "balance_cash": 0, "missing": 0}
    try:
        rule = _service_credit_rule(service)
        if rule is None:
            return {**empty, "ok": True, "charged": False, "reason": "خدمت پولی تعریف‌نشده؛ بدون کسر."}
        fee = max(0, int(rule["fee"] or 0))
        if not rule["enabled"] or fee <= 0:
            return {**empty, "ok": True, "charged": False, "fee": fee,
                    "reason": "این خدمت رایگان است."}
        ref = str(ref_id or "").strip()[:80]
        if not ref:
            logger.warning("charge_service_credit: شناسه یکپارچه خدمت خالی است (service=%s user=%s)", service, user_id)
            return {**empty, "ok": False, "reason": "شناسه یکپارچه خدمت معتبر نیست."}
        idem = f"service_{rule['key']}:{ref}"[:120]
        conn = get_giso_db_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            # ضدتکرار: اگر همین خدمت قبلاً برای این رویداد کسر شده، دوباره نگیر.
            dup = conn.execute(
                "SELECT 1 FROM wallet_transactions WHERE idempotency_key=? LIMIT 1", (idem,)
            ).fetchone()
            if dup:
                conn.rollback()
                b = get_wallet_balances(int(user_id), conn=conn)
                return {"ok": True, "charged": False, "fee": fee,
                        "reason": "هزینه این خدمت قبلاً کسر شده است.",
                        "balance_spend": b["spend"], "balance_cash": b["cash"], "missing": 0}
            b = get_wallet_balances(int(user_id), conn=conn)
            spend, cash = b["spend"], b["cash"]
            if spend + cash < fee:
                conn.rollback()
                return {"ok": False, "charged": False, "fee": fee,
                        "reason": "اعتبار کافی نیست؛ لطفاً کیف پول خود را شارژ کنید.",
                        "balance_spend": spend, "balance_cash": cash, "missing": fee - (spend + cash)}
            now = _now()
            # اول spend سپس cash. ردیف اول (هر scope که باشد) همیشه کلید پایه idem را
            # می‌گیرد تا لنگر ضدتکرار و شمارش گزارش همیشه وجود داشته باشد؛ ردیف دوم (در
            # حالت تقسیم بین دو کیف) پسوند :cash می‌گیرد.
            spend_part = min(spend, fee)
            cash_part = fee - spend_part
            parts = []
            if spend_part > 0:
                parts.append(("spend", spend_part, ""))
            if cash_part > 0:
                parts.append(("cash", cash_part, " (بخش نقدی)"))
            for idx, (scope, part_amt, suffix) in enumerate(parts):
                key = idem if idx == 0 else idem + ":cash"
                conn.execute(
                    "INSERT INTO wallet_transactions "
                    "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                    "VALUES (?, 'service_charge', ?, 'used', 'service_credit', 0, ?, ?, ?, ?)",
                    (int(user_id), -part_amt, scope, key,
                     f"هزینه {rule['label']}{suffix} — {str(reason or '').strip()[:300]}", now),
                )
            conn.commit()
            nb = get_wallet_balances(int(user_id), conn=conn)
            return {"ok": True, "charged": True, "fee": fee,
                    "reason": "هزینه خدمت از کیف پول کسر شد.",
                    "balance_spend": nb["spend"], "balance_cash": nb["cash"], "missing": 0}
        finally:
            conn.close()
    except sqlite3.IntegrityError:
        # idempotency_key تکراری = همین رویداد قبلاً کسر شده
        return {**empty, "ok": True, "charged": False, "fee": _positive_int(rule.get("fee", 0) if rule else 0),
                "reason": "هزینه این خدمت قبلاً کسر شده است."}
    except Exception as exc:
        logger.exception("charge service credit failed: %s", exc)
        return {**empty, "reason": "کسر هزینه خدمت ناموفق بود."}


def service_charge_report(limit: int = 200) -> dict:
    """گزارش کسرهای خدمات: شمارش تکرار هر خدمت + فهرست تراکنش‌ها."""
    try:
        limit = max(1, min(500, int(limit or 200)))
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT t.id,t.user_id,t.amount,t.balance_scope,t.description,t.created_at,"
                "COALESCE(u.name,'') name, COALESCE(u.phone,'') phone "
                "FROM wallet_transactions t LEFT JOIN giso_web_auth u ON u.id=t.user_id "
                "WHERE t.kind='service_charge' ORDER BY t.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            # شمارش تکرار بر اساس خدمت: کلیدها service_<key>:<id> و ردیف نقدی ...:cash.
            # times = تعداد رویداد (فقط ردیف اصلی spend/کل، نه :cash)؛ total = مجموع هر دو بخش.
            cnt_rows = conn.execute(
                "SELECT SUBSTR(idempotency_key,1,INSTR(idempotency_key,':')-1) AS svc, "
                "SUM(CASE WHEN idempotency_key NOT LIKE '%:cash' THEN 1 ELSE 0 END) AS times, "
                "COALESCE(SUM(-amount),0) AS total "
                "FROM wallet_transactions WHERE kind='service_charge' AND idempotency_key LIKE 'service_%:%' "
                "GROUP BY svc"
            ).fetchall()
        counts = []
        labels = {f"service_{k}": lbl for k, lbl, *_ in SERVICE_CREDIT_DEFS}
        svc_key = {f"service_{k}": k for k, *_ in SERVICE_CREDIT_DEFS}
        for r in cnt_rows:
            svc = r["svc"] if "svc" in r.keys() else r[0]
            times = r["times"] if "times" in r.keys() else r[1]
            total = r["total"] if "total" in r.keys() else r[2]
            counts.append({"service": svc_key.get(svc, svc), "label": labels.get(svc, svc),
                           "times": int(times or 0), "total": int(total or 0)})
        items = [dict(r) for r in rows]
        return {"items": items, "counts": counts}
    except Exception as exc:
        logger.warning("service charge report failed: %s", exc)
        return {"items": [], "counts": []}


def grant_initial_spend_credit(user_id: int) -> bool:
    """اعطای یک‌بارهٔ «اعتبار مصرفی اولیهٔ رایگان» (تنظیم مالی سوپرادمین) — ایدمپوتنت per کاربر."""
    amount = _positive_int(_setting("wallet_initial_spend_credit"), 0)
    if amount <= 0 or not user_id:
        return False
    key = f"initial_spend_{int(user_id)}"
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM wallet_transactions WHERE idempotency_key=?", (key,)).fetchone():
            conn.rollback()
            return False
        conn.execute(
            "INSERT INTO wallet_transactions(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (int(user_id), "credit", int(amount), "available", "initial_credit", int(user_id),
             "spend", key, "اعتبار مصرفی اولیهٔ رایگان (تنظیمات مالی)", _now()))
        conn.commit()
        return True
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("initial spend credit grant failed: %s", exc)
        return False


# ═══════════ هسته‌ی مانده/تراکنش (انتقال از wallet.py برای رعایت سقف ۷۲۳) ═══════════
def _balance_rows(conn, user_id: int) -> dict:
    marks = ",".join("?" for _ in POSTED_STATUSES)
    rows = conn.execute(
        "SELECT COALESCE(NULLIF(balance_scope,''),'cash') AS scope, COALESCE(SUM(amount),0) AS amount "
        "FROM wallet_transactions WHERE user_id=? AND status IN (%s) "
        "GROUP BY COALESCE(NULLIF(balance_scope,''),'cash')" % marks,
        (int(user_id),) + POSTED_STATUSES,
    ).fetchall()
    values = {"cash": 0, "spend": 0}
    for row in rows:
        scope = row["scope"] if row["scope"] in SCOPES else "cash"
        values[scope] += int(row["amount"] or 0)
    return values


def get_wallet_balances(user_id: int, conn=None) -> dict:
    """مانده صحیح دفترکل؛ debitهای used/pending/paid نیز از مانده کم می‌شوند."""
    owns = conn is None
    try:
        if owns:
            conn = get_giso_db_conn()
        raw = _balance_rows(conn, int(user_id))
        cash = max(0, int(raw["cash"]))
        spend = max(0, int(raw["spend"]))
        return {
            "cash": cash,
            "spend": spend,
            "usable": cash + spend,
            "settleable": cash,
            "balance": cash + spend,  # قرارداد سازگاری برای کارت‌های قدیمی
            "cash_raw": int(raw["cash"]),
            "spend_raw": int(raw["spend"]),
        }
    except Exception as exc:
        logger.warning("wallet balance failed for %s: %s", user_id, exc)
        return {"cash": 0, "spend": 0, "usable": 0, "settleable": 0,
                "balance": 0, "cash_raw": 0, "spend_raw": 0}
    finally:
        if owns and conn is not None:
            conn.close()


def get_user_transactions(user_id: int, limit: int = 50) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id,kind,amount,status,source_type,source_id,"
                "COALESCE(NULLIF(balance_scope,''),'cash') AS balance_scope,description,created_at "
                "FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (int(user_id), max(1, min(200, int(limit or 50)))),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("wallet transactions failed: %s", exc)
        return []


def get_admin_financial_summary() -> dict:
    try:
        with get_giso_db_conn() as conn:
            pending_topups = conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(amount),0) FROM wallet_topup_requests WHERE status='pending'"
            ).fetchone()
            pending_withdrawals = conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(amount),0) FROM withdrawal_requests WHERE status='pending'"
            ).fetchone()
            cash_total = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
                "WHERE COALESCE(NULLIF(balance_scope,''),'cash')='cash' AND status IN ('available','used','pending','paid')"
            ).fetchone()[0]
            spend_total = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
                "WHERE balance_scope='spend' AND status IN ('available','used','pending','paid')"
            ).fetchone()[0]
        return {
            "pending_topups": int(pending_topups[0] or 0),
            "pending_topup_amount": int(pending_topups[1] or 0),
            "pending_withdrawals": int(pending_withdrawals[0] or 0),
            "pending_withdrawal_amount": int(pending_withdrawals[1] or 0),
            "cash_total": int(cash_total or 0),
            "spend_total": int(spend_total or 0),
        }
    except Exception:
        return {"pending_topups": 0, "pending_topup_amount": 0,
                "pending_withdrawals": 0, "pending_withdrawal_amount": 0,
                "cash_total": 0, "spend_total": 0}
