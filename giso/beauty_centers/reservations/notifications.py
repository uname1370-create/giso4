from giso.panel.modules.notifications.core import safe_log
from giso.panel.modules.notifications import log_user_notification


def _owner_phone(center) -> str:
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT phone FROM giso_web_auth WHERE id=?",
                (int(center.get("owner_user_id") or 0),),
            ).fetchone()
        return str((row["phone"] if row else "") or "")
    except Exception:
        return ""


def notify_new_reservation(reservation, center):
    # P0: اعلان هم برای ادمین (سرپرستی) و هم برای مالک مرکز (اقدام) ثبت می‌شود.
    # قبلاً فقط target_role='admin' بود و مالک در پنل خودش چیزی نمی‌دید.
    safe_log(category='beauty_centers', subcategory='new_reservation',
             title='نوبت جدید ثبت شد',
             message=f"📅 {reservation.get('user_name') or reservation.get('user_phone')}\n"
                     f"💇 {reservation.get('service_name')}\n"
                     f"📅 {reservation.get('reservation_date')} {reservation.get('reservation_time')}",
             target_role='admin', source_type='reservation',
             source_id=reservation.get('id', 0), destination='both')
    owner_phone = _owner_phone(center or {})
    if owner_phone:
        try:
            log_user_notification(
                owner_phone, 'new_reservation_owner',
                '📅 نوبت جدید برای مرکز شما',
                f"📅 {reservation.get('user_name') or reservation.get('user_phone')}\n"
                f"💇 {reservation.get('service_name')}\n"
                f"📅 {reservation.get('reservation_date')} {reservation.get('reservation_time')}\n"
                f"مشاهده: داشبورد مرکز ← تب نوبت‌ها",
                source_type='reservation_owner', source_id=reservation.get('id', 0),
                category='beauty_centers')
        except Exception:
            pass
        try:
            from giso.beauty_centers.services import _CENTER_NOTIFY_POOL, _send_center_owner_bale
            _CENTER_NOTIFY_POOL.submit(
                _send_center_owner_bale, owner_phone,
                'نوبت جدید برای مرکز شما',
                f"{reservation.get('service_name')} — {reservation.get('reservation_date')} {reservation.get('reservation_time')}",
                '/dashboard/beauty-center?tab=reservations')
        except Exception:
            pass

def notify_user_confirmed(reservation, center):
    safe_log(category='beauty_centers', subcategory='reservation_confirmed',
             title='✅ نوبت تأیید شد',
             message=f"✅ نوبت شما تأیید شد\n💇 {reservation.get('service_name')}\n"
                     f"📍 {center.get('name')}\n"
                     f"📅 {reservation.get('reservation_date')} {reservation.get('reservation_time')}\n"
                     f"💳 پرداخت حضوری",
             target_role='none', source_type='reservation',
             source_id=reservation.get('id', 0),
             recipient_id=reservation.get('user_phone', ''), destination='both')

def notify_user_rejected(reservation, center):
    safe_log(category='beauty_centers', subcategory='reservation_rejected',
             title='❌ نوبت رد شد',
             message=f"❌ نوبت شما رد شد\n"
                     f"💬 دلیل: {reservation.get('reject_reason') or '-'}",
             target_role='none', source_type='reservation',
             source_id=reservation.get('id', 0),
             recipient_id=reservation.get('user_phone', ''), destination='both')

def notify_reminder(reservation, center, hours_before):
    title = '⏰ یادآوری — فردا' if hours_before == 24 else '⏰ یادآوری — ۲ ساعت دیگه'
    message = f"⏰ {'فردا' if hours_before == 24 else '۲ ساعت دیگه'} ساعت {reservation.get('reservation_time')} نوبتتونه\n💇 {reservation.get('service_name')}\n📍 {center.get('name')}"
    safe_log(category='beauty_centers', subcategory='reservation_reminder',
             title=title, message=message, target_role='none',
             source_type='reservation', source_id=reservation.get('id', 0),
             recipient_id=reservation.get('user_phone', ''), destination='both')
