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
from datetime import datetime

from giso.base import get_giso_db_conn, normalize_phone
from giso.money import format_toman

logger = logging.getLogger("giso_wallet")
from giso.wallet_core import (
    SCOPES,
    MISSION_EVENTS,
    SERVICE_FEE_KEYS,
    _DIGIT_MAP,
    SERVICE_CREDIT_DEFS,
    WalletCheckoutError,
    _now,
    _setting,
    _positive_int,
    get_financial_settings,
    is_financial_superadmin,
    save_financial_settings,
    get_wallet_balances,
    get_user_transactions,
    get_admin_financial_summary,
    _RANK_LEVELS_DEFAULT,
    _rank_levels_config,
    rank_daily_credit_enabled,
    get_rank_settings,
    save_rank_settings,
    get_user_rank,
    get_weekly_leaderboard,
    get_service_credit_settings,
    save_service_credit_settings,
    charge_service_credit,
    service_charge_report,
)
from giso.wallet_missions import (
    list_missions_for_user,
    list_missions_admin,
    create_mission,
    delete_mission,
    update_mission,
    complete_mission,
    record_product_mission_view,
    complete_bale_connection_mission,
)

def create_topup_request(user_id: int, amount, payment_reference: str = "",
                         user_note: str = "", receipt_path: str = "") -> tuple:
    """ثبت درخواست شارژ با رسید اجباری؛ کد پیگیری عمداً اختیاری است."""
    settings = get_financial_settings()
    if not settings["topup_enabled"]:
        return False, "درخواست افزایش موجودی فعلاً غیرفعال است.", None
    amount = _positive_int(amount)
    reference = str(payment_reference or "").strip()[:120]
    receipt = str(receipt_path or "").strip().lower()[:120]
    note = str(user_note or "").strip()[:1000]
    if amount < settings["min_topup"]:
        return False, f"حداقل مبلغ افزایش موجودی {format_toman(settings['min_topup'])} است.", None
    if not re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|png)", receipt):
        return False, "تصویر رسید پرداخت معتبر الزامی است.", None
    try:
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "INSERT INTO wallet_topup_requests "
                "(user_id,amount,payment_reference,receipt_path,user_note,status,created_at) "
                "VALUES (?,?,?,?,?, 'pending',?)",
                (int(user_id), amount, reference, receipt, note, _now()),
            )
            conn.commit()
            request_id = int(cur.lastrowid)
        # مرکز اعلان: درخواست جدید شارژ (پیش‌فرض سوپرادمین)
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("wallet", "topup_request", "درخواست جدید شارژ کیف پول",
                     f"درخواست شارژ #{request_id} — مبلغ: {format_toman(amount)}",
                     source_type="wallet_topup_request", source_id=request_id)
        except Exception:
            pass
        return True, "درخواست افزایش موجودی ثبت شد و در انتظار بررسی است.", request_id
    except Exception as exc:
        logger.exception("create topup failed: %s", exc)
        return False, "ثبت درخواست افزایش موجودی ناموفق بود.", None

def list_user_topups(user_id: int, limit: int = 30) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM wallet_topup_requests WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (int(user_id), max(1, min(100, int(limit or 30)))),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []

def list_topups(limit: int = 200) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT t.*,u.name AS user_name,u.phone AS user_phone "
                "FROM wallet_topup_requests t LEFT JOIN giso_web_auth u ON u.id=t.user_id "
                "ORDER BY CASE t.status WHEN 'pending' THEN 0 ELSE 1 END,t.id DESC LIMIT ?",
                (max(1, min(500, int(limit or 200))),),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("list topups failed: %s", exc)
        return []

def review_topup(request_id: int, new_status: str, admin_note: str = "") -> tuple:
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند درخواست شارژ را بررسی کند."
    new_status = str(new_status or "").strip().lower()
    if new_status not in ("approved", "rejected"):
        return False, "وضعیت درخواست نامعتبر است."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM wallet_topup_requests WHERE id=?", (int(request_id),)).fetchone()
        if not row:
            raise WalletCheckoutError("درخواست افزایش موجودی پیدا نشد.")
        if row["status"] != "pending":
            raise WalletCheckoutError("این درخواست قبلاً بررسی شده است.")
        actor_id = 0
        try:
            from flask_login import current_user
            actor_id = int(getattr(current_user, "id", 0) or 0)
        except Exception:
            pass
        now = _now()
        conn.execute(
            "UPDATE wallet_topup_requests SET status=?,admin_note=?,reviewed_at=?,reviewed_by_user_id=? "
            "WHERE id=? AND status='pending'",
            (new_status, str(admin_note or "").strip()[:1000], now, actor_id, int(request_id)),
        )
        if new_status == "approved":
            conn.execute(
                "INSERT INTO wallet_transactions "
                "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                "VALUES (?, 'topup', ?, 'available', 'wallet_topup', ?, 'cash', ?, ?, ?)",
                (int(row["user_id"]), int(row["amount"]), int(request_id),
                 f"topup:{int(request_id)}", f"تأیید افزایش موجودی #{int(request_id)}", now),
            )
        conn.commit()
        # اعلان به کاربر در پنل سایت (شارژ تأیید/رد شد)
        try:
            phone_row = conn.execute("SELECT phone FROM giso_web_auth WHERE id=?", (int(row["user_id"]),)).fetchone()
            if phone_row and phone_row["phone"]:
                from giso.panel.modules.notifications import log_user_notification
                if new_status == "approved":
                    log_user_notification(phone_row["phone"], "topup_status", "شارژ کیف پول تأیید شد",
                                          f"درخواست شارژ #{int(request_id)} تأیید شد و {format_toman(int(row['amount']))} به کیف پول شما اضافه شد.",
                                          source_type="wallet_topup_status", source_id=int(request_id), category="wallet")
                else:
                    _note = f" — یادداشت: {str(admin_note or '').strip()[:200]}" if str(admin_note or '').strip() else ""
                    log_user_notification(phone_row["phone"], "topup_status", "شارژ کیف پول رد شد",
                                          f"درخواست شارژ #{int(request_id)} رد شد.{_note}",
                                          source_type="wallet_topup_status", source_id=int(request_id), category="wallet")
        except Exception as e_notif:
            logger.debug(f"topup user notify failed: {e_notif}")
        return True, "درخواست افزایش موجودی تأیید شد." if new_status == "approved" else "درخواست افزایش موجودی رد شد."
    except (WalletCheckoutError, sqlite3.IntegrityError) as exc:
        conn.rollback()
        return False, str(exc) if isinstance(exc, WalletCheckoutError) else "اعتبار این درخواست قبلاً ثبت شده است."
    except Exception as exc:
        conn.rollback()
        logger.exception("review topup failed: %s", exc)
        return False, "بررسی درخواست افزایش موجودی ناموفق بود."
    finally:
        conn.close()

def create_withdrawal_request(user_id: int, amount, holder_name: str,
                              sheba: str = "", card: str = "") -> tuple:
    """رزرو اتمیک فقط از cash؛ spend هرگز قابل تسویه نیست."""
    settings = get_financial_settings()
    if not settings["withdrawal_enabled"]:
        return False, "تسویه کیف پول فعلاً غیرفعال است.", None
    amount = _positive_int(amount)
    holder = str(holder_name or "").strip()[:150]
    sheba = str(sheba or "").strip().upper().replace(" ", "")
    card = re.sub(r"\D", "", str(card or ""))
    if amount < settings["min_withdrawal"]:
        return False, f"حداقل مبلغ تسویه {format_toman(settings['min_withdrawal'])} است.", None
    if not holder:
        return False, "نام صاحب کارت الزامی است.", None
    if not card:
        return False, "شماره کارت الزامی است.", None
    if len(card) != 16:
        return False, "شماره کارت باید ۱۶ رقم باشد.", None
    if sheba and not re.fullmatch(r"IR\d{24}", sheba):
        return False, "شماره شبا باید با IR شروع شود و ۲۶ کاراکتر باشد.", None
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balances = get_wallet_balances(int(user_id), conn=conn)
        if amount > balances["cash"]:
            raise WalletCheckoutError(f"موجودی نقدی قابل تسویه ({format_toman(balances['cash'])}) کافی نیست.")
        now = _now()
        cur = conn.execute(
            "INSERT INTO withdrawal_requests "
            "(user_id,amount,card_holder_name,card_number,sheba,status,created_at) "
            "VALUES (?,?,?,?,?,'pending',?)",
            (int(user_id), amount, holder, card, sheba, now),
        )
        request_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
            "VALUES (?, 'withdrawal', ?, 'pending', 'withdrawal', ?, 'cash', ?, ?, ?)",
            (int(user_id), -amount, request_id, f"withdrawal:{request_id}",
             f"درخواست تسویه #{request_id}", now),
        )
        conn.commit()
        # مرکز اعلان: درخواست جدید تسویه (پیش‌فرض سوپرادمین)
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("wallet", "withdrawal_request", "درخواست جدید تسویه کیف پول",
                     f"درخواست تسویه #{request_id} — مبلغ: {format_toman(amount)}",
                     source_type="wallet_withdrawal_request", source_id=request_id)
        except Exception:
            pass
        return True, "درخواست تسویه ثبت شد و موجودی نقدی آن رزرو شد.", request_id
    except WalletCheckoutError as exc:
        conn.rollback()
        return False, str(exc), None
    except Exception as exc:
        conn.rollback()
        logger.exception("withdrawal request failed: %s", exc)
        return False, "ثبت درخواست تسویه ناموفق بود.", None
    finally:
        conn.close()

def list_user_withdrawals(user_id: int, limit: int = 30) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM withdrawal_requests WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (int(user_id), max(1, min(100, int(limit or 30)))),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []

def list_withdrawals(limit: int = 200) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT w.*,u.name AS user_name,u.phone AS user_phone "
                "FROM withdrawal_requests w LEFT JOIN giso_web_auth u ON u.id=w.user_id "
                "ORDER BY CASE w.status WHEN 'pending' THEN 0 ELSE 1 END,w.id DESC LIMIT ?",
                (max(1, min(500, int(limit or 200))),),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []

def review_withdrawal(withdrawal_id: int, new_status: str, admin_note: str = "") -> tuple:
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند تسویه را بررسی کند."
    new_status = str(new_status or "").strip().lower()
    if new_status not in ("paid", "rejected"):
        return False, "وضعیت تسویه نامعتبر است."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM withdrawal_requests WHERE id=?", (int(withdrawal_id),)).fetchone()
        if not row:
            raise WalletCheckoutError("درخواست تسویه پیدا نشد.")
        if row["status"] != "pending":
            raise WalletCheckoutError("این درخواست قبلاً بررسی شده است.")
        now = _now()
        conn.execute(
            "UPDATE withdrawal_requests SET status=?,admin_note=?,updated_at=? WHERE id=? AND status='pending'",
            (new_status, str(admin_note or "").strip()[:1000], now, int(withdrawal_id)),
        )
        tx_status = "paid" if new_status == "paid" else "reversed"
        cur = conn.execute(
            "UPDATE wallet_transactions SET status=? WHERE source_type='withdrawal' AND source_id=? AND status='pending'",
            (tx_status, int(withdrawal_id)),
        )
        if cur.rowcount != 1:
            raise WalletCheckoutError("تراکنش رزرو تسویه معتبر نیست؛ عملیات انجام نشد.")
        conn.commit()
        # اعلان به کاربر در پنل سایت (تسویه پرداخت/رد شد)
        try:
            phone_row = conn.execute("SELECT phone FROM giso_web_auth WHERE id=?", (int(row["user_id"]),)).fetchone()
            if phone_row and phone_row["phone"]:
                from giso.panel.modules.notifications import log_user_notification
                if new_status == "paid":
                    log_user_notification(phone_row["phone"], "withdrawal_status", "تسویه پرداخت شد",
                                          f"درخواست تسویه #{int(withdrawal_id)} به مبلغ {format_toman(int(row['amount']))} پرداخت شد.",
                                          source_type="wallet_withdrawal_status", source_id=int(withdrawal_id), category="wallet")
                else:
                    log_user_notification(phone_row["phone"], "withdrawal_status", "تسویه رد شد",
                                          f"درخواست تسویه #{int(withdrawal_id)} رد شد و موجودی نقدی شما آزاد شد.",
                                          source_type="wallet_withdrawal_status", source_id=int(withdrawal_id), category="wallet")
        except Exception as e_notif:
            logger.debug(f"withdrawal user notify failed: {e_notif}")
        return True, "تسویه پرداخت‌شده ثبت شد." if new_status == "paid" else "تسویه رد و موجودی نقدی آزاد شد."
    except WalletCheckoutError as exc:
        conn.rollback()
        return False, str(exc)
    except Exception as exc:
        conn.rollback()
        logger.exception("review withdrawal failed: %s", exc)
        return False, "بررسی تسویه ناموفق بود."
    finally:
        conn.close()

def manual_adjust(user_id: int, amount, scope: str, reason: str = "") -> tuple:
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند مانده کیف پول را تغییر دهد."
    try:
        amount = int(str(amount or "0").translate(_DIGIT_MAP))
    except (TypeError, ValueError):
        amount = 0
    scope = str(scope or "").strip().lower()
    if amount == 0:
        return False, "مبلغ تغییر نمی‌تواند صفر باشد."
    if scope not in SCOPES:
        return False, "نوع موجودی نامعتبر است."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balances = get_wallet_balances(int(user_id), conn=conn)
        if amount < 0 and abs(amount) > balances[scope]:
            raise WalletCheckoutError("کسر دستی بیشتر از ماندهٔ همان نوع موجودی است.")
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,description,created_at) "
            "VALUES (?, 'adjustment', ?, 'available', 'manual', 0, ?, ?, ?)",
            (int(user_id), amount, scope,
             f"اصلاح دستی سوپرادمین — {str(reason or 'بدون توضیح').strip()[:500]}", _now()),
        )
        conn.commit()
        return True, f"مانده {('نقدی' if scope == 'cash' else 'اعتباری')} {format_toman(amount, show_plus=True)} تغییر کرد."
    except WalletCheckoutError as exc:
        conn.rollback()
        return False, str(exc)
    except Exception as exc:
        conn.rollback()
        logger.exception("manual wallet adjustment failed: %s", exc)
        return False, "تغییر مانده کیف پول ناموفق بود."
    finally:
        conn.close()

def _discount_inside_transaction(conn, code: str, gross: int) -> tuple:
    code = str(code or "").strip().upper()
    if not code:
        return 0, ""
    row = conn.execute("SELECT * FROM discount_codes WHERE code=? AND is_active=1", (code,)).fetchone()
    if not row:
        raise WalletCheckoutError("کد تخفیف نامعتبر است.")
    expires = str(row["expires_at"] or "").strip()
    if expires:
        try:
            if datetime.now() > datetime.strptime(expires, "%Y-%m-%d %H:%M:%S"):
                raise WalletCheckoutError("کد تخفیف منقضی شده است.")
        except ValueError:
            pass
    maximum = int(row["max_uses"] or 0)
    used = int(row["used_count"] or 0)
    if maximum > 0 and used >= maximum:
        raise WalletCheckoutError("ظرفیت استفاده از کد تخفیف تمام شده است.")
    minimum = int(row["min_order_amount"] or 0)
    if gross < minimum:
        raise WalletCheckoutError(f"حداقل مبلغ سفارش برای این کد {format_toman(minimum)} است.")
    value = max(0, int(row["discount_value"] or 0))
    amount = int(gross * value / 100) if row["discount_type"] == "percent" else min(value, gross)
    cur = conn.execute(
        "UPDATE discount_codes SET used_count=used_count+1 WHERE id=? AND (max_uses=0 OR used_count<max_uses)",
        (int(row["id"]),),
    )
    if cur.rowcount != 1:
        raise WalletCheckoutError("ظرفیت استفاده از کد تخفیف تمام شده است.")
    return max(0, min(amount, gross)), code

def create_shop_checkout_atomic(user_id: int, items: list, customer: dict,
                                pay_with_wallet: bool = False, discount_code: str = "") -> dict:
    """ساخت checkout، سفارش‌ها و debit کیف پول در یک BEGIN IMMEDIATE.

    مبلغ و publish/stock محصول داخل همان transaction دوباره از DB خوانده می‌شود.
    WalletTransaction فقط پس از ساخت ShopCheckout به source معتبر آن متصل می‌شود.
    """
    import secrets
    shared_tracking = ""
    for item in items or []:
        code = str(item.get("tracking_code") or "").strip()[:40]
        if code:
            shared_tracking = code
            break
    if not shared_tracking:
        shared_tracking = "GSO-" + secrets.token_hex(4).upper()
    normalized = []
    for item in items or []:
        try:
            product_id = int(item.get("product_id") or 0)
            quantity = max(1, min(99, int(item.get("quantity") or 1)))
        except (TypeError, ValueError):
            continue
        if product_id:
            normalized.append({
                "product_id": product_id,
                "quantity": quantity,
                "tracking_code": shared_tracking,
            })
    if not normalized:
        raise WalletCheckoutError("سبد خرید معتبر نیست.")
    name = str(customer.get("name") or "").strip()[:100]
    phone = normalize_phone(customer.get("phone") or "")
    address = str(customer.get("address") or "").strip()
    courier_note = str(customer.get("courier_note") or "").strip()[:1000]
    delivery_time = str(customer.get("delivery_time") or "").strip()[:200]
    if not name or not phone or not address:
        raise WalletCheckoutError("نام، شماره تماس و آدرس الزامی است.")

    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # E1 fix: رزرو اتمیک موجودی — جمع تعداد هر محصول سبد، سپس SELECT + UPDATE داخل همین تراکنش.
        # SQLite معادل مستقیم FOR UPDATE ندارد؛ BEGIN IMMEDIATE از ابتدا قفل write را می‌گیرد،
        # بنابراین stock بین SELECT و UPDATE نمی‌تواند توسط تراکنش دیگری تغییر کند.
        now = _now()
        # اگر ستون stock وجود نداشته باشد (DB قدیمی/تست پیش از migration)، رفتار legacy بدون محدودیت می‌ماند.
        has_stock_col = False
        try:
            for col in conn.execute("PRAGMA table_info(products)").fetchall():
                try:
                    col_name = str(col["name"])
                except (TypeError, KeyError, IndexError):
                    col_name = str(col[1])
                if col_name == "stock":
                    has_stock_col = True
                    break
        except Exception:
            has_stock_col = False
        product_cols = ("id,name,price,in_stock,publish_status,stock" if has_stock_col
                        else "id,name,price,in_stock,publish_status")
        qty_by_product: dict[int, int] = {}
        for item in normalized:
            qty_by_product[int(item["product_id"])] = (
                qty_by_product.get(int(item["product_id"]), 0) + int(item["quantity"])
            )
        verified_products: dict[int, dict] = {}
        # بهینه‌سازی N+1: یک کوئری IN به‌جای کوئری per محصول؛ اعتبارسنجی‌ها عیناً حفظ شدند
        _ids = [int(pid) for pid in qty_by_product]
        _rows = conn.execute(
            f"SELECT {product_cols} FROM products WHERE id IN ({','.join('?' for _ in _ids)})", _ids,
        ).fetchall() if _ids else []
        _by_id = {int(r["id"]): r for r in _rows}
        for product_id, wanted in qty_by_product.items():
            product = _by_id.get(int(product_id))
            if not product or not int(product["in_stock"] or 0):
                raise WalletCheckoutError("یکی از محصولات سبد دیگر موجود نیست.")
            if str(product["publish_status"] or "published") != "published":
                raise WalletCheckoutError("یکی از محصولات سبد دیگر برای خرید عمومی منتشر نیست.")
            # stock NULL = سقف نامحدود (رفتار قبلی)؛ فقط محصولات دارای stock عددی رزرو می‌شوند.
            if has_stock_col:
                stock_value = product["stock"]
                if stock_value is not None:
                    try:
                        stock_left = int(stock_value or 0)
                    except (TypeError, ValueError):
                        stock_left = 0
                    if stock_left < wanted:
                        raise WalletCheckoutError(
                            f"موجودی «{product['name']}» کافی نیست "
                            f"(موجودی: {stock_left}، درخواستی: {wanted})."
                        )
                    conn.execute(
                        "UPDATE products SET stock=?, in_stock=CASE WHEN ?<=0 THEN 0 ELSE in_stock END, "
                        "updated_at=? WHERE id=?",
                        (stock_left - wanted, stock_left - wanted, now, product_id),
                    )
            verified_products[product_id] = product
        priced_items = []
        gross = 0
        for item in normalized:
            product = verified_products[int(item["product_id"])]
            unit_price = max(0, int(product["price"] or 0))
            line_total = unit_price * item["quantity"]
            gross += line_total
            priced_items.append({
                **item, "name": product["name"], "unit_price": unit_price,
                "line_total": line_total,
            })
        discount_amount, applied_code = _discount_inside_transaction(conn, discount_code, gross)
        payable = max(0, gross - discount_amount)
        cash_used = 0
        spend_used = 0
        if pay_with_wallet and payable:
            balances = get_wallet_balances(int(user_id), conn=conn)
            # اعتبار غیرقابل‌تسویه زودتر مصرف می‌شود تا cash کاربر حفظ شود.
            spend_used = min(balances["spend"], payable)
            cash_used = min(balances["cash"], payable - spend_used)
        wallet_used = spend_used + cash_used
        cod_amount = max(0, payable - wallet_used)
        checkout = conn.execute(
            "INSERT INTO shop_checkouts "
            "(user_id,gross_amount,discount_amount,wallet_used,cash_wallet_used,spend_wallet_used,"
            "cod_amount,discount_code,status,created_at) VALUES (?,?,?,?,?,?,?,?, 'placed',?)",
            (int(user_id), gross, discount_amount, wallet_used, cash_used, spend_used,
             cod_amount, applied_code, now),
        )
        checkout_id = int(checkout.lastrowid)
        payment_status = "settled" if cod_amount == 0 else ("split_due" if wallet_used else "cod_due")
        invoice_number = f"GSO-{datetime.now().strftime('%Y%m%d')}-{checkout_id:06d}"
        invoice_cur = conn.execute(
            "INSERT INTO shop_invoices "
            "(invoice_number,checkout_id,user_id,customer_name,customer_phone,customer_address,"
            "gross_amount,discount_amount,payable_amount,wallet_paid_amount,cod_amount,payment_status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (invoice_number, checkout_id, int(user_id), name, phone, address, gross,
             discount_amount, payable, wallet_used, cod_amount, payment_status, now),
        )
        invoice_id = int(invoice_cur.lastrowid)
        order_ids = []
        for item in priced_items:
            cur = conn.execute(
                "INSERT INTO product_orders "
                "(user_id,phone,customer_name,product_id,checkout_id,invoice_id,address,quantity,status,tracking_code,"
                "shipping_cost,courier_note,delivery_time,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,'pending',?,0,?,?,?)",
                (int(user_id), phone, name, item["product_id"], checkout_id, invoice_id, address,
                 item["quantity"], item["tracking_code"], courier_note, delivery_time, now),
            )
            order_id = int(cur.lastrowid)
            order_ids.append(order_id)
            conn.execute(
                "INSERT INTO shop_invoice_items "
                "(invoice_id,order_id,product_id,product_name,unit_price,quantity,line_total) "
                "VALUES (?,?,?,?,?,?,?)",
                (invoice_id, order_id, item["product_id"], item["name"], item["unit_price"],
                 item["quantity"], item["line_total"]),
            )
        for scope, used in (("spend", spend_used), ("cash", cash_used)):
            if not used:
                continue
            conn.execute(
                "INSERT INTO wallet_transactions "
                "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                "VALUES (?, 'purchase', ?, 'used', 'shop_checkout', ?, ?, ?, ?, ?)",
                (int(user_id), -used, checkout_id, scope,
                 f"checkout:{checkout_id}:{scope}",
                 f"پرداخت کیف پول برای checkout فروشگاه #{checkout_id}", now),
            )
        conn.commit()
        return {
            "checkout_id": checkout_id,
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "payment_status": payment_status,
            "order_ids": order_ids,
            "items": priced_items,
            "gross_amount": gross,
            "discount_amount": discount_amount,
            "payable_amount": payable,
            "wallet_used": wallet_used,
            "cash_wallet_used": cash_used,
            "spend_wallet_used": spend_used,
            "cod_amount": cod_amount,
            "discount_code": applied_code,
        }
    except WalletCheckoutError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.exception("atomic shop checkout failed: %s", exc)
        raise WalletCheckoutError("ثبت اتمیک سفارش ناموفق بود؛ هیچ مبلغی از کیف پول کسر نشد.")
    finally:
        conn.close()

def edit_shop_checkout_atomic(user_id:int,checkout_id:int,quantities:dict,address:str,courier_note:str="",delivery_time:str="")->tuple[bool,str]:
    """ویرایش امن سفارش COD بدون برداشت کیف پول؛ فقط پیش از شروع پردازش."""
    address=str(address or "").strip()[:1000]
    if not address:return False,"آدرس الزامی است."
    conn=get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        checkout=conn.execute("SELECT * FROM shop_checkouts WHERE id=? AND user_id=?",(int(checkout_id),int(user_id))).fetchone()
        if not checkout:return False,"سفارش پیدا نشد."
        if str(checkout['status'] or 'placed')!='placed' or int(checkout['wallet_used'] or 0)>0 or int(checkout['discount_amount'] or 0)>0:
            conn.rollback();return False,"سفارش پرداخت‌شده یا تخفیف‌دار برای حفظ صحت فاکتور قابل ویرایش نیست."
        orders=conn.execute("SELECT po.*,ii.id item_id,ii.unit_price FROM product_orders po JOIN shop_invoice_items ii ON ii.order_id=po.id WHERE po.checkout_id=? ORDER BY po.id",(int(checkout_id),)).fetchall()
        if not orders or any(str(o['status']) not in ('pending','new') for o in orders):
            conn.rollback();return False,"ویرایش فقط پیش از تأیید و آماده‌سازی سفارش ممکن است."
        desired=[]
        for o in orders:
            try:q=max(0,min(99,int(quantities.get(str(o['id']),o['quantity']) or 0)))
            except (TypeError,ValueError):q=int(o['quantity'] or 1)
            if q:desired.append((o,q))
        if not desired:conn.rollback();return False,"حداقل یک محصول باید در سفارش باقی بماند."
        keep={int(o['id']) for o,q in desired};invoice_id=int(orders[0]['invoice_id'])
        for o in orders:
            if int(o['id']) not in keep:
                conn.execute("DELETE FROM shop_invoice_items WHERE order_id=?",(o['id'],));conn.execute("DELETE FROM product_orders WHERE id=?",(o['id'],))
        gross=0
        for o,q in desired:
            line=int(o['unit_price'] or 0)*q;gross+=line
            conn.execute("UPDATE product_orders SET quantity=?,address=?,courier_note=?,delivery_time=? WHERE id=?",(q,address,str(courier_note or '')[:1000],str(delivery_time or '')[:200],o['id']))
            conn.execute("UPDATE shop_invoice_items SET quantity=?,line_total=? WHERE id=?",(q,line,o['item_id']))
        conn.execute("UPDATE shop_checkouts SET gross_amount=?,cod_amount=? WHERE id=?",(gross,gross,int(checkout_id)))
        conn.execute("UPDATE shop_invoices SET customer_address=?,gross_amount=?,payable_amount=?,cod_amount=? WHERE id=?",(address,gross,gross,gross,invoice_id))
        conn.commit();return True,"سفارش و فاکتور با موفقیت ویرایش شد."
    except Exception as exc:
        conn.rollback();logger.exception("checkout edit failed: %s",exc);return False,"ویرایش سفارش ناموفق بود."
    finally:conn.close()

def get_service_fees() -> dict:
    """کارمزد خدمات (تومان) — از giso_config خوانده می‌شود.

    کلیدها بر اساس SERVICE_FEE_KEYS هستند؛ مقدار پیش‌فرض صفر است.
    """
    out = {}
    for name, (key, default) in SERVICE_FEE_KEYS.items():
        out[name] = _positive_int(_setting(key), default)
    return out

def save_service_fees(values: dict) -> tuple:
    """ذخیره کارمزد خدمات — فقط سوپرادمین مالی."""
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند کارمزد خدمات را تغییر دهد."
    try:
        from giso_admin import set_giso_config
        for name, (key, default) in SERVICE_FEE_KEYS.items():
            fee = _positive_int(values.get(f"fee_{name}"), default)
            set_giso_config(key, str(fee))
        return True, "کارمزد خدمات ذخیره شد."
    except Exception as exc:
        logger.exception("save service fees failed: %s", exc)
        return False, "ذخیره کارمزد خدمات ناموفق بود."

def charge_service_fee(user_id: int, service: str, amount: int, reason: str = "") -> tuple:
    """کسر اتمیک کارمزد سرویس از cash کیف پول (در صورت فعال بودن و وجود مانده).

    طبق قرارداد، بازارچه مو هرگز از کیف پول کسر نمی‌شود.
    """
    service = str(service or "").strip().lower()
    if service == "marketplace":
        return True, "بازارچه مو از کیف پول کسر نمی‌شود."
    if service not in SERVICE_FEE_KEYS:
        return False, "نوع سرویس نامعتبر است."
    fee = _positive_int(amount)
    if fee <= 0:
        return False, "مبلغ کارمزد نامعتبر است."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balances = get_wallet_balances(int(user_id), conn=conn)
        if balances["cash"] < fee:
            conn.rollback()
            return False, "موجودی نقدی کاربر برای کسر کارمزد کافی نیست."
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
            "VALUES (?, 'service_fee', ?, 'used', 'service_fee', 0, 'cash', ?, ?, ?)",
            (int(user_id), -fee, f"service_fee:{service}:{int(user_id)}",
             f"کارمزد سرویس {service} — {str(reason or 'بدون توضیح').strip()[:400]}", _now()),
        )
        conn.commit()
        return True, "کارمزد سرویس کسر شد."
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("charge service fee failed: %s", exc)
        return False, "کسر کارمزد سرویس ناموفق بود."
    finally:
        conn.close()

__all__ = [
    "WalletCheckoutError", "get_financial_settings", "save_financial_settings",
    "is_financial_superadmin", "get_wallet_balances", "get_user_transactions",
    "create_topup_request", "list_user_topups", "list_topups", "review_topup",
    "create_withdrawal_request", "list_user_withdrawals", "list_withdrawals", "review_withdrawal",
    "manual_adjust", "list_missions_for_user", "list_missions_admin",
    "create_mission", "update_mission", "delete_mission",
    "complete_mission", "record_product_mission_view", "complete_bale_connection_mission",
    "create_shop_checkout_atomic", "edit_shop_checkout_atomic", "get_admin_financial_summary",
    "MISSION_EVENTS", "SERVICE_FEE_KEYS", "get_service_fees", "save_service_fees",
    "charge_service_fee",
    "get_user_rank", "get_weekly_leaderboard",
    "SERVICE_CREDIT_DEFS", "get_service_credit_settings", "save_service_credit_settings",
    "charge_service_credit", "service_charge_report",
    "get_rank_settings", "save_rank_settings", "rank_daily_credit_enabled",
    "_rank_levels_config",
]
