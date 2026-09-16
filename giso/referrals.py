# -*- coding: utf-8 -*-
"""
giso/referrals.py — برنامه معرفی دوستان و کیف پول گیسو (فاز ۳)

مسئولیت‌های سازگاری:
- تولید/اعتبارسنجی کد معرفی ثبت‌نام و حفظ رابطه‌های تاریخی
- soft-deprecation پورسانت Hair Sale و Shop referral بدون حذف رکوردهای قدیمی
- wrapper قراردادهای قدیمی روی سرویس مرکزی ``giso.wallet``
- گزارش سوابق معرفی برای ممیزی

همه داده‌های بیزینسی در giso/data/giso.db ذخیره می‌شوند؛
تنظیمات برنامه در giso_config (bot.db) نگهداری می‌شوند.
"""
import logging
from datetime import datetime

from giso.models import db, User, Referral
from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_referrals")

# ─────────────────────────── تنظیمات ───────────────────────────
SETTINGS_DEFAULTS = {
    "referral_program_enabled": "0",
    "referral_commission_mode": "percent",          # percent | fixed (فروش مو)
    "referral_commission_percent": "5",
    "referral_commission_fixed_amount": "0",
    "referral_min_withdrawal": "100000",
    # پورسانت فروشگاه (معرفی دوستان برای خرید)
    "shop_referral_amount": "10000",                # مبلغ پورسانت هر معرفی فروشگاه (تومان)
    "shop_referral_max": "10",                      # حداکثر تعداد معرفی فروشگاه
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_setting(key: str) -> str:
    try:
        from giso_admin import get_giso_config
        val = get_giso_config(key, SETTINGS_DEFAULTS.get(key, ""))
        return str(val or "").strip() if val is not None else SETTINGS_DEFAULTS.get(key, "")
    except Exception as e:
        logger.debug(f"referral get_setting({key}): {e}")
        return SETTINGS_DEFAULTS.get(key, "")


def _set_setting(key: str, value):
    try:
        from giso_admin import set_giso_config
        set_giso_config(key, str(value))
    except Exception as e:
        logger.warning(f"referral set_setting({key}): {e}")


def get_referral_settings() -> dict:
    """تنظیمات فعلی برنامه معرفی (mode: percent یا fixed — فقط یکی فعال است)."""
    # تصمیم محصول: برنامه معرفی متوقف است؛ مقدار تاریخی bot.db دیگر آن را فعال نمی‌کند.
    enabled = False
    mode = _get_setting("referral_commission_mode").strip().lower()
    if mode not in ("percent", "fixed"):
        mode = "percent"
    try:
        percent = int(float(_get_setting("referral_commission_percent")))
    except (TypeError, ValueError):
        percent = int(SETTINGS_DEFAULTS["referral_commission_percent"])
    try:
        fixed_amount = int(_get_setting("referral_commission_fixed_amount"))
    except (TypeError, ValueError):
        fixed_amount = int(SETTINGS_DEFAULTS["referral_commission_fixed_amount"])
    try:
        min_withdrawal = int(_get_setting("referral_min_withdrawal"))
    except (TypeError, ValueError):
        min_withdrawal = int(SETTINGS_DEFAULTS["referral_min_withdrawal"])
    return {
        "enabled": enabled,
        "mode": mode,
        "commission_percent": max(0, min(100, percent)),
        "commission_fixed_amount": max(0, fixed_amount),
        "min_withdrawal": max(0, min_withdrawal),
    }


def get_show_commission_site() -> bool:
    """آیا بخش پورسانت در کیف پول سایت نمایش داده شود؟ (فاز 5.1 ربات — پیش‌فرض: نمایش)."""
    val = str(_get_setting("referral_show_commission_site") or "").strip().lower()
    if not val:
        return True  # پیش‌فرض: نمایش (رفتار قبلی حفظ شود)
    return val in ("1", "true", "on", "yes")


def set_show_commission_site(flag: bool) -> bool:
    """ذخیره وضعیت نمایش پورسانت در کیف پول سایت (giso_config — مشترک با ربات)."""
    try:
        _set_setting("referral_show_commission_site", "1" if flag else "0")
        return True
    except Exception as e:
        logger.warning(f"set_show_commission_site: {e}")
        return False


def save_referral_settings(enabled: bool, percent: int, min_withdrawal: int,
                           mode: str = "percent", fixed_amount: int = 0,
                           shop_amount: int = 10000, shop_max: int = 10):
    """ذخیره تنظیمات برنامه معرفی (فقط سوپرادمین). mode فقط یکی از percent/fixed."""
    # فقط برای سازگاری امضای قدیمی؛ برنامه هرگز دوباره فعال نمی‌شود.
    _set_setting("referral_program_enabled", "0")
    mode = (mode or "percent").strip().lower()
    if mode not in ("percent", "fixed"):
        mode = "percent"
    _set_setting("referral_commission_mode", mode)
    try:
        percent = max(0, min(100, int(percent)))
    except (TypeError, ValueError):
        percent = int(SETTINGS_DEFAULTS["referral_commission_percent"])
    try:
        fixed_amount = max(0, int(fixed_amount))
    except (TypeError, ValueError):
        fixed_amount = int(SETTINGS_DEFAULTS["referral_commission_fixed_amount"])
    try:
        min_withdrawal = max(0, int(min_withdrawal))
    except (TypeError, ValueError):
        min_withdrawal = int(SETTINGS_DEFAULTS["referral_min_withdrawal"])
    _set_setting("referral_commission_percent", str(percent))
    _set_setting("referral_commission_fixed_amount", str(fixed_amount))
    _set_setting("referral_min_withdrawal", str(min_withdrawal))
    # پورسانت فروشگاه
    try:
        shop_amount = max(0, int(shop_amount))
    except (TypeError, ValueError):
        shop_amount = int(SETTINGS_DEFAULTS["shop_referral_amount"])
    try:
        shop_max = max(1, int(shop_max))
    except (TypeError, ValueError):
        shop_max = int(SETTINGS_DEFAULTS["shop_referral_max"])
    _set_setting("shop_referral_amount", str(shop_amount))
    _set_setting("shop_referral_max", str(shop_max))


def get_shop_referral_settings() -> dict:
    """تنظیمات پورسانت فروشگاه (معرفی دوستان)."""
    try:
        amount = int(_get_setting("shop_referral_amount") or SETTINGS_DEFAULTS["shop_referral_amount"])
    except (TypeError, ValueError):
        amount = int(SETTINGS_DEFAULTS["shop_referral_amount"])
    try:
        max_count = int(_get_setting("shop_referral_max") or SETTINGS_DEFAULTS["shop_referral_max"])
    except (TypeError, ValueError):
        max_count = int(SETTINGS_DEFAULTS["shop_referral_max"])
    return {"amount": amount, "max_count": max_count}


def on_shop_referral_register(referrer_user_id: int, referred_user_id: int):
    """سازگاری legacy: از این پس ثبت‌نام معرفی‌شده هیچ اعتبار مالی ایجاد نمی‌کند.

    رابطه تاریخی referral حفظ می‌شود و مفهوم معرفی فقط می‌تواند ورودی مأموریت‌های
    آتی باشد. این تابع عمداً no-op است تا callerهای قدیمی credit تازه نسازند.
    """
    logger.info(
        "shop referral commission is soft-deprecated; no credit for referrer=%s referred=%s",
        referrer_user_id, referred_user_id,
    )
    return None


# ─────────────────────── سازگاری سوابق تاریخی ───────────────────────
def ensure_referral_code(user) -> str:
    """سازگاری تاریخی؛ کد جدید تولید نمی‌شود و کد قدیمی فقط بازگردانده می‌شود."""
    if not user:
        return ""
    return getattr(user, "referral_code", "") or ""


def resolve_referrer(code: str, phone_norm: str):
    """
    اعتبارسنجی کد معرفی در فرم ثبت‌نام.
    خروجی: (referrer_user یا None, code نرمال‌شده یا '', پیام خطا یا '')
    """
    code = (code or "").strip().upper()
    if not code:
        return None, "", ""
    st = get_referral_settings()
    if not st["enabled"]:
        return None, "", "برنامه معرفی فعلاً غیرفعال است."
    referrer = User.query.filter_by(referral_code=code).first()
    if not referrer:
        return None, "", "کد معرفی نامعتبر است."
    if phone_norm and referrer.phone == phone_norm:
        return None, "", "نمی‌توانید با کد معرفی خودتان ثبت‌نام کنید."
    # جلوگیری از معرفی تکراری برای یک شماره توسط همان معرف
    dup = Referral.query.filter_by(referrer_user_id=referrer.id, referred_phone=phone_norm).first()
    if dup:
        return None, "", "این شماره قبلاً با همین کد معرفی ثبت‌نام شده است."
    return referrer, code, ""


def attach_referral_to_user(user, code: str, phone: str = ""):
    """
    چسباندن معرفی به کاربر از روی کد (مخصوص فرم فروش مو).
    هرگز مسدودکننده نیست — خروجی (ok: bool, message: str):
      - کد خالی → (True, '')
      - کد معتبر و کاربر بدون معرف → ثبت معرفی + (True, پیام موفقیت)
      - کد نامعتبر / self / تکراری → (False, پیام خطا) اما فراخواننده نباید جلوی جریان را بگیرد
    """
    code = (code or "").strip().upper()
    if not code:
        return True, ""
    if not user or not getattr(user, "id", None):
        return True, ""
    # اگر کاربر قبلاً معرفی شده باشد، دوباره ثبت نمی‌شود
    if getattr(user, "referred_by_user_id", 0) or 0:
        return True, ""
    st = get_referral_settings()
    if not st["enabled"]:
        return False, "برنامه معرفی فعلاً غیرفعال است."
    referrer, ref_code, err = resolve_referrer(code, phone or (getattr(user, "phone", "") or ""))
    if err or not referrer:
        return False, (err or "کد معرفی نامعتبر است.")
    # self-referral (گارد دوم؛ resolve_referrer هم چک می‌کند)
    if referrer.id == user.id:
        return False, "نمی‌توانید از کد معرفی خودتان استفاده کنید."
    try:
        user.referred_by_code = ref_code
        user.referred_by_user_id = referrer.id
        db.session.commit()
    except Exception as e:
        logger.warning(f"attach_referral_to_user set: {e}")
        db.session.rollback()
    register_referral(referrer.id, user.id, ref_code, user.phone or phone)
    return True, "کد معرفی با موفقیت اعمال شد."


def register_referral(referrer_user_id: int, referred_user_id: int, code: str, referred_phone: str):
    """برنامه متوقف است؛ برای سازگاری callerهای قدیمی هیچ رکورد جدیدی ساخته نمی‌شود."""
    logger.info("referral registration ignored (program retired): referrer=%s referred=%s",
                referrer_user_id, referred_user_id)
    return None


# ─────────────────────── چرخه پورسانت ───────────────────────
def _find_referral_for_order(order_id: int, phone: str):
    """پیدا کردن referral مرتبط با سفارش: اول با order_id، بعد با شماره."""
    if order_id:
        try:
            r = Referral.query.filter_by(hair_order_id=order_id).first()
            if r:
                return r
        except Exception:
            pass
    if phone:
        try:
            r = (Referral.query
                 .filter(Referral.referred_phone == phone,
                         Referral.status.in_(["registered", "hair_request_submitted"]))
                 .order_by(Referral.id.desc()).first())
            if r:
                return r
        except Exception:
            pass
    return None


def on_hair_order_created(order_id: int):
    """وقتی کاربر معرفی‌شده درخواست فروش مو ثبت می‌کند → referral را به وضعیت درخواست برسان."""
    try:
        if not order_id:
            return
        from giso.models import HairOrder
        order = HairOrder.query.get(order_id)
        if not order:
            return
        phone = order.phone or ""
        r = _find_referral_for_order(order_id, phone)
        if not r:
            return
        changed = False
        if r.hair_order_id != order_id:
            r.hair_order_id = order_id
            changed = True
        if r.status in ("registered", "invited"):
            r.status = "hair_request_submitted"
            changed = True
        if changed:
            r.updated_at = _now()
            db.session.commit()
    except Exception as e:
        logger.warning(f"on_hair_order_created({order_id}): {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def on_hair_order_status_change(order_id: int, new_status: str):
    """
    قلاب چرخه وضعیت سفارش فروش مو:
    - completed → اعتبار یک‌باره پورسانت به کیف پول معرف
    - rejected → اگر هنوز پورسانت داده نشده، معرفی رد می‌شود
    - سایر → به‌روزرسانی وضعیت معرفی
    """
    try:
        if not order_id or not new_status:
            return
        from giso.models import HairOrder
        order = HairOrder.query.get(order_id)
        if not order:
            return
        new_status = (new_status or "").strip().lower()
        phone = order.phone or ""
        r = _find_referral_for_order(order_id, phone)
        if not r:
            return
        r.hair_order_id = order_id

        if new_status == "completed":
            _credit_commission(r, order)
            return
        if new_status in ("rejected", "reject", "canceled", "cancelled"):
            if r.status != "commission_credited":
                r.status = "rejected"
                r.notes = (r.notes or "") + f" | سفارش #{order_id} رد شد"
                r.updated_at = _now()
                db.session.commit()
            return
        # سایر وضعیت‌ها: در جریان
        if r.status in ("registered", "invited"):
            r.status = "hair_request_submitted"
        elif r.status == "hair_request_submitted" and new_status in ("reviewing", "priced", "approved"):
            r.status = "hair_request_submitted"  # ثابت می‌ماند تا تکمیل
        r.updated_at = _now()
        db.session.commit()
    except Exception as e:
        logger.warning(f"on_hair_order_status_change({order_id},{new_status}): {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def _credit_commission(referral: Referral, order):
    """سازگاری legacy: پورسانت جدید Hair Sale دیگر ایجاد نمی‌شود.

    رکوردهای referrals و wallet_transactions تاریخی بدون حذف یا بازنویسی باقی
    می‌مانند. وضعیت referral جاری فقط برای ممیزی soft-deprecation ثبت می‌شود.
    """
    try:
        if referral.status == "commission_credited":
            return  # اعتبار تاریخی دست‌نخورده می‌ماند.
        referral.status = "deprecated_no_commission"
        referral.hair_order_id = int(getattr(order, "id", 0) or 0)
        referral.updated_at = _now()
        referral.notes = (referral.notes or "") + " | پورسانت Hair Sale غیرفعال است؛ اعتباری ایجاد نشد"
        db.session.commit()
        logger.info("hair-sale referral commission skipped: ref#%s order#%s", referral.id, referral.hair_order_id)
    except Exception as e:
        logger.warning(f"_credit_commission deprecated path: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


# ─────────────────────────── کیف پول ───────────────────────────
def get_wallet_balance(user_id: int) -> int:
    """قرارداد legacy: کل مانده قابل مصرف کیف پول واحد (cash + spend)."""
    try:
        from giso.wallet import get_wallet_balances
        return int(get_wallet_balances(user_id)["usable"])
    except Exception as e:
        logger.warning(f"get_wallet_balance: {e}")
        return 0


def get_month_commission(user_id: int) -> int:
    """پورسانت این ماه (میلادی جاری)."""
    try:
        month_prefix = datetime.now().strftime("%Y-%m")
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM wallet_transactions "
                "WHERE user_id=? AND kind='commission' AND status='available' AND created_at LIKE ?",
                (user_id, month_prefix + "%")
            ).fetchone()
            return int((row[0] if row else 0) or 0)
    except Exception as e:
        logger.warning(f"get_month_commission: {e}")
        return 0


def get_successful_referrals_count(user_id: int) -> int:
    try:
        return Referral.query.filter_by(referrer_user_id=user_id, status="commission_credited").count()
    except Exception:
        return 0


def get_wallet_summary(user_id: int) -> dict:
    from giso.wallet import get_wallet_balances
    balances = get_wallet_balances(user_id)
    return {
        **balances,
        "month_commission": get_month_commission(user_id),
        "successful_referrals": get_successful_referrals_count(user_id),
        "total_referrals": _count_referrals(user_id),
    }


def _count_referrals(user_id: int) -> int:
    try:
        return Referral.query.filter_by(referrer_user_id=user_id).count()
    except Exception:
        return 0


def get_user_referrals(user_id: int, limit: int = 30):
    try:
        rows = (Referral.query.filter_by(referrer_user_id=user_id)
                .order_by(Referral.id.desc()).limit(limit).all())
        out = []
        for r in rows:
            referred_name = ""
            referred_phone = r.referred_phone or ""
            try:
                u = User.query.get(r.referred_user_id)
                if u:
                    referred_name = (u.name or "").strip() or (u.first_name or "")
            except Exception:
                pass
            out.append({
                "id": r.id,
                "referred_name": referred_name,
                "referred_phone": referred_phone,
                "status": r.status,
                "hair_order_id": r.hair_order_id,
                "sale_amount": r.sale_amount,
                "commission_amount": r.commission_amount,
                "created_at": r.created_at,
            })
        return out
    except Exception as e:
        logger.warning(f"get_user_referrals: {e}")
        return []


def get_user_transactions(user_id: int, limit: int = 30):
    try:
        from giso.wallet import get_user_transactions as _transactions
        return _transactions(user_id, limit=limit)
    except Exception as e:
        logger.warning(f"get_user_transactions: {e}")
        return []


# ─────────────────────── درخواست تسویه ───────────────────────
def create_withdrawal_request(user_id: int, amount, holder_name: str, sheba: str = "", card: str = "") -> tuple:
    """wrapper سازگار با سرویس مرکزی؛ تسویه فقط از cash رزرو می‌شود."""
    from giso.wallet import create_withdrawal_request as _create
    return _create(user_id, amount, holder_name, sheba, card)


# ─────────────────────── مدیریت ادمین ───────────────────────
def list_referrals(limit: int = 100):
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT r.*, u.name AS referrer_name, u.phone AS referrer_phone, "
                "       ru.name AS referred_name, ru.phone AS referred_phone2 "
                "FROM referrals r "
                "LEFT JOIN giso_web_auth u ON u.id = r.referrer_user_id "
                "LEFT JOIN giso_web_auth ru ON ru.id = r.referred_user_id "
                "ORDER BY r.id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"list_referrals: {e}")
        return []


def get_referral_stats() -> dict:
    try:
        with get_giso_db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
            credited = conn.execute("SELECT COUNT(*) FROM referrals WHERE status='commission_credited'").fetchone()[0]
            submitted = conn.execute("SELECT COUNT(*) FROM referrals WHERE status='hair_request_submitted'").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM referrals WHERE status='rejected'").fetchone()[0]
            sum_comm = conn.execute("SELECT COALESCE(SUM(commission_amount),0) FROM referrals WHERE status='commission_credited'").fetchone()[0]
            return {
                "total": int(total or 0),
                "credited": int(credited or 0),
                "submitted": int(submitted or 0),
                "rejected": int(rejected or 0),
                "total_commission": int(sum_comm or 0),
            }
    except Exception as e:
        logger.warning(f"get_referral_stats: {e}")
        return {"total": 0, "credited": 0, "submitted": 0, "rejected": 0, "total_commission": 0}


def list_withdrawals(limit: int = 100):
    from giso.wallet import list_withdrawals as _list
    return _list(limit=limit)


def set_withdrawal_status(withdrawal_id: int, new_status: str, admin_note: str = "") -> tuple:
    """wrapper legacy؛ سرویس مرکزی مجوز صریح سوپرادمین و transition اتمیک دارد."""
    from giso.wallet import review_withdrawal
    return review_withdrawal(withdrawal_id, new_status, admin_note)



__all__ = [
    "get_referral_settings", "save_referral_settings",
    "get_show_commission_site", "set_show_commission_site",
    "ensure_referral_code", "resolve_referrer", "register_referral", "attach_referral_to_user",
    "on_hair_order_created", "on_hair_order_status_change",
    "get_wallet_summary", "get_wallet_balance", "get_month_commission",
    "get_successful_referrals_count", "get_user_referrals", "get_user_transactions",
    "create_withdrawal_request",
    "list_referrals", "get_referral_stats", "list_withdrawals", "set_withdrawal_status",
]
