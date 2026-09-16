# -*- coding: utf-8 -*-
"""
giso/channel_importer.py — ایمپورت هوشمند محصول از کانال بله به فروشگاه گیسو.

جریان:
    پست جدید در کانال → خواندن کپشن/عکس → پارس هوشمند (regex + AI)
    → ثبت محصول «در انتظار» در products → پیش‌نمایش به ادمین‌ها در ربات
    → تأیید با دکمه اینلاین → انتشار در فروشگاه (بدون دخالت سوپرادمین)

دسترسی: فقط ادمین‌های گیسو (سوپرادمین یا عضو giso_admins) می‌توانند تأیید/رد کنند.
"""
import json
import logging
import re
from datetime import datetime

from giso.money import format_toman

logger = logging.getLogger("giso_channel_importer")

# نقشه کلمات کلیدی → دسته‌بندی استاندارد فروشگاه (کلمات امن، بدون زیررشته‌های خطرناک مثل «مو»)
_CAT_KEYWORDS = {
    "hair":  ["شامپو", "ماسک مو", "سرم مو", "روغن آرگان", "ضدریزش", "موخوره", "موها", "موی "],
    "face":  ["ضدآفتاب", "فوم شست", "تونر", "آبرسان", "جوش"],
    # کالاهای بهداشتی زنانه/عمومی (شیاف، بهداشت بانوان، واژن، رحم، عفونت…)
    "beauty": ["رژ", "آرایش", "ریمل", "خط چشم", "شیاف", "بهداشت", "واژن", "واژ", "رحم",
               "رحمی", "عفونت", "بانوان", "زنانه", "بانو", "قاعدگی", "پریود"],
    "body":  ["لوسیون بدن", "صابون", "بادی اسپلش", "اسکراب بدن", "نرم کننده بدن"],
    "care":  ["خمیر دندان", "خمیردندان", "مسواک", "دئودورانت", "بوگیر", "پدیکور", "مانیکور",
              "بیوتی بلندر", "پد تخم مرغی", "بهداشت دهان"],
    # خوراکی/تغذیه (تغذیهٔ زیبایی، سفارش خاص — در فروشگاه عمومی نمایش داده نمی‌شود)
    "nutrition": ["دمنوش", "چای ترش", "عرق ", "عسل", "روغن زیتون", "آبلیمو", "آبغوره", "سرکه",
                  "شربت", "ادویه", "زعفران", "شیره", "تخم خرفه", "شیر بادام", "بیدمشک", "اسطوخودوس",
                  "گلاب", "گردو", "بادام", "سنجد", "عناب", "خرما", "کیک", "بیسکوئیت", "گرانو",
                  "روغن خوراکی", "بلغور", "آرد ", "نخود", "کشکش", "شیرینی"],
}
# کلمات عمومی پوست/کرم که باید بعد از تشخیص خوراکی بررسی شوند (تا «کرم دست» غذایی اشتباه نشود)
_FACE_GENERIC = ["پوست", "صورت", "کرم"]
# اگر این کلمات آمد یعنی قطعاً خوراکی است (میان کلمات مشترک مثل «سرم/روغن» اولویت دارد)
_NUTRITION_STRONG = ["دمنوش", "چای ترش", "عرق ", "عسل", "روغن زیتون", "آبلیمو", "آبغوره",
                     "سرکه", "شربت", "ادویه", "زعفران", "تخم خرفه", "شیر بادام", "بیدمشک",
                     "اسطوخودوس", "سنجد", "عناب", "بیسکوئیت", "گرانو", "کیک ", "چای "]
OOS_MARKERS = ["ناموجود", "تمام شد", "اتمام موجودی", "نامـوجود"]

# حذف ایموجی/نمادها از نام محصول
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u200d\ufe0f✅❌⛔⚠️🔥💰📦📸🖼💊✨👉👇🫶😊😌😍🤍🫦🦋🧹🌿👑🌙☑️🔴💯]+",
    flags=re.UNICODE,
)

# خطوط کپشن که مربوط به تماس/سفارش/قیمت عمده تأمین‌کننده‌اند و نباید در توضیح سایت بیایند
_SUPPLIER_LINE_MARKERS = (
    "@", "سفارش", "همکار", "تلگرام", "اینستاگرام", "واتساپ", "واتس اپ", "پیام بد",
    "دایرکت", "تماس", "شماره", "پشتیبان", "ادمین", "t.me", "http", "www.",
    "مشاوره", "بازاریاب", "پخش", "عمده فروش",
)

_CB_PREFIX = "chimp"  # پیشوند callback دکمه‌ها

# برچسبی که به توضیح محصول فاقد قیمت اضافه می‌شود — هنگام انتشار پاک می‌شود
PRICE_MISSING_NOTE = "\n\n⚠️ قیمت به‌صورت خودکار تشخیص داده نشد — قبل از انتشار در پنل اصلاح کنید."


# ══════════════════ ابزارهای کمکی ══════════════════

def _fa2en(s: str) -> str:
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(str(fa.index(c)) if c in fa else c for c in (s or ""))


def get_shop_channel_id() -> str:
    """آیدی کانال فروشگاه (ذخیره‌شده توسط سوپرادمین در پنل/bot)."""
    try:
        from giso_admin import get_giso_config
        return (get_giso_config("bale_channel_id", "") or "").strip()
    except Exception as e:
        logger.warning(f"get_shop_channel_id: {e}")
        return ""


def _is_shop_channel(msg) -> bool:
    """آیا پست متعلق به کانال فروشگاه ثبت‌شده است؟"""
    ref = get_shop_channel_id()
    if not ref or not getattr(msg, "chat", None):
        return False
    cands = {str(msg.chat.id)}
    if getattr(msg.chat, "username", None):
        cands.add("@" + msg.chat.username.lower())
    return ref.lstrip("@").lower() in {c.lstrip("@").lower() for c in cands}


def _parse_price(text: str) -> int:
    """استخراج قیمت تومان از کپشن (الگوهای رایج فارسی کانال‌های فروش)."""
    t = _fa2en(text)
    # نرمال‌سازی جداکننده‌ها: ممیز هزار می‌تواند «, ٬ ، /» باشد
    t = t.replace("٬", ",").replace("،", ",").replace("/", ",")
    # 1) «۶۳ هزار تومان / ۳۵۰ هزار ت / ۶۳هزارتومان» → عدد × ۱۰۰۰
    m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*)?\s*([0-9]{1,4})\s*هزار\s*(?:تومان|تومن|ت\.?|ت\s)", t)
    if m:
        try:
            whole = (m.group(1) or "").replace(",", "")
            part = m.group(2)
            val = int((whole or "") + part)
            if val > 0:
                return val * 1000
        except (ValueError, IndexError):
            pass
    # 2) الگوهای کامل: «قیمت: ۴۲۰٬۰۰۰ تومان» یا «... تومان»
    patterns = [
        r"قیمت[^0-9]{0,12}([0-9][0-9,]{2,})",
        r"([0-9][0-9,]{3,})\s*(?:تومان|ت\s?ومان|تومن)",
        r"([0-9][0-9,]{3,})\s*(?:هزار\s)?ت[.\s]",
        r"([0-9][0-9,]{4,})",  # عدد خام ≥۵ رقم (مثلاً «قیمت 810,000» بدون واحد)
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            try:
                val = int(m.group(1).replace(",", ""))
                if val > 1000:
                    return val
            except (ValueError, IndexError):
                continue
    return 0


def _parse_category(text: str) -> str:
    """دسته‌بندی با اولویت و امتیازدهی: خوراکی ابتدا (کلیدهای قوی)، سپس دسته‌های آرایشی.

    کلمات مشترک مثل «روغن/سرم» بین آرایشی و خوراکی هستند؛ اگر نشانهٔ قویِ خوراکی
    (دمنوش/عسل/عرق/آبلیمو…) بود، خوراکی برنده است تا «روغن زیتون» موی پوست نشود.
    """
    t = text or ""
    # 1) نشانهٔ قوی خوراکی → تغذیه
    if any(k in t for k in _NUTRITION_STRONG):
        return "nutrition"
    # 2) امتیاز دسته‌های آرایشی/بهداشتی (کلیدهای تخصصی؛ کلمات عمومیِ کرم/پوست وزن کم)
    scores = {}
    for cat, keys in _CAT_KEYWORDS.items():
        if cat == "nutrition":
            continue
        scores[cat] = sum(1 for k in keys if k in t)
    # کلمات عمومی فقط وقتی امتیاز بدهند که دسته تخصصی دیگری برنده نشده باشد
    generic = sum(1 for k in _FACE_GENERIC if k in t)
    best = max(scores, key=scores.get) if scores else ""
    if scores.get(best, 0) > 0:
        return best
    if generic > 0:
        return "face"
    return "hair"


def is_nutrition_product(text: str) -> bool:
    """آیا این پست خوراکی/تغذیه است (تا در فروشگاه عمومی منتشر نشود)؟"""
    return _parse_category(text) == "nutrition"


_SUBCAT_PATTERNS = [
    r"زیر\s?دسته\s*[:：]\s*([^\n،,؛;]+)",
    r"زیرگروه\s*[:：]\s*([^\n،,؛;]+)",
    r"نوع\s*محصول\s*[:：]\s*([^\n،,؛;]+)",
]


def _parse_subcategory(text: str) -> str:
    """استخراج زیردسته از کپشن (regex ساده — اگر نبود خالی می‌ماند)."""
    for pat in _SUBCAT_PATTERNS:
        m = re.search(pat, text or "", re.I)
        if m:
            val = m.group(1).strip().strip("*_#").strip()
            if 2 <= len(val) <= 60:
                return val
    return ""


def _strip_emoji(s: str) -> str:
    s = _EMOJI_RE.sub(" ", s or "")
    return re.sub(r"\s{2,}", " ", s).strip()


def _is_supplier_line(line: str) -> bool:
    """خطوط تماس/سفارش/قیمت عمده تأمین‌کننده که نباید در فروشگاه دیده شوند."""
    low = line.replace("‌", " ")
    return any(mark in low for mark in _SUPPLIER_LINE_MARKERS)


def _clean_name(text: str) -> str:
    """نام محصول = اولین خط معنادار کپشن (بدون ایموجی، هشتگ، خطوط تماس)."""
    for line in (text or "").splitlines():
        line = line.strip().strip("*_").strip()
        if not line or line.startswith("#") or _is_supplier_line(line):
            continue
        # حذف پیشوندهای رایج
        line = re.sub(r"^(نام محصول|محصول|نام)\s*[:：]\s*", "", line)
        line = _strip_emoji(line)
        if 3 <= len(line) <= 120:
            return line
    return _strip_emoji((text or "").strip().splitlines()[0][:100]) if text else "محصول کانال"


async def _ai_parse(caption: str) -> dict:
    """اگر regex به قیمت نرسید، از ai_brain گیسو برای استخراج JSON استفاده می‌کنیم."""
    try:
        from giso.ai_brain import ask_ai_fast
        prompt = (
            "این متن یک پست فروشگاهی محصول آرایشی/مراقبتی است. "
            "خروجی را فقط به صورت JSON بده با کلیدهای: "
            "name (نام محصول), price (قیمت تومان به عدد، اگر نبود 0), "
            "category (یکی از hair, face, beauty), "
            "subcategory (زیردسته یا نوع دقیق‌تر محصول مثل شامپو/ماسک/سرم/کرم/ضدآفتاب؛ "
            "اگر در متن نبود رشته خالی \"\"), "
            "summary (یک جمله توضیح کوتاه). "
            "بدون هیچ متن اضافه. متن پست:\n" + caption[:1200]
        )
        raw = await ask_ai_fast([{"role": "user", "content": prompt}]) or ""
        # فاز اصلاح: خروجی AI ممکن است dict/list باشد (نه str) → نرمال به رشته قبل از regex
        if not isinstance(raw, str):
            try:
                raw = json.dumps(raw, ensure_ascii=False)
            except Exception:
                raw = str(raw)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            data = json.loads(m.group(0))
            return {
                "name": str(data.get("name", ""))[:120],
                "price": int(data.get("price") or 0),
                "category": str(data.get("category", "hair")).lower(),
                "subcategory": str(data.get("subcategory", ""))[:60],
                "summary": str(data.get("summary", ""))[:300],
            }
    except Exception as e:
        logger.info(f"ai_parse fallback (no ai): {e}")
    return {}


async def parse_post(caption: str) -> dict:
    """پارس نهایی: اول regex (سریع/مجانی)، در صورت نیاز AI."""
    caption = caption or ""
    name = _clean_name(caption)
    price = _parse_price(caption)
    category = _parse_category(caption)
    subcategory = _parse_subcategory(caption)
    summary = ""
    if not price:
        ai = await _ai_parse(caption)
        if ai:
            name = ai.get("name") or name
            price = ai.get("price") or 0
            category = ai.get("category") or category
            subcategory = ai.get("subcategory") or subcategory
            summary = ai.get("summary") or ""
    # توضیح سایت: فقط خطوط معنادار، بدون هشتگ و بدون خطوط تماس/سفارش/قیمت عمده تأمین‌کننده
    desc_lines = []
    for l in caption.splitlines():
        l = l.strip()
        if not l or l.startswith("#") or _is_supplier_line(l):
            continue
        desc_lines.append(_strip_emoji(l))
    description = summary or (" ".join(desc_lines[:4])[:300])
    in_stock = not any(m in caption for m in OOS_MARKERS)
    return {"name": name, "price": price, "category": category,
            "subcategory": subcategory, "description": description, "in_stock": in_stock}


# ══════════════════ ذخیره‌سازی ══════════════════

def _make_slug(name: str) -> str:
    import re as _re
    s = _re.sub(r"[^\w\u0600-\u06FF]+", "-", (name or "").strip())
    return _re.sub(r"-{2,}", "-", s).strip("-")[:120]


def _channel_msg_exists(channel_msg_id: str) -> bool:
    from giso.base import get_giso_db_conn
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT id FROM products WHERE channel_msg_id=? AND source='channel'",
            (channel_msg_id,),
        ).fetchone()
        return row is not None


def _insert_pending_product(parsed: dict, channel_msg_id: str, image_path: str,
                            status: str = "pending") -> int:
    """ثبت محصول در products (giso.db) با وضعیت داده‌شده.

    status: 'pending' (در انتظار تأیید ادمین) یا 'special_order' (خوراکی/تغذیه —
    در فروشگاه عمومی نمایش داده نمی‌شود، فقط سفارش خاص با توصیهٔ AI).
    """
    from giso.base import get_giso_db_conn
    try:
        from giso.models import migrate_giso_tables
        migrate_giso_tables()
    except Exception:
        pass
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price_fa_note = "" if parsed["price"] else PRICE_MISSING_NOTE
    with get_giso_db_conn() as conn:
        try:
            # فاز P2: ثبت زیردسته — اگر ستون وجود نداشت (قدیمی)، fallback بدون زیردسته
            cur = conn.execute(
                """INSERT INTO products
                   (name, description, price, image_path, in_stock, category, subcategory,
                    slug, views, source, channel_msg_id, publish_status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    parsed["name"][:180],
                    (parsed["description"] + price_fa_note)[:600],
                    parsed["price"],
                    image_path or "",
                    1 if parsed["in_stock"] else 0,
                    parsed["category"][:60],
                    (parsed.get("subcategory") or "")[:60],
                    _make_slug(parsed["name"]),
                    0,
                    "channel",
                    channel_msg_id,
                    status,
                    now,
                    now,
                ),
            )
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            cur = conn.execute(
                """INSERT INTO products
                   (name, description, price, image_path, in_stock, category,
                    slug, views, source, channel_msg_id, publish_status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    parsed["name"][:180],
                    (parsed["description"] + price_fa_note)[:600],
                    parsed["price"],
                    image_path or "",
                    1 if parsed["in_stock"] else 0,
                    parsed["category"][:60],
                    _make_slug(parsed["name"]),
                    0,
                    "channel",
                    channel_msg_id,
                    status,
                    now,
                    now,
                ),
            )
        conn.commit()
        return int(cur.lastrowid)


async def _download_photo_as_webp(bot, photo_size) -> str:
    """دانلود عکس پست کانال و ذخیره WebP در پوشه آپلود فروشگاه."""
    try:
        from giso.config import Config
        from PIL import Image
        from io import BytesIO
        import os
        f = await bot.get_file(photo_size.file_id)
        data = bytes(await f.download_as_bytearray())
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        fname = f"ch_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.webp"
        full = os.path.join(Config.UPLOAD_FOLDER, fname)
        img = Image.open(BytesIO(data)).convert("RGB")
        img.thumbnail((900, 900))
        img.save(full, "WEBP", quality=82, method=6)
        return "uploads/" + fname
    except Exception as e:
        logger.warning(f"channel photo download failed: {e}")
        return ""


def _target_admin_ids() -> set:
    """گیرندگان پیام تأیید: ادمین‌های بلهٔ گیسو (از bot.db) + سوپرادمین‌های اصلی."""
    ids = set()
    try:
        from giso_admin import list_giso_admins
        for a in list_giso_admins():
            bid = str(a.get("bale_id") or a.get("telegram_id") or "").strip()
            if bid.isdigit():
                ids.add(int(bid))
    except Exception as e:
        logger.debug(f"list admins err: {e}")
    try:
        from giso.base import _load_main_admin_ids
        for a in _load_main_admin_ids():
            try:
                ids.add(int(str(a).strip()))
            except (TypeError, ValueError):
                pass
    except Exception as e:
        logger.debug(f"main admins err: {e}")
    return ids


def _fa_num(n) -> str:
    try:
        from giso.base import _fa_num as f
        return f(n)
    except Exception:
        return str(n)


# ══════════════════ هندلرها ══════════════════

async def on_channel_post(update, context):
    """هندلر پست جدید کانال فروشگاه — ثبت در انتظار + ارسال پیش‌نمایش به ادمین‌ها."""
    msg = getattr(update, "channel_post", None) or getattr(update, "message", None)
    if not msg or not _is_shop_channel(msg):
        return
    caption = (getattr(msg, "caption", None) or getattr(msg, "text", None) or "").strip()
    if not caption or caption.startswith("/"):
        return

    channel_msg_id = str(getattr(msg, "message_id", "") or "")
    if not channel_msg_id:
        return
    try:
        if _channel_msg_exists(channel_msg_id):
            logger.info(f"channel post {channel_msg_id} already imported, skip")
            return
    except Exception as e:
        logger.debug(f"dedupe check err: {e}")

    # دانلود عکس (اگر هست)
    image_path = ""
    photos = getattr(msg, "photo", None) or []
    if photos:
        image_path = await _download_photo_as_webp(context.bot, photos[-1])

    parsed = await parse_post(caption)
    # خوراکی/تغذیه → «سفارش خاص» (در فروشگاه عمومی نمایش داده نمی‌شود؛ فقط AI در برنامهٔ تغذیه پیشنهاد می‌دهد)
    is_food = parsed.get("category") == "nutrition"
    try:
        pid = _insert_pending_product(parsed, channel_msg_id, image_path,
                                      status=("special_order" if is_food else "pending"))
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("channel", "post", "پست جدید کانال", f"«{parsed.get('name', 'محصول')}» در انتظار بررسی است.",
                     source_type="channel_post", source_id=pid)
            if not image_path:
                safe_log("channel", "post_no_photo", "⚠️ پست کانال بدون عکس",
                         f"«{parsed.get('name', 'محصول')}» بدون عکس است — از بات (دکمه «🖼 تعویض عکس» در کارت تأیید) یا پنل وب عکس را اضافه کنید.",
                         source_type="channel_post", source_id=pid)
        except Exception as exc:
            logger.exception("channel notification event failed: %s", exc)
    except Exception as e:
        logger.error(f"insert pending product failed: {e}", exc_info=True)
        return

    # حالت انتشار: خودکار → فوراً published؛ با تأیید (پیش‌فرض) → پیش‌نمایش به ادمین‌ها
    try:
        from giso.shop import get_publish_mode
        mode = get_publish_mode()
    except Exception:
        mode = "review"

    if mode == "auto" and parsed["price"] > 0 and not is_food:
        try:
            from giso.base import get_giso_db_conn
            with get_giso_db_conn() as conn:
                conn.execute(
                    "UPDATE products SET publish_status='published', updated_at=? WHERE id=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pid),
                )
                conn.commit()
            await _send_auto_notice_to_admins(context, pid, parsed, image_path=image_path)
            logger.info(f"channel product #{pid} auto-published (msg {channel_msg_id})")
            return
        except Exception as e:
            logger.warning(f"auto publish failed, fallback to review: {e}")

    # پیش‌نمایش به ادمین‌ها (حالت تأیید — پیش‌فرض امن)
    await _send_preview_to_admins(context, pid, parsed, image_path)
    logger.info(f"channel product #{pid} imported as pending (msg {channel_msg_id})")


async def _send_auto_notice_to_admins(context, pid: int, parsed: dict, image_path: str = ""):
    """اطلاع انتشار خودکار: بدون دکمه، برای اطلاع‌رسانی به ادمین‌ها."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    price_txt = format_toman(parsed["price"]) if parsed["price"] else "⚠️ نامشخص"
    photo_txt = "🖼 عکس: ✅ دارد" if image_path else "🖼 عکس: ⚠️ ندارد — از پنل وب ← تب محصولات اضافه کنید"
    text = (
        f"🟢 منتشر شد (حالت خودکار)\n"
        f"🏷 {parsed['name']}\n"
        f"💰 {price_txt}\n"
        f"{photo_txt}\n"
        f"🆔 {_fa_num(pid)}\n\n"
        "از پنل وب ← تب محصولات می‌توانید ویرایش/حذف/افزودن عکس کنید."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 حذف فوری", callback_data=f"{_CB_PREFIX}|del|{pid}"),
    ]])
    for cid in _target_admin_ids():
        try:
            # Keep the established superadmin action; normal admins only receive
            # an informational auto-publish notice and cannot delete the product.
            from giso.base import is_super_admin
            recipient_kb = kb if is_super_admin(cid) else None
            await context.bot.send_message(chat_id=cid, text=text, reply_markup=recipient_kb)
        except Exception as e:
            logger.debug(f"auto notice to {cid}: {e}")


async def _send_preview_to_admins(context, pid: int, parsed: dict, image_path: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    cat_fa = {"hair": "مراقبت مو", "face": "مراقبت پوست", "beauty": "زیبایی"}.get(parsed["category"], parsed["category"])
    sub_txt = f"\n🗂 زیردسته: {parsed.get('subcategory', '')}" if parsed.get("subcategory") else ""
    price_txt = format_toman(parsed["price"]) if parsed["price"] else "⚠️ نامشخص — قبل از انتشار اصلاح شود"
    stock_txt = "✅ موجود" if parsed["in_stock"] else "⛔ ناموجود"
    photo_txt = "🖼 عکس: ✅ دارد" if image_path else "🖼 عکس: ⚠️ ندارد — قبل از انتشار از دکمه «🖼 تعویض عکس» در کارت تأیید یا پنل وب اضافه کنید"
    text = (
        f"📦 محصول جدید از کانال (در انتظار تأیید)\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏷 نام: {parsed['name']}\n"
        f"📂 دسته: {cat_fa}{sub_txt}\n"
        f"💰 قیمت: {price_txt}\n"
        f"📦 موجودی: {stock_txt}\n"
        f"{photo_txt}\n"
        f"📝 توضیح: {parsed['description'][:160]}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 شناسه: {_fa_num(pid)}\n\n"
        "✅ (تأیید و انتشار در فروشگاه) بدون نیاز به سوپرادمین."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ انتشار در فروشگاه", callback_data=f"{_CB_PREFIX}|pub|{pid}"),
        InlineKeyboardButton("❌ رد و حذف", callback_data=f"{_CB_PREFIX}|del|{pid}"),
    ], [
        InlineKeyboardButton("✏️ ویرایش از پنل وب", callback_data=f"{_CB_PREFIX}|edit|{pid}"),
        InlineKeyboardButton("📸 پیش‌نمایش کپشن", callback_data=f"{_CB_PREFIX}|view|{pid}"),
    ]])
    restricted_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ انتشار", callback_data=f"shop_pen|pub|{pid}|0"),
        InlineKeyboardButton("❌ رد", callback_data=f"shop_pen|rej|{pid}|0"),
    ]])
    for cid in _target_admin_ids():
        try:
            from giso.base import is_super_admin
            # Superadmin keeps the original four actions.  A normal admin can
            # only approve/reject the already-imported pending post.
            recipient_kb = kb if is_super_admin(cid) else restricted_kb
            if image_path:
                from giso.config import Config
                import os
                full = os.path.join(Config.GISO_DIR, "static", image_path)
                if os.path.exists(full):
                    with open(full, "rb") as fh:
                        await context.bot.send_photo(chat_id=cid, photo=fh, caption=text, reply_markup=recipient_kb)
                    continue
            await context.bot.send_message(chat_id=cid, text=text, reply_markup=recipient_kb)
        except Exception as e:
            logger.debug(f"preview to {cid}: {e}")


def _is_channel_admin(uid: int) -> bool:
    try:
        from giso.base import is_super_admin
        if is_super_admin(uid):
            return True
    except Exception:
        pass
    try:
        from giso_admin import is_giso_admin
        return bool(is_giso_admin(user_id=uid))
    except Exception as e:
        logger.debug(f"is_giso_admin err: {e}")
        return False


async def on_channel_callback(query, context, uid: int) -> bool:
    """مدیریت دکمه‌های اینلاین تأیید/رد محصول کانال. خروجی: True یعنی هندل شد."""
    data = query.data or ""
    if not data.startswith(_CB_PREFIX + "|"):
        return False
    parts = data.split("|")
    if len(parts) != 3:
        return False
    action, pid_s = parts[1], parts[2]
    try:
        pid = int(pid_s)
    except ValueError:
        return False

    if not _is_channel_admin(uid):
        await query.answer("⛔ فقط ادمین گیسو می‌تواند این مورد را تأیید کند.", show_alert=True)
        return True

    from giso.base import get_giso_db_conn
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT id, name, publish_status FROM products WHERE id=? AND source='channel'",
            (pid,),
        ).fetchone()
        if not row:
            await query.answer("⚠️ محصول پیدا نشد (شاید قبلاً حذف شده).", show_alert=True)
            return True
        name = row["name"]

        if action == "pub":
            price_row = conn.execute("SELECT price FROM products WHERE id=?", (pid,)).fetchone()
            if not price_row or not price_row["price"]:
                await query.answer(
                    "⚠️ قیمت این محصول صفر است. اول از پنل وب (تب محصولات) قیمت را وارد و بعد انتشار بدهید.",
                    show_alert=True)
                return True
            conn.execute(
                "UPDATE products SET publish_status='published', description=REPLACE(description, ?, ''), updated_at=? WHERE id=?",
                (PRICE_MISSING_NOTE, now, pid),
            )
            conn.commit()
            await query.answer("✅ در فروشگاه منتشر شد!")
            try:
                await query.edit_message_caption(
                    caption=(f"🟢 «{name}» منتشر شد.\n"
                             f"اکنون در فروشگاه گیسو قابل خرید است."))
            except Exception:
                try:
                    await query.edit_message_text(f"🟢 «{name}» منتشر شد.")
                except Exception:
                    pass
            return True

        if action == "del":
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            await query.answer("🗑 حذف شد.")
            try:
                await query.edit_message_caption(caption=f"⛔ محصول «{name}» رد و حذف شد.")
            except Exception:
                try:
                    await query.edit_message_text(f"⛔ محصول «{name}» رد و حذف شد.")
                except Exception:
                    pass
            return True

        if action == "view":
            await query.answer("🖼 کپشن محصول در پیام بالایی همین گفتگوست.", show_alert=False)
            return True

        if action == "edit":
            await query.answer(
                "✏️ برای ویرایش دقیق (قیمت/توضیح/دسته): پنل وب گیسو ← تب «📦 محصولات» ← همین محصول را ویرایش و سپس از دکمه ✅ اینجا منتشر کنید.",
                show_alert=True)
            return True

    return True


__all__ = [
    "PRICE_MISSING_NOTE",
    "on_channel_post",
    "on_channel_callback",
    "parse_post",  # async
    "get_shop_channel_id",
    "_is_shop_channel",
]
