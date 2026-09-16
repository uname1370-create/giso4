# -*- coding: utf-8 -*-
"""Business rules for Beauty Centers. Giso is an introduction platform only."""
from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import secrets
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from giso.base import get_giso_db_conn, normalize_phone
from giso.config import Config

logger = logging.getLogger("giso_beauty_centers")
_CENTER_NOTIFY_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="giso_beauty_owner")

CENTER_CATEGORIES = {"hair": "مو", "skin_face": "پوست و صورت", "beauty": "آرایش و زیبایی"}
CENTER_TYPES = {
    "salon": "سالن زیبایی", "hair_center": "مرکز تخصصی مو",
    "skin_beauty": "مرکز پوست و صورت", "independent": "آرایشگر یا متخصص مستقل",
    "nail_center": "مرکز خدمات ناخن", "bridal": "مرکز خدمات عروس و میکاپ",
    "licensed_clinic": "کلینیک زیبایی دارای مجوز",
}
SERVICES = {
    "haircut": "کوتاهی مو", "hair_color": "رنگ مو", "bleach": "دکلره",
    "hair_repair": "احیا و ترمیم", "keratin": "کراتین", "straightening": "صافی",
    "extension": "اکستنشن", "braid": "بافت مو", "scalp_care": "مراقبت کف سر",
    "facial": "فیشال", "skin_cleansing": "پاک‌سازی پوست", "skin_hydration": "آبرسانی پوست",
    "face_care": "مراقبت صورت", "makeup": "میکاپ", "hairstyle": "شینیون",
    "brow": "ابرو", "lash": "مژه", "nail": "ناخن", "bridal": "خدمات عروس",
}
CATEGORY_SERVICES = {
    "hair": ("haircut", "hair_color", "bleach", "hair_repair", "keratin", "straightening", "extension", "braid", "scalp_care"),
    "skin_face": ("facial", "skin_cleansing", "skin_hydration", "face_care", "brow", "lash"),
    "beauty": ("makeup", "hairstyle", "brow", "lash", "nail", "bridal"),
}
CATEGORY_CENTER_TYPES = {
    "hair": ("salon", "hair_center", "independent"),
    "skin_face": ("skin_beauty", "licensed_clinic", "independent"),
    "beauty": ("salon", "independent", "nail_center", "bridal"),
}
PRICE_LEVELS = {
    "economic": "اقتصادی", "standard": "متعادل", "premium": "ممتاز",
    "on_request": "قیمت پس از بررسی",
}

STATUS_FA = {
    "pending_review": "در انتظار بررسی", "reviewing": "در حال بررسی",
    "published": "منتشرشده", "rejected": "نیازمند اصلاح",
    "paused": "متوقف‌شده", "closed": "بسته‌شده",
}
DISCLAIMER = (
    "گیسو فقط بستر معرفی کاربران و مراکز زیبایی است و در ارائه خدمات، تعیین قیمت، "
    "پرداخت، کیفیت، نتیجه کار یا اختلاف میان طرفین نقشی ندارد. بررسی صلاحیت و انتخاب نهایی بر عهده کاربر است."
)
TERMS_VERSION = "beauty-centers-v1"
CENTER_IMAGE_MAX_BYTES = 5 * 1024 * 1024
CENTER_IMAGE_MAX_PIXELS = 20_000_000
CENTER_IMAGE_MAX_SIDE = 12_000
CENTER_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

_KEYWORD_TAGS = {
    "دکلره": ("bleach", "hair_repair"), "آسیب": ("hair_repair",),
    "موخوره": ("haircut", "hair_repair"), "خشکی": ("hair_repair", "keratin"),
    "وز": ("keratin", "straightening"), "ریزش": ("scalp_care",),
    "کف سر": ("scalp_care",), "رنگ": ("hair_color",),
    "پوست": ("facial", "skin_cleansing"), "جوش": ("facial", "skin_cleansing"),
    "پاکسازی": ("skin_cleansing",), "پاک‌سازی": ("skin_cleansing",),
}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def json_services(raw) -> list[str]:
    try:
        value = json.loads(raw or "[]") if isinstance(raw, str) else raw
        return [tag for tag in value if tag in SERVICES] if isinstance(value, list) else []
    except Exception:
        return []


def decorate_center(row, active_discount=None, feedback_summary=None, discount_service_active=None) -> dict:
    center = dict(row or {})
    center["services"] = json_services(center.get("services_json"))
    center["service_labels"] = [SERVICES[tag] for tag in center["services"]]
    center["category_label"] = CENTER_CATEGORIES.get(center.get("category"), "مو")
    center["type_label"] = CENTER_TYPES.get(center.get("center_type"), "مرکز زیبایی")
    center["price_level_label"] = PRICE_LEVELS.get(center.get("price_level"), "قیمت پس از بررسی")
    center["starting_price"] = max(0, int(center.get("starting_price") or 0))
    center["status_label"] = STATUS_FA.get(center.get("status"), center.get("status") or "—")
    center["listing_expired"] = bool(center.get("listing_expires_at") and str(center.get("listing_expires_at")) <= now_str())
    center["promotion_active"] = bool(center.get("promotion_type") and center.get("promotion_expires_at") and str(center.get("promotion_expires_at")) > now_str())
    # Legacy custom discount records are retained for audit, but no longer drive public UI.
    center["active_discount"] = dict(active_discount) if active_discount else {}
    center["feedback"] = feedback_summary or {}
    center["discount_service_active"] = bool(discount_service_active)
    # تک‌مرکز: وضعیت بسته و امتیاز را مستقیم می‌خواند؛ فهرست عمومی batch می‌فرستد.
    if center.get("id") and (feedback_summary is None or discount_service_active is None):
        try:
            with get_giso_db_conn() as conn:
                if discount_service_active is None:
                    center["discount_service_active"] = bool(conn.execute("SELECT 1 FROM beauty_center_promotions WHERE center_id=? AND package_key='discount' AND status='active' AND expires_at>datetime('now','localtime') LIMIT 1",(int(center['id']),)).fetchone())
            if feedback_summary is None:
                center["feedback"] = center_feedback_summary(int(center["id"]))
        except Exception:pass
    return center


def get_center(center_id: int) -> dict:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT * FROM beauty_centers WHERE id=?", (int(center_id),)).fetchone()
        return decorate_center(row) if row else {}
    except Exception:
        return {}


def get_center_by_slug(slug: str) -> dict:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT * FROM beauty_centers WHERE slug=?", (str(slug or ""),)).fetchone()
        return decorate_center(row) if row else {}
    except Exception:
        return {}


def get_owner_center(user_id: int) -> dict:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT * FROM beauty_centers WHERE owner_user_id=?", (int(user_id),)).fetchone()
        return decorate_center(row) if row else {}
    except Exception:
        return {}


def _slug_seed(name: str) -> str:
    value = re.sub(r"[^\w\u0600-\u06ff]+", "-", str(name or "").strip().lower(), flags=re.UNICODE)
    return value.strip("-_")[:90] or "beauty-center"


def _normalize_business_phone(value) -> str:
    raw = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    mobile = normalize_phone(raw)
    if mobile:
        return mobile
    compact = re.sub(r"[^\d+]", "", raw)
    digits = re.sub(r"\D", "", compact)
    return compact[:20] if 8 <= len(digits) <= 14 else ""


def _price_int(value) -> int:
    translated = str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    digits = re.sub(r"\D", "", translated)
    return min(10_000_000_000, int(digits or 0))


def _normalize_fields(values: dict) -> tuple[dict, str]:
    category = str(values.get("category") or "").strip()
    center_type = str(values.get("center_type") or "").strip()
    if category not in CENTER_CATEGORIES:
        return {}, "یکی از دسته‌های مو، پوست و صورت، یا آرایش و زیبایی را انتخاب کنید."
    if center_type not in CATEGORY_CENTER_TYPES[category]:
        return {}, "نوع مرکز با دسته تخصصی انتخاب‌شده سازگار نیست."
    selected = values.get("services") or []
    if isinstance(selected, str):
        selected = [selected]
    selected = list(dict.fromkeys(tag for tag in selected if tag in SERVICES))[:16]
    if any(tag not in CATEGORY_SERVICES[category] for tag in selected):
        return {}, "یکی از خدمات انتخاب‌شده با دسته مرکز مرتبط نیست."
    price_level = str(values.get("price_level") or "on_request").strip()
    if price_level not in PRICE_LEVELS:
        return {}, "سطح هزینه معتبر نیست."
    starting_price = _price_int(values.get("starting_price"))
    fields = {
        "name": " ".join(str(values.get("name") or "").split())[:160],
        "category": category, "center_type": center_type,
        "price_level": price_level, "starting_price": starting_price,
        "city": " ".join(str(values.get("city") or "").split())[:100],
        "region": " ".join(str(values.get("region") or "").split())[:150],
        "address_summary": " ".join(str(values.get("address_summary") or "").split())[:300],
        "business_phone": _normalize_business_phone(values.get("business_phone") or ""),
        "salon_phone": _normalize_business_phone(values.get("salon_phone") or ""),
        "display_phone_choice": str(values.get("display_phone_choice") or "business").strip(),
        "contact_time": " ".join(str(values.get("contact_time") or "").split())[:100],
        "description": str(values.get("description") or "").strip()[:700],
        "services_json": json.dumps(selected, ensure_ascii=False),
    }
    if not fields["name"]:
        return {}, "نام مرکز الزامی است."
    if not fields["city"]:
        return {}, "شهر مرکز الزامی است."
    if not fields["business_phone"]:
        return {}, "شماره تماس کاری معتبر الزامی است."
    if fields["display_phone_choice"] not in ("business", "salon"):
        fields["display_phone_choice"] = "business"
    # حداقل یک شماره باید در آگهی نمایش داده شود
    if fields["display_phone_choice"] == "salon" and not fields["salon_phone"]:
        return {}, "برای نمایش تلفن آرایشگاه، شماره ثابت آن را وارد کنید."
    if not selected:
        return {}, "حداقل یک خدمت را انتخاب کنید."
    return fields, ""


def save_center_image(file_storage) -> tuple[str, str]:
    """Validate by decoded content and atomically persist a metadata-free WebP."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return "", "تصویر اصلی مرکز الزامی است."
    temporary = None
    try:
        raw = file_storage.read(CENTER_IMAGE_MAX_BYTES + 1)
        if not raw:
            return "", "فایل تصویر خالی است."
        if len(raw) > CENTER_IMAGE_MAX_BYTES:
            return "", "حجم تصویر باید کمتر از ۵ مگابایت باشد."
        from PIL import Image, ImageOps
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(raw))
            source_format = str(probe.format or "").upper()
            width, height = int(probe.width or 0), int(probe.height or 0)
            if source_format not in CENTER_IMAGE_FORMATS:
                return "", "فقط تصویر واقعی JPG، PNG یا WebP پذیرفته می‌شود."
            if width < 1 or height < 1 or max(width, height) > CENTER_IMAGE_MAX_SIDE:
                return "", "طول یا عرض تصویر بیش از حد مجاز است."
            if width * height > CENTER_IMAGE_MAX_PIXELS:
                return "", "ابعاد تصویر بیش از حد بزرگ است."
            if bool(getattr(probe, "is_animated", False)) or int(getattr(probe, "n_frames", 1) or 1) != 1:
                return "", "تصویر متحرک پذیرفته نمی‌شود."
            probe.verify()

            image = Image.open(io.BytesIO(raw))
            if str(image.format or "").upper() != source_format:
                return "", "ساختار فایل تصویر معتبر نیست."
            image = ImageOps.exif_transpose(image)
            image.load()
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))

        upload_root = Path(Config.UPLOAD_FOLDER).resolve()
        directory = (upload_root / "beauty_centers").resolve()
        if upload_root not in directory.parents:
            raise ValueError("invalid beauty center upload root")
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"center_{secrets.token_hex(16)}.webp"
        output = directory / filename
        temporary = directory / f".{filename}.{secrets.token_hex(8)}.tmp"
        image.save(temporary, format="WEBP", quality=86, method=6, exif=b"")
        os.replace(temporary, output)
        temporary = None
        return f"uploads/beauty_centers/{filename}", ""
    except Exception:
        return "", "فایل تصویر معتبر نیست. فقط تصویر واقعی JPG، PNG یا WebP ارسال کنید."
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass


def create_center(owner_user_id: int, values: dict, image_path: str) -> tuple[bool, str, dict]:
    fields, error = _normalize_fields(values)
    if error:
        return False, error, {}
    if not image_path:
        return False, "تصویر اصلی مرکز الزامی است.", {}
    if not values.get("terms_accepted"):
        return False, "پذیرش قوانین معرفی مراکز الزامی است.", {}
    if get_owner_center(owner_user_id):
        return False, "برای این حساب قبلاً یک مرکز ثبت شده است.", {}
    stamp = now_str()
    temp_slug = f"pending-{secrets.token_hex(8)}"
    try:
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "INSERT INTO beauty_centers "
                "(owner_user_id,name,slug,category,center_type,price_level,starting_price,city,region,address_summary,business_phone,contact_time,"
                "description,services_json,image_path,status,terms_version,terms_accepted_at,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending_review',?,?,?,?)",
                (int(owner_user_id), fields["name"], temp_slug, fields["category"], fields["center_type"],
                 fields["price_level"], fields["starting_price"], fields["city"],
                 fields["region"], fields["address_summary"], fields["business_phone"], fields["contact_time"],
                 fields["description"], fields["services_json"], image_path, TERMS_VERSION, stamp, stamp, stamp),
            )
            center_id = int(cur.lastrowid)
            slug = f"{_slug_seed(fields['name'])}-{center_id}"
            conn.execute("UPDATE beauty_centers SET slug=? WHERE id=?", (slug, center_id))
            conn.commit()
        center = get_center(center_id)
        notify_center_admins(center)
        return True, "درخواست مرکز برای بررسی ارسال شد.", center
    except Exception as exc:
        logger.exception("create beauty center failed: %s", exc)
        return False, "ثبت درخواست مرکز ناموفق بود.", {}


def update_owner_center(center_id: int, owner_user_id: int, values: dict, image_path: str = "") -> tuple[bool, str, dict]:
    center = get_center(center_id)
    if not center or int(center.get("owner_user_id") or 0) != int(owner_user_id):
        return False, "مرکز پیدا نشد یا دسترسی ندارید.", {}
    fields, error = _normalize_fields(values)
    if error:
        return False, error, center
    # سقف ویرایش: روزی یک‌بار (مأموریت 36)
    last_edit = str(center.get("last_edit_at") or "")[:10]
    if last_edit and last_edit == now_str()[:10]:
        return False, "امروز اطلاعات را ویرایش کرده‌اید؛ ویرایش بعدی از فردا امکان‌پذیر است.", center
    # هر ویرایش نیازمند بررسی دوبارهٔ مدیریت است
    new_status = "pending_review"
    final_image = image_path or center.get("image_path") or ""
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "UPDATE beauty_centers SET name=?,category=?,center_type=?,price_level=?,starting_price=?,city=?,region=?,address_summary=?,business_phone=?,"
                "salon_phone=?,display_phone_choice=?,contact_time=?,description=?,services_json=?,image_path=?,status=?,last_edit_at=?,admin_note='',updated_at=? WHERE id=? AND owner_user_id=?",
                (fields["name"], fields["category"], fields["center_type"], fields["price_level"], fields["starting_price"],
                 fields["city"], fields["region"], fields["address_summary"],
                 fields["business_phone"], fields["salon_phone"], fields["display_phone_choice"],
                 fields["contact_time"], fields["description"], fields["services_json"],
                 final_image, new_status, now_str(), now_str(), int(center_id), int(owner_user_id)),
            )
            conn.commit()
        return True, "اطلاعات مرکز ذخیره شد و برای بررسی دوبارهٔ مدیریت ارسال شد.", get_center(center_id)
    except Exception as exc:
        logger.exception("update owner center failed: %s", exc)
        return False, "ذخیره اطلاعات مرکز ناموفق بود.", center


def set_owner_active(center_id: int, owner_user_id: int, active: bool) -> tuple[bool, str]:
    center = get_center(center_id)
    if not center or int(center.get("owner_user_id") or 0) != int(owner_user_id):
        return False, "دسترسی ندارید."
    if center.get("status") not in ("published", "paused"):
        return False, "فقط مرکز منتشرشده یا متوقف‌شده قابل تغییر است."
    status = "published" if active else "paused"
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE beauty_centers SET status=?,is_active=?,updated_at=? WHERE id=?",
                     (status, 1 if active else 0, now_str(), int(center_id)))
        conn.commit()
    return True, "مرکز دوباره نمایش داده شد." if active else "نمایش مرکز موقتاً متوقف شد."


def sitemap_centers(limit: int = 5000) -> list[dict]:
    """Return only indexable center fields for sitemap generation."""
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT slug,updated_at,published_at FROM beauty_centers "
                "WHERE status='published' AND is_active=1 AND slug<>'' "
                "ORDER BY id DESC LIMIT ?",
                (max(1, min(5000, int(limit))),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("beauty center sitemap query failed: %s", exc)
        return []


def list_public_centers(query: str = "", city: str = "", category: str = "", center_type: str = "", service: str = "", price_level: str = "", limit: int = 60) -> list[dict]:
    clauses = ["status='published'", "is_active=1", "(listing_expires_at='' OR listing_expires_at>datetime('now','localtime'))"]
    params = []
    query = str(query or "").strip()[:100]
    if query:
        clauses.append("(name LIKE ? OR description LIKE ? OR services_json LIKE ?)")
        params.extend([f"%{query}%"] * 3)
    if city:
        clauses.append("city=?"); params.append(str(city)[:100])
    if category in CENTER_CATEGORIES:
        clauses.append("category=?"); params.append(category)
    if center_type in CENTER_TYPES:
        clauses.append("center_type=?"); params.append(center_type)
    if service in SERVICES:
        clauses.append("services_json LIKE ?"); params.append(f'%"{service}"%')
    if price_level in PRICE_LEVELS:
        clauses.append("price_level=?"); params.append(price_level)
    params.append(max(1, min(100, int(limit))))
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM beauty_centers WHERE " + " AND ".join(clauses) +
                " ORDER BY CASE WHEN promotion_type='featured' AND promotion_expires_at>datetime('now','localtime') THEN 2 ELSE 0 END DESC, promotion_bumped_at DESC,is_featured DESC,sort_order DESC,published_at DESC,id DESC LIMIT ?", params,
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            feedbacks, discount_services = {}, set()
            if ids:
                marks = ",".join("?" for _ in ids)
                rating_rows=conn.execute(f"SELECT center_id,COUNT(*) count,SUM(CASE overall_level WHEN 'good' THEN 5 WHEN 'average' THEN 3 ELSE 1 END) points FROM beauty_center_feedback WHERE status='visible' AND center_id IN ({marks}) GROUP BY center_id",ids).fetchall()
                for rating in rating_rows:
                    count=int(rating['count'] or 0);score=(float(rating['points'] or 0)/count) if count else 0
                    feedbacks[int(rating['center_id'])]={"count":count,"score":round(score,1),"score100":round(score*20),"label":_feedback_label(score)}
                promo_rows=conn.execute(f"SELECT DISTINCT center_id FROM beauty_center_promotions WHERE package_key='discount' AND status='active' AND expires_at>datetime('now','localtime') AND center_id IN ({marks})",ids).fetchall()
                discount_services={int(r['center_id']) for r in promo_rows}
        return [decorate_center(row, {}, feedbacks.get(int(row["id"]), {}), int(row["id"]) in discount_services) for row in rows]
    except Exception as exc:
        logger.warning("list public centers failed: %s", exc)
        return []


def analysis_service_tags(analysis_id: int, user_id: int = 0) -> list[str]:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT type,ai_report_json FROM analyses WHERE id=? AND "
                "(user_id=? OR phone=(SELECT phone FROM giso_web_auth WHERE id=?))",
                (int(analysis_id), int(user_id or 0), int(user_id or 0)),
            ).fetchone()
        if not row:
            return []
        text = f"{row['type'] or ''} {row['ai_report_json'] or ''}".lower()
        tags = []
        for keyword, values in _KEYWORD_TAGS.items():
            if keyword in text:
                tags.extend(values)
        if not tags:
            tags.extend(("hair_repair", "haircut") if row["type"] == "hair" else ("facial", "skin_cleansing"))
        return list(dict.fromkeys(tags))
    except Exception:
        return []


def recommended_centers(analysis_id: int, user_id: int, city: str = "", limit: int = 3,
                        track_impression: bool = True) -> list[dict]:
    tags = analysis_service_tags(analysis_id, user_id)
    if not tags:
        return []
    candidates = list_public_centers(city=city, limit=100)
    scored = []
    for center in candidates:
        score = sum(1 for tag in tags if tag in center["services"])
        if score:
            center["match_tags"] = [SERVICES[tag] for tag in tags if tag in center["services"]]
            scored.append((score, int(center.get("is_featured") or 0), center))
    scored.sort(key=lambda item: (-item[0], -item[1], int(item[2]["id"])))
    result = [item[2] for item in scored[:max(1, min(3, int(limit)))]]
    if result and track_impression:
        # بهینه‌سازی N+1: به‌جای دو کوئری داخل حلقه، یک UPDATE دسته‌ای + executemany (رفتار عیناً یکسان)
        ids = [int(c["id"]) for c in result]
        uid = int(user_id or 0)
        with get_giso_db_conn() as conn:
            marks = ",".join("?" for _ in ids)
            conn.execute(f"UPDATE beauty_centers SET analysis_impressions=analysis_impressions+1 WHERE id IN ({marks})", ids)
            conn.executemany(
                "INSERT INTO beauty_center_events(center_id,event_type,user_id,created_at) VALUES (?,'analysis_impression',?,datetime('now','localtime'))",
                [(i, uid) for i in ids])
            conn.commit()
    return result


def increment_view(center_id: int):
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE beauty_centers SET views_count=views_count+1 WHERE id=? AND status='published'", (int(center_id),))
        conn.execute("INSERT INTO beauty_center_events(center_id,event_type,created_at) VALUES (?,'view',datetime('now','localtime'))",(int(center_id),))
        conn.commit()


def reveal_contact(center_id: int, user_id: int, price_inquiry: bool = False) -> tuple[bool, str]:
    if not user_id:
        return False, "برای مشاهده راه ارتباطی وارد شوید."
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT business_phone FROM beauty_centers WHERE id=? AND status='published' AND is_active=1", (int(center_id),)).fetchone()
        if not row:
            return False, "مرکز در دسترس نیست."
        owner = conn.execute("SELECT owner_user_id FROM beauty_centers WHERE id=?", (int(center_id),)).fetchone()
        if not owner or int(owner["owner_user_id"] or 0) != int(user_id):
            if price_inquiry:
                conn.execute("UPDATE beauty_centers SET contact_clicks=contact_clicks+1,price_inquiry_clicks=price_inquiry_clicks+1 WHERE id=?", (int(center_id),))
            else:
                conn.execute("UPDATE beauty_centers SET contact_clicks=contact_clicks+1 WHERE id=?", (int(center_id),))
            conn.execute("INSERT INTO beauty_center_events(center_id,event_type,user_id,created_at) VALUES (?,?,?,datetime('now','localtime'))",(int(center_id),'price_inquiry' if price_inquiry else 'contact',int(user_id)))
        conn.commit()
    return True, str(row["business_phone"] or "")


def get_or_create_conversation(center_id: int, user_id: int) -> tuple[bool, str, dict]:
    center = get_center(center_id)
    if not center or center.get("status") != "published" or not center.get("is_active"):
        return False, "مرکز برای گفتگو در دسترس نیست.", {}
    if int(center.get("owner_user_id") or 0) == int(user_id):
        return False, "مالک نمی‌تواند با مرکز خودش گفتگوی مشتری ایجاد کند.", {}
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT * FROM beauty_center_conversations WHERE center_id=? AND user_id=?",
                           (int(center_id), int(user_id))).fetchone()
        if not row:
            stamp = now_str()
            cur = conn.execute("INSERT INTO beauty_center_conversations(center_id,user_id,status,last_message_at,created_at) VALUES (?,?,'active','',?)",
                               (int(center_id), int(user_id), stamp))
            conn.execute("INSERT INTO beauty_center_events(center_id,event_type,user_id,created_at) VALUES (?,'conversation',?,?)",(int(center_id),int(user_id),stamp))
            conn.commit()
            row = conn.execute("SELECT * FROM beauty_center_conversations WHERE id=?", (cur.lastrowid,)).fetchone()
        elif row["status"] == "closed":
            conn.execute("UPDATE beauty_center_conversations SET status='active',closed_at='' WHERE id=?", (row["id"],))
            conn.commit(); row = conn.execute("SELECT * FROM beauty_center_conversations WHERE id=?", (row["id"],)).fetchone()
    return True, "", dict(row)


def conversation_for_party(conversation_id: int, user_id: int) -> tuple[dict, dict]:
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT c.*,b.owner_user_id,b.name AS center_name,b.slug FROM beauty_center_conversations c JOIN beauty_centers b ON b.id=c.center_id WHERE c.id=?", (int(conversation_id),)).fetchone()
    if not row or int(user_id) not in (int(row["user_id"]), int(row["owner_user_id"])):
        return {}, {}
    return dict(row), get_center(row["center_id"])


def conversation_messages(conversation_id: int, user_id: int) -> list[dict]:
    conversation, _center = conversation_for_party(conversation_id, user_id)
    if not conversation:
        return []
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE beauty_center_messages SET is_read=1 WHERE conversation_id=? AND sender_user_id!=?",
                     (int(conversation_id), int(user_id)))
        rows = conn.execute("SELECT * FROM beauty_center_messages WHERE conversation_id=? ORDER BY id", (int(conversation_id),)).fetchall()
        conn.commit()
    return [dict(row) for row in rows]


def notify_conversation_message(conversation: dict, sender_user_id: int, message_id: int, message_text: str):
    recipient_id = int(conversation["owner_user_id"]) if int(sender_user_id) == int(conversation["user_id"]) else int(conversation["user_id"])
    try:
        with get_giso_db_conn() as conn:
            user = conn.execute("SELECT phone FROM giso_web_auth WHERE id=?", (recipient_id,)).fetchone()
        if not user or not user["phone"]:
            return
        sender_label = "کاربر" if int(sender_user_id) == int(conversation["user_id"]) else "مرکز"
        title = f"پیام جدید {sender_label} در مراکز زیبایی"
        body = str(message_text or "")[:220]
        from giso.panel.modules.notifications import log_user_notification
        log_user_notification(user["phone"], "center_message", title, body,
                              source_type="beauty_center_message", source_id=int(message_id), category="beauty_centers")
        path = "/dashboard/beauty-center?tab=messages" if recipient_id == int(conversation["owner_user_id"]) else f"/beauty-centers/{conversation['slug']}/chat?conversation_id={conversation['id']}"
        _CENTER_NOTIFY_POOL.submit(_send_center_owner_bale, user["phone"], title, body, path)
    except Exception as exc:
        logger.debug("beauty conversation notification failed: %s", exc)


def send_conversation_message(conversation_id: int, sender_user_id: int, text: str) -> tuple[bool, str, int]:
    conversation, _center = conversation_for_party(conversation_id, sender_user_id)
    if not conversation:
        return False, "گفتگو پیدا نشد یا دسترسی ندارید.", 0
    if conversation.get("status") != "active":
        return False, "این گفتگو بسته است.", 0
    message = " ".join(str(text or "").split())[:1000]
    if not message:
        return False, "پیام خالی است.", 0
    with get_giso_db_conn() as conn:
        recent = conn.execute("SELECT COUNT(*) FROM beauty_center_messages WHERE conversation_id=? AND sender_user_id=? AND created_at>=datetime('now','localtime','-1 minute')",
                              (int(conversation_id), int(sender_user_id))).fetchone()[0]
        if recent >= 10:
            return False, "تعداد پیام‌ها زیاد است؛ یک دقیقه بعد دوباره تلاش کنید.", 0
        stamp = now_str()
        cur = conn.execute("INSERT INTO beauty_center_messages(conversation_id,sender_user_id,message_text,is_read,created_at) VALUES (?,?,?,0,?)",
                           (int(conversation_id), int(sender_user_id), message, stamp))
        conn.execute("UPDATE beauty_center_conversations SET last_message_at=? WHERE id=?", (stamp, int(conversation_id)))
        message_id = int(cur.lastrowid)
        conn.commit()
    notify_conversation_message(conversation, sender_user_id, message_id, message)
    return True, "پیام ارسال شد.", message_id


def owner_conversation_unread_count(owner_user_id:int)->int:
    with get_giso_db_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM beauty_center_messages m JOIN beauty_center_conversations c ON c.id=m.conversation_id JOIN beauty_centers b ON b.id=c.center_id WHERE b.owner_user_id=? AND m.sender_user_id!=? AND m.is_read=0",(int(owner_user_id),int(owner_user_id))).fetchone()[0] or 0)


def owner_conversations(owner_user_id: int) -> list[dict]:
    with get_giso_db_conn() as conn:
        rows = conn.execute("SELECT c.*,u.first_name,u.last_name,(SELECT message_text FROM beauty_center_messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_message,(SELECT COUNT(*) FROM beauty_center_messages m WHERE m.conversation_id=c.id AND m.sender_user_id!=? AND m.is_read=0) AS unread FROM beauty_center_conversations c JOIN beauty_centers b ON b.id=c.center_id LEFT JOIN giso_web_auth u ON u.id=c.user_id WHERE b.owner_user_id=? ORDER BY COALESCE(c.last_message_at,c.created_at) DESC",
                            (int(owner_user_id), int(owner_user_id))).fetchall()
    return [dict(row) for row in rows]


def user_center_unread_count(user_id: int) -> int:
    with get_giso_db_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM beauty_center_messages m JOIN beauty_center_conversations c ON c.id=m.conversation_id WHERE c.user_id=? AND m.sender_user_id!=? AND m.is_read=0",
            (int(user_id), int(user_id)),
        ).fetchone()[0] or 0)


def user_center_conversations(user_id: int) -> list[dict]:
    """فهرست پرسش‌وپاسخ کاربر با مراکز؛ فقط گفتگوهای متعلق به خود کاربر."""
    with get_giso_db_conn() as conn:
        rows = conn.execute(
            "SELECT c.*,b.name AS center_name,b.slug,b.city,b.region,b.image_path,b.status AS center_status,"
            "(SELECT message_text FROM beauty_center_messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_message,"
            "(SELECT sender_user_id FROM beauty_center_messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_sender_id,"
            "(SELECT COUNT(*) FROM beauty_center_messages m WHERE m.conversation_id=c.id AND m.sender_user_id!=? AND m.is_read=0) AS unread "
            "FROM beauty_center_conversations c JOIN beauty_centers b ON b.id=c.center_id "
            "WHERE c.user_id=? ORDER BY COALESCE(NULLIF(c.last_message_at,''),c.created_at) DESC",
            (int(user_id), int(user_id)),
        ).fetchall()
    return [dict(row) for row in rows]


def _feedback_label(score: float) -> str:
    score100=float(score or 0)*20
    if score100>=85:return "بسیار خوب"
    if score100>=70:return "خوب"
    if score100>=50:return "متوسط"
    return "نیازمند بهبود"


def center_feedback_summary(center_id: int) -> dict:
    with get_giso_db_conn() as conn:
        rows=conn.execute("SELECT overall_level,created_at FROM beauty_center_feedback WHERE center_id=? AND status='visible' ORDER BY id DESC",(int(center_id),)).fetchall()
    counts={"weak":0,"average":0,"good":0};points={"weak":1,"average":3,"good":5}
    for row in rows: counts[row['overall_level']]=counts.get(row['overall_level'],0)+1
    total=len(rows);score=(sum(points.get(row['overall_level'],1) for row in rows)/total) if total else 0
    return {"count":total,"score":round(score,1),"score100":round(score*20),"label":_feedback_label(score),"counts":counts}


def submit_center_feedback(conversation_id:int,user_id:int,values:dict)->tuple[bool,str]:
    conv,center=conversation_for_party(conversation_id,user_id)
    if not conv or int(conv['user_id'])!=int(user_id): return False,"فقط کاربر گفتگو می‌تواند بازخورد ثبت کند."
    levels={"weak","average","good"}; overall=str(values.get('overall_level') or '')
    if overall not in levels:return False,"یکی از گزینه‌های خوب، متوسط یا ضعیف را انتخاب کنید."
    with get_giso_db_conn() as conn:
        got=conn.execute("SELECT 1 FROM beauty_center_messages WHERE conversation_id=? AND sender_user_id=? LIMIT 1",(int(conversation_id),int(center['owner_user_id']))).fetchone()
        if not got:return False,"پس از دریافت پاسخ مرکز می‌توانید بازخورد ثبت کنید."
        try:conn.execute("INSERT INTO beauty_center_feedback(center_id,conversation_id,user_id,response_level,price_level,overall_level,comment,status,created_at) VALUES (?,?,?,?,?,?,?,'pending',datetime('now','localtime'))",(int(center['id']),int(conversation_id),int(user_id),overall,overall,overall,''));conn.commit()
        except Exception:return False,"بازخورد این گفتگو قبلاً ثبت شده است."
    return True,"بازخورد ثبت شد و پس از بررسی نمایش داده می‌شود."


def close_conversation(conversation_id: int, user_id: int) -> tuple[bool, str]:
    conversation, _center = conversation_for_party(conversation_id, user_id)
    if not conversation:
        return False, "گفتگو پیدا نشد."
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE beauty_center_conversations SET status='closed',closed_at=? WHERE id=?", (now_str(), int(conversation_id)))
        conn.commit()
    return True, "گفتگو بسته شد."


def process_center_expiry_notifications() -> int:
    """ارسال یک‌باره یادآوری‌های ۷، ۳، ۱ روز و انقضا؛ فراخوانی امن و idempotent."""
    sent=0
    with get_giso_db_conn() as conn:
        rows=conn.execute("SELECT * FROM beauty_centers WHERE status='published' AND listing_expires_at<>'' AND listing_expires_at<=datetime('now','localtime','+7 days')").fetchall()
        for raw in rows:
            center=decorate_center(raw)
            days=int(conn.execute("SELECT CAST(julianday(?) - julianday(datetime('now','localtime')) AS INTEGER)",(center['listing_expires_at'],)).fetchone()[0] or 0)
            key='expired' if days<=0 else ('d1' if days<=1 else ('d3' if days<=3 else 'd7'))
            try:conn.execute("INSERT INTO beauty_center_expiry_notices(center_id,notice_key,created_at) VALUES (?,?,datetime('now','localtime'))",(center['id'],key))
            except Exception:continue
            notify_center_owner(center,title="یادآوری اعتبار آگهی مرکز",message=("اعتبار ۳۰ روزه آگهی شما پایان یافت." if days<=0 else f"{max(1,days)} روز تا پایان اعتبار آگهی شما باقی مانده است."));sent+=1
        # یادآوری یک‌باره بازخورد پس از ۴۸ ساعت سکوت گفتگو.
        reminders=conn.execute("SELECT c.id,c.center_id,c.user_id,b.name,b.slug,u.phone FROM beauty_center_conversations c JOIN beauty_centers b ON b.id=c.center_id JOIN giso_web_auth u ON u.id=c.user_id WHERE COALESCE(c.last_message_at,c.created_at)<=datetime('now','localtime','-48 hours') AND EXISTS(SELECT 1 FROM beauty_center_messages m WHERE m.conversation_id=c.id AND m.sender_user_id=b.owner_user_id) AND NOT EXISTS(SELECT 1 FROM beauty_center_feedback f WHERE f.conversation_id=c.id)").fetchall()
        for r in reminders:
            key=f"feedback_{r['id']}"
            try:conn.execute("INSERT INTO beauty_center_expiry_notices(center_id,notice_key,created_at) VALUES (?,?,datetime('now','localtime'))",(r['center_id'],key))
            except Exception:continue
            try:
                from giso.panel.modules.notifications import log_user_notification
                log_user_notification(r['phone'],'center_feedback','ثبت بازخورد مرکز',f"اگر گفتگوی شما با {r['name']} تمام شده، تجربه خود را ثبت کنید.",source_type='beauty_center_feedback_reminder',source_id=r['id'],category='beauty_centers')
                _CENTER_NOTIFY_POOL.submit(_send_center_owner_bale,r['phone'],'ثبت بازخورد مرکز',f"تجربه ارتباط با {r['name']} را ثبت کنید.",f"/beauty-centers/{r['slug']}/chat?conversation_id={r['id']}")
                sent+=1
            except Exception:pass
        conn.commit()
    return sent


def _purchase_key(prefix: str, owner_user_id: int, nonce: str) -> str:
    """Build a stable idempotency key from a server-rendered form nonce."""
    import re
    clean = str(nonce or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{32}", clean):
        return ""
    return f"{prefix}:{int(owner_user_id)}:{clean}"


def _wait_label(seconds) -> str:
    seconds=max(0,int(seconds or 0))
    if seconds>=86400:return f"{(seconds+86399)//86400} روز"
    if seconds>=3600:return f"{(seconds+3599)//3600} ساعت"
    return f"{max(1,(seconds+59)//60)} دقیقه"


def center_promotion_availability(center: dict) -> dict:
    """Read-only UI state; purchase functions repeat every check atomically."""
    result={key:{"allowed":False,"message":""} for key in ("bump","featured","discount","renew")}
    if not center or center.get('status')!='published' or not center.get('is_active'):
        for value in result.values():value["message"]="فقط برای آگهی فعال"
        return result
    with get_giso_db_conn() as conn:
        anchor=center.get('published_at') or center.get('created_at') or now_str()
        bump_wait=conn.execute("SELECT MAX(0,CAST((julianday(datetime(?,'+24 hours'))-julianday(datetime('now','localtime')))*86400 AS INTEGER))",(anchor,)).fetchone()[0]
        last_bump=conn.execute("SELECT created_at FROM beauty_center_promotions WHERE center_id=? AND package_key='bump' AND status='active' ORDER BY id DESC LIMIT 1",(int(center['id']),)).fetchone()
        if last_bump:
            bump_wait=max(int(bump_wait or 0),int(conn.execute("SELECT MAX(0,CAST((julianday(datetime(?,'+24 hours'))-julianday(datetime('now','localtime')))*86400 AS INTEGER))",(last_bump['created_at'],)).fetchone()[0] or 0))
        result['bump']={"allowed":int(bump_wait or 0)<=0,"message":"قابل فعال‌سازی" if int(bump_wait or 0)<=0 else f"{_wait_label(bump_wait)} تا فعال‌شدن"}
        for package in ('featured','discount'):
            active=conn.execute("SELECT expires_at FROM beauty_center_promotions WHERE center_id=? AND package_key=? AND status='active' AND expires_at>datetime('now','localtime') ORDER BY id DESC LIMIT 1",(int(center['id']),package)).fetchone()
            wait=int(conn.execute("SELECT MAX(0,CAST((julianday(?)-julianday(datetime('now','localtime')))*86400 AS INTEGER))",(active['expires_at'],)).fetchone()[0] or 0) if active else 0
            result[package]={"allowed":not bool(active),"message":f"هنوز {_wait_label(wait)} اعتبار دارد" if active else "قابل فعال‌سازی"}
        expiry=center.get('listing_expires_at') or ''
        remaining=float(conn.execute("SELECT COALESCE(julianday(NULLIF(?,''))-julianday(datetime('now','localtime')),0)",(expiry,)).fetchone()[0] or 0)
        result['renew']={"allowed":remaining<=10,"message":f"{max(0,int(remaining+0.999))} روز تا پایان؛ قابل تمدید" if remaining<=10 else f"تمدید از ۱۰ روز مانده فعال می‌شود؛ {int(remaining+0.999)} روز باقی است"}
    return result


def renew_center_listing(owner_user_id:int, nonce: str = "")->tuple[bool,str]:
    center=get_owner_center(owner_user_id)
    if not center:return False,"مرکز پیدا نشد."
    try:
        from giso_admin import get_giso_config
        price=int(get_giso_config('beauty_renew_price','50000') or 50000)
    except Exception:price=50000
    from giso.marketplace.services import _debit_buyer_feature
    key=_purchase_key('beauty_renew', owner_user_id, nonce)
    if not key:return False,"درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
    with get_giso_db_conn() as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            live=conn.execute("SELECT id,status,is_active,listing_expires_at FROM beauty_centers WHERE owner_user_id=?",(int(owner_user_id),)).fetchone()
            if not live or live['status']!='published' or not live['is_active']:conn.rollback();return False,"فقط آگهی فعال قابل تمدید است."
            remaining=float(conn.execute("SELECT COALESCE(julianday(NULLIF(?,''))-julianday(datetime('now','localtime')),0)",(live['listing_expires_at'],)).fetchone()[0] or 0)
            if remaining>10:conn.rollback();return False,f"تمدید فقط از ۱۰ روز مانده فعال می‌شود؛ {int(remaining+0.999)} روز باقی است."
            previous=conn.execute("SELECT id FROM wallet_transactions WHERE idempotency_key IN (?,?) LIMIT 1",(key+':spend',key+':cash')).fetchone()
            if previous:conn.rollback();return True,"این تمدید قبلاً ثبت شده است."
            ok,msg=_debit_buyer_feature(owner_user_id,price,key,"تمدید ۳۰ روزه آگهی مرکز",conn)
            if not ok:conn.rollback();return False,msg
            conn.execute("UPDATE beauty_centers SET status='published',is_active=1,listing_expires_at=CASE WHEN listing_expires_at>datetime('now','localtime') THEN datetime(listing_expires_at,'+30 days') ELSE datetime('now','localtime','+30 days') END,updated_at=datetime('now','localtime') WHERE id=?",(live['id'],));conn.execute("DELETE FROM beauty_center_expiry_notices WHERE center_id=?",(center['id'],));conn.commit();return True,"آگهی مرکز برای ۳۰ روز تمدید شد."
        except Exception:conn.rollback();return False,"تمدید آگهی ناموفق بود."


def purchase_center_promotion(owner_user_id:int,package_key:str,nonce: str = "")->tuple[bool,str]:
    center=get_owner_center(owner_user_id)
    if not center or center.get('status')!='published' or not center.get('is_active'):return False,"فقط آگهی فعال قابل ارتقا است."
    try:
        from giso_admin import get_giso_config
        prices={"bump":int(get_giso_config('beauty_bump_price','25000') or 25000),"featured":int(get_giso_config('beauty_featured_price','120000') or 120000),"discount":int(get_giso_config('beauty_discount_price','60000') or 60000)}
    except Exception:prices={"bump":25000,"featured":120000,"discount":60000}
    if package_key not in prices:return False,"بسته نامعتبر است."
    try:
        from giso_admin import get_giso_config
        enabled=str(get_giso_config('beauty_promotions_enabled','1') or '1')=='1'
        package_enabled=str(get_giso_config(f'beauty_{package_key}_enabled','1') or '1')=='1'
    except Exception:enabled=package_enabled=True
    if not enabled or not package_enabled:return False,"این بسته فعلاً غیرفعال است."
    key=_purchase_key(f'beauty_promo_{package_key}', owner_user_id, nonce)
    if not key:return False,"درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
    if package_key=='bump':days=0
    elif package_key=='discount':days=1
    else:days=7
    from giso.marketplace.services import _debit_buyer_feature
    with get_giso_db_conn() as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            live=conn.execute("SELECT id,status,is_active,published_at,created_at FROM beauty_centers WHERE owner_user_id=?",(int(owner_user_id),)).fetchone()
            if not live or live['status']!='published' or not live['is_active']:conn.rollback();return False,"فقط آگهی فعال قابل ارتقا است."
            if package_key=='bump':
                last=conn.execute("SELECT created_at FROM beauty_center_promotions WHERE center_id=? AND package_key='bump' AND status='active' ORDER BY id DESC LIMIT 1",(live['id'],)).fetchone()
                anchor=(last['created_at'] if last else (live['published_at'] or live['created_at']))
                wait=int(conn.execute("SELECT MAX(0,CAST((julianday(datetime(?,'+24 hours'))-julianday(datetime('now','localtime')))*86400 AS INTEGER))",(anchor,)).fetchone()[0] or 0)
                if wait>0:conn.rollback();return False,f"نردبان هنوز فعال نیست؛ {_wait_label(wait)} دیگر دوباره تلاش کنید."
            elif package_key in ('featured','discount'):
                active=conn.execute("SELECT expires_at FROM beauty_center_promotions WHERE center_id=? AND package_key=? AND status='active' AND expires_at>datetime('now','localtime') ORDER BY id DESC LIMIT 1",(live['id'],package_key)).fetchone()
                if active:
                    wait=int(conn.execute("SELECT MAX(0,CAST((julianday(?)-julianday(datetime('now','localtime')))*86400 AS INTEGER))",(active['expires_at'],)).fetchone()[0] or 0)
                    conn.rollback();return False,f"این گزینه هنوز {_wait_label(wait)} اعتبار دارد و دوباره قابل خرید نیست."
            previous=conn.execute("SELECT id FROM beauty_center_promotions WHERE transaction_key=? LIMIT 1",(key,)).fetchone()
            if previous:conn.rollback();return True,"این ارتقا قبلاً ثبت شده است."
            ok,msg=_debit_buyer_feature(owner_user_id,prices[package_key],key,"افزایش دیده‌شدن آگهی مرکز",conn)
            if not ok:conn.rollback();return False,msg
            expires='' if not days else conn.execute("SELECT datetime('now','localtime',?)",(f'+{days} days',)).fetchone()[0]
            if package_key=='featured':
                conn.execute("UPDATE beauty_centers SET promotion_type='featured',promotion_expires_at=?,promotion_bumped_at=datetime('now','localtime') WHERE id=?",(expires,int(center['id'])))
            elif package_key=='bump':
                conn.execute("UPDATE beauty_centers SET promotion_bumped_at=datetime('now','localtime') WHERE id=?",(int(center['id']),))
            conn.execute("INSERT INTO beauty_center_promotions(center_id,owner_user_id,package_key,amount,starts_at,expires_at,transaction_key,status,created_at) VALUES (?,?,?,?,datetime('now','localtime'),?,?,'active',datetime('now','localtime'))",(int(center['id']),int(owner_user_id),package_key,prices[package_key],expires,key));conn.commit();return True,"افزایش دیده‌شدن فعال شد."
        except Exception:conn.rollback();return False,"فعال‌سازی ناموفق بود."


def admin_set_status(center_id: int, status: str, note: str = "", actor_id: int = 0) -> tuple[bool, str, dict]:
    if status not in STATUS_FA:
        return False, "وضعیت نامعتبر است.", {}
    center = get_center(center_id)
    if not center:
        return False, "مرکز پیدا نشد.", {}
    stamp = now_str()
    published_at = stamp if status == "published" and not center.get("published_at") else center.get("published_at") or ""
    try:
        from giso_admin import get_giso_config
        listing_days=max(1,min(365,int(get_giso_config('beauty_listing_days','30') or 30)))
    except Exception:listing_days=30
    with get_giso_db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT status,updated_at FROM beauty_centers WHERE id=?", (int(center_id),)).fetchone()
        if not current or str(current["status"] or "") != str(center.get("status") or "") or str(current["updated_at"] or "") != str(center.get("updated_at") or ""):
            conn.rollback()
            return False, "این پرونده هم‌زمان توسط مدیر دیگری تغییر کرد؛ صفحه را تازه‌سازی کنید.", get_center(center_id)
        conn.execute(
            "UPDATE beauty_centers SET status=?,is_active=?,admin_note=?,published_at=?,listing_expires_at=CASE WHEN ?='published' THEN datetime('now','localtime',?) ELSE listing_expires_at END,updated_at=? WHERE id=?",
            (status, 1 if status == "published" else int(center.get("is_active") or 0), str(note or "")[:500], published_at, status, f'+{listing_days} days', stamp, int(center_id)),
        )
        conn.commit()
    updated = get_center(center_id)
    if status == "published" and center.get("status") != "published":
        try:
            from giso.wallet import complete_mission
            complete_mission(int(updated["owner_user_id"]), "beauty_center_published",
                             event_key=f"center:{int(center_id)}:published")
        except Exception:
            pass
    notify_center_owner(updated, title="وضعیت مرکز زیبایی", message=f"وضعیت «{updated['name']}» به {updated['status_label']} تغییر کرد.")
    return True, "وضعیت مرکز به‌روزرسانی شد.", updated


def list_admin_centers(status: str = "", limit: int = 200) -> list[dict]:
    sql = "SELECT c.*,u.name AS owner_name,u.phone AS owner_phone FROM beauty_centers c LEFT JOIN giso_web_auth u ON u.id=c.owner_user_id"
    params = []
    if status in STATUS_FA:
        sql += " WHERE c.status=?"; params.append(status)
    sql += " ORDER BY CASE c.status WHEN 'pending_review' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END,c.id DESC LIMIT ?"
    params.append(max(1, min(500, int(limit))))
    with get_giso_db_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [decorate_center(row) for row in rows]


def notify_center_admins(center: dict):
    try:
        from giso.panel.modules.notifications import safe_log
        safe_log("beauty_centers", "center_new", "درخواست مرکز زیبایی جدید",
                 f"مرکز #{center.get('id')} — {center.get('name')} — {center.get('city')}",
                 target_role="both", source_type="beauty_center_new", source_id=center.get("id"),
                 destination="site")
    except Exception as exc:
        logger.debug("beauty center admin notification failed: %s", exc)
    try:
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.panel.modules import notifications as notification_module
        token = (_token_from_env() or _token_from_db() or "").strip()
        if not token:
            return
        center_id = int(center.get("id") or 0)
        markup = {"inline_keyboard": [[
            {"text": "🔍 بررسی", "callback_data": f"bc_act|{center_id}|review|0"},
            {"text": "✅ انتشار", "callback_data": f"bc_act|{center_id}|publish|0"},
            {"text": "❌ رد", "callback_data": f"bc_act|{center_id}|reject|0"},
        ]]}
        text = (f"🏥 درخواست مرکز زیبایی جدید\n━━━━━━━━━━━━━━━━\n"
                f"نام: {html.escape(str(center.get('name') or '—'))}\nنوع: {html.escape(str(center.get('type_label') or '—'))}\n"
                f"📍 {html.escape(str(center.get('city') or '—'))}، {html.escape(str(center.get('region') or '—'))}\n"
                f"خدمات: {html.escape('، '.join(center.get('service_labels') or []) or '—')}")
        targets = notification_module._super_admin_ids() | notification_module._regular_admin_ids()
        for target in targets:
            _http_post(f"https://tapi.bale.ai/bot{token}/sendMessage",
                       json_payload={"chat_id": int(target), "text": text, "parse_mode": "HTML",
                                     "reply_markup": markup})
    except Exception as exc:
        logger.debug("beauty center Bale admin notification failed: %s", exc)


def _send_center_owner_bale(phone: str, title: str, message: str, path: str = "/dashboard/beauty-center"):
    try:
        from giso.base import _http_post, _token_from_db, _token_from_env
        normalized = normalize_phone(phone or "")
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT bale_id FROM giso_users WHERE phone=? AND contact_shared=1 LIMIT 1", (normalized,)).fetchone()
            site_row = conn.execute("SELECT value FROM giso_config WHERE key='site_base_url'").fetchone()
        if not row or not str(row["bale_id"] or "").isdigit():
            return
        token = (_token_from_env() or _token_from_db() or "").strip()
        if not token:
            return
        site = str(site_row["value"] or "https://gisosadeghi.ir").rstrip("/") if site_row else "https://gisosadeghi.ir"
        body = (f"🏥 {html.escape(title)}\n━━━━━━━━━━━━━━━━\n{html.escape(message)}\n\n"
                f"🔗 {site}{path}")
        _http_post(f"https://tapi.bale.ai/bot{token}/sendMessage",
                   json_payload={"chat_id": int(row["bale_id"]), "text": body, "parse_mode": "HTML"})
    except Exception as exc:
        logger.debug("beauty center owner Bale notification failed: %s", exc)


def notify_center_owner(center: dict, title: str, message: str):
    try:
        with get_giso_db_conn() as conn:
            owner = conn.execute("SELECT phone FROM giso_web_auth WHERE id=?", (int(center.get("owner_user_id") or 0),)).fetchone()
        if not owner:
            return
        # Same proven site+Bale transport, with a dedicated Beauty Centers category.
        from giso.panel.modules.notifications import log_user_notification
        log_user_notification(owner["phone"], "center_status", title, message,
                              source_type=f"beauty_center_{center.get('status')}", source_id=center.get("id"), category="beauty_centers")
        try:
            _CENTER_NOTIFY_POOL.submit(_send_center_owner_bale, owner["phone"], title, message)
        except Exception:
            pass
    except Exception as exc:
        logger.debug("beauty center owner notification failed: %s", exc)


__all__ = [
    "CENTER_CATEGORIES", "CENTER_TYPES", "SERVICES", "CATEGORY_SERVICES", "CATEGORY_CENTER_TYPES",
    "PRICE_LEVELS", "STATUS_FA", "DISCLAIMER", "TERMS_VERSION",
    "CENTER_IMAGE_MAX_BYTES", "CENTER_IMAGE_MAX_PIXELS", "CENTER_IMAGE_MAX_SIDE", "CENTER_IMAGE_FORMATS",
    "decorate_center", "get_center", "get_center_by_slug", "get_owner_center",
    "save_center_image", "create_center", "update_owner_center", "set_owner_active",
    "list_public_centers", "sitemap_centers", "recommended_centers", "analysis_service_tags",
    "increment_view", "reveal_contact", "get_or_create_conversation", "conversation_for_party",
    "conversation_messages", "send_conversation_message", "notify_conversation_message", "owner_conversations",
    "user_center_conversations", "user_center_unread_count", "close_conversation", "admin_set_status", "list_admin_centers",
]
