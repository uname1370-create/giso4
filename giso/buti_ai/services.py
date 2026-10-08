# -*- coding: utf-8 -*-
"""
giso/buti_ai/services.py — منطق ذخیره‌سازی نشست‌ها و ثبت در لیست انتظار آینه جادویی.
"""
import logging
from datetime import datetime
from giso.base import get_giso_db_conn, normalize_phone

logger = logging.getLogger("giso_buti_ai_services")


def save_mirror_session(user_id, service_type, city="مشهد", center_id=None,
                        conversation_id=None, status="completed"):
    """ثبت جلسه پیش‌نمایش آینه جادویی در دیتابیس."""
    try:
        conn = get_giso_db_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """
            INSERT INTO buti_ai_sessions (user_id, service_type, city, center_id, conversation_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, service_type, city, center_id, conversation_id, status, now_str)
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Error saving buti_ai session: %s", e)
        return None


def save_final_design(user_id, candidate, generation):
    """ذخیره طرح نهایی انتخاب‌شده کاربر برای رزرو/پیگیری بعدی."""
    try:
        import json

        conn = get_giso_db_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        candidate = candidate or {}
        generation = generation or {}
        cur = conn.execute(
            """
            INSERT INTO buti_ai_final_designs (
                session_id, user_id, service_type, original_filename, final_filename,
                selected_style, recommended_style, change_level, provider, model,
                status, prompt_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.get("session_id"),
                user_id,
                candidate.get("service_type") or "eyebrow",
                candidate.get("photo_filename"),
                generation.get("filename"),
                candidate.get("final_style"),
                candidate.get("recommended_style"),
                candidate.get("change_key"),
                generation.get("provider"),
                generation.get("model"),
                generation.get("status") or "created",
                json.dumps({"candidate": candidate, "generation": generation}, ensure_ascii=False),
                now_str,
            ),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Error saving buti_ai final design: %s", e)
        return None


def save_service_waitlist(user_id, phone_number, city, service_type, source="", payload=None):
    """ثبت درخواست کاربر وقتی برای خدمت انتخابی مرکز فعال نداریم."""
    try:
        import json

        clean_phone = normalize_phone(phone_number)
        if not clean_phone:
            return False, "شماره موبایل معتبر وارد کن.", None
        city = " ".join(str(city or "").split())[:80] or "مشهد"
        service_type = " ".join(str(service_type or "").split())[:60]
        if not service_type:
            return False, "نوع خدمت مشخص نیست.", None
        source = " ".join(str(source or "").split())[:80]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        conn = get_giso_db_conn()
        cur = conn.execute(
            """
            INSERT INTO buti_ai_waitlist (
                user_id, phone_number, city, service_type, source, status, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (user_id, clean_phone, city, service_type, source, payload_json, now_str),
        )
        conn.commit()
        return True, "درخواستت ثبت شد. وقتی مرکز فعال برای این خدمت اضافه شود، اطلاع می‌دهیم.", cur.lastrowid
    except Exception as e:
        logger.error("Error saving buti_ai service waitlist: %s", e)
        return False, "ثبت درخواست انجام نشد. لطفاً کمی بعد دوباره تلاش کن.", None


def waitlist_interest_count(service_type, city=""):
    """تعداد درخواست‌های باز برای یک خدمت؛ برای نمایش تقاضا و تصمیم محصول."""
    try:
        conn = get_giso_db_conn()
        service_type = str(service_type or "").strip()
        city = str(city or "").strip()
        if city:
            row = conn.execute(
                "SELECT COUNT(*) FROM buti_ai_waitlist WHERE service_type=? AND city=? AND status='open'",
                (service_type, city),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM buti_ai_waitlist WHERE service_type=? AND status='open'",
                (service_type,),
            ).fetchone()
        return int(row[0] if row else 0)
    except Exception as e:
        logger.error("Error counting buti_ai waitlist: %s", e)
        return 0


def _clean_city_service(city, service_type):
    city = " ".join(str(city or "").split())[:80] or "مشهد"
    service_type = " ".join(str(service_type or "").split())[:60]
    return city, service_type


def record_service_demand(user_id, city, service_type, source="", payload=None, dedupe_key=""):
    """ثبت تقاضای سبک/بی‌نیاز از شماره وقتی مرکز فعال برای خدمت وجود ندارد."""
    try:
        import json

        city, service_type = _clean_city_service(city, service_type)
        if not service_type:
            return False, None
        source = " ".join(str(source or "").split())[:80]
        dedupe_key = " ".join(str(dedupe_key or "").split())[:160]
        conn = get_giso_db_conn()
        if dedupe_key:
            row = conn.execute(
                "SELECT id FROM buti_ai_service_demand WHERE dedupe_key=? LIMIT 1",
                (dedupe_key,),
            ).fetchone()
            if row:
                return True, int(row[0])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        cur = conn.execute(
            """
            INSERT INTO buti_ai_service_demand (
                user_id, city, service_type, source, status, dedupe_key, payload_json, created_at
            ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (user_id, city, service_type, source, dedupe_key, payload_json, now_str),
        )
        conn.commit()
        return True, cur.lastrowid
    except Exception as e:
        logger.error("Error recording buti_ai service demand: %s", e)
        return False, None


def service_demand_count(service_type, city=""):
    """تعداد تقاضاهای ثبت‌شده بدون شماره برای آمار مدیریت."""
    try:
        conn = get_giso_db_conn()
        service_type = str(service_type or "").strip()
        city = str(city or "").strip()
        if city:
            row = conn.execute(
                "SELECT COUNT(*) FROM buti_ai_service_demand WHERE service_type=? AND city=? AND status='open'",
                (service_type, city),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM buti_ai_service_demand WHERE service_type=? AND status='open'",
                (service_type,),
            ).fetchone()
        return int(row[0] if row else 0)
    except Exception as e:
        logger.error("Error counting buti_ai service demand: %s", e)
        return 0


def total_service_interest_count(service_type, city=""):
    """جمع لیست انتظار و تقاضای سبک برای نمایش «نیاز بازار» به مدیریت."""
    return waitlist_interest_count(service_type, city) + service_demand_count(service_type, city)


def add_to_waitlist(phone_number, city, service_type):
    """ثبت شماره و تقاضای کاربر در لیست انتظار شهرستان‌ها؛ سازگار با کد قدیمی."""
    ok, _message, row_id = save_service_waitlist(
        None, phone_number, city, service_type, source="legacy_waitlist", payload={},
    )
    return row_id if ok else None


def get_final_design_by_id(design_id, user_id=None):
    """Load a final design only when its owning user is explicitly supplied."""
    try:
        import json
        if not user_id:
            return None
        conn = get_giso_db_conn()
        row = conn.execute(
            "SELECT * FROM buti_ai_final_designs WHERE id=? AND user_id=?",
            (int(design_id), int(user_id)),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            payload = json.loads(d.get("prompt_json") or "{}")
            d["candidate"] = payload.get("candidate") or {}
            d["generation"] = payload.get("generation") or {}
        except Exception:
            d["candidate"] = {}
            d["generation"] = {}
        return d
    except Exception as e:
        logger.error("Error loading final design %s: %s", design_id, e)
        return None
