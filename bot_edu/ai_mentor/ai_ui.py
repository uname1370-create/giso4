"""
ai_ui.py — کیبوردهای «یار هوشمند شغلی».

⚠️ نکتهٔ مهم دربارهٔ پیشوند callback:
پیشوند `ai_` قبلاً کاملاً توسط «پنل مدیریت پروایدرهای AI» گرفته شده و در
handlers.py با شرط `d.startswith(("ai_", "a_ai_"))` به مسیر ادمین می‌رود.
اگر این ماژول هم از `ai_` استفاده می‌کرد، همهٔ دکمه‌های کاربر عادی پشت گاردِ
`if not is_admin(user): return` می‌افتاد و برای کاربر کار نمی‌کرد.
به همین دلیل پیشوند اختصاصی **`aim_`** (AI Mentor) انتخاب شد.

وابستگی: ui (فقط btn/mkb/back_btn/home_btn)، ai_db و stdlib.
"""
from core import fa_num
from ui import btn, mkb, back_btn, home_btn

from . import ai_db

# ========================= کاربر =========================

def ai_main_user_kb(has_active_path: bool = False):
    """منوی اصلی یار هوشمند — چیدمان بازطراحی‌شده.

    ردیف اول بسته به داشتن مسیر فعال، «ادامه» یا «شروع» را نشان می‌دهد.
    «یادگیری با AI» و «تنظیمات» حذف شدند؛ محتوایشان به «راهنما و تعرفه»
    و «پروفایل» منتقل شده است.
    """
    first = ([btn("🎯 ادامه مسیر من", "aim_continue")]
             if has_active_path else
             [btn("🚀 شروع مسیر جدید", "aim_start")])
    return mkb([
        first,
        [btn("🔥 ترندهای بازار", "aim_trends"),
         btn("🎤 شبیه‌ساز مصاحبه", "aim_interview_sim")],
        [btn("💼 مأموریت‌های واقعی", "aim_real_missions"),
         btn("👥 یادگیری تیمی", "aim_team_learning")],
        [btn("💳 شارژ اعتبار", "aim_buy"),
         btn("📋 راهنما و تعرفه", "aim_guide_pricing")],
        [btn("👤 پروفایل و پیشرفت من", "aim_profile")],
        home_btn(),
    ])


# ========================= فاز ۳ =========================

def ai_profile_kb():
    """پروفایل — مرکز همهٔ امکانات شخصی کاربر."""
    return mkb([
        [btn("✏️ ویرایش اطلاعات", "aim_edit_profile"),
         btn("🗂 مدیریت مسیرها", "aim_paths")],
        [btn("📄 گزارش آمادگی شغلی", "aim_reports")],
        [btn("🎓 ساخت رزومه", "aim_certs"),
         btn("🌐 پروفایل عمومی", "aim_public_profile")],
        [btn("👯‍♂️ شبیه‌سازی همزاد شغلی", "aim_career_twin")],
        [btn("💬 چت با منتور", "aim_chat"),
         btn("💰 موجودی من", "aim_balance")],
        back_btn("aim_menu"),
    ])


def ai_edit_profile_kb():
    """انتخاب فیلد برای ویرایش."""
    return mkb([
        [btn("📝 نام و نام خانوادگی", "aim_edit_field|name")],
        [btn("🎂 سن", "aim_edit_field|age"),
         btn("🏙 شهر", "aim_edit_field|city")],
        back_btn("aim_profile"),
    ])


def ai_paths_kb(paths):
    """مدیریت مسیرها — ادامه یا بایگانی هر مسیر."""
    rows = []
    for p in paths[:10]:
        icon = {"active": "▶️", "completed": "✅"}.get(p["status"], "📦")
        rows.append([btn(f"{icon} {p['target_job'][:30]}",
                         f"aim_path_view|{p['id']}")])
    if not rows:
        rows.append([btn("— هنوز مسیری نساخته‌اید —", "aim_noop")])
    rows.append([btn("🚀 شروع مسیر جدید", "aim_start")])
    rows.append(back_btn("aim_profile"))
    return mkb(rows)


def ai_path_manage_kb(path_id, status):
    rows = []
    if status == "active":
        rows.append([btn("🎯 ادامهٔ این مسیر", "aim_continue")])
        rows.append([btn("📦 بایگانی مسیر", f"aim_path_archive|{path_id}")])
    else:
        rows.append([btn("♻️ فعال‌کردن دوباره", f"aim_path_activate|{path_id}")])
        rows.append([btn("🗑 حذف مسیر", f"aim_path_delete|{path_id}")])
    rows.append([btn("📄 گزارش این مسیر", f"aim_report_path|{path_id}")])
    rows.append(back_btn("aim_paths"))
    return mkb(rows)


# ========================= فاز ۴ =========================

def ai_missions_kb(missions, done_ids=()):
    """فهرست مأموریت‌های واقعی."""
    rows = []
    for m in missions[:12]:
        mark = "✅" if m["id"] in done_ids else "💼"
        rows.append([btn(
            f"{mark} {m['title'][:30]} — {fa_num(m['reward_credits'])} اعتبار",
            f"aim_mission_view|{m['id']}")])
    if not rows:
        rows.append([btn("— فعلاً مأموریتی تعریف نشده —", "aim_noop")])
    rows.append([btn("📋 ارسال‌های من", "aim_my_missions")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def ai_mission_detail_kb(mission_id, can_submit=True):
    rows = []
    if can_submit:
        rows.append([btn("✍️ ارسال کار انجام‌شده", f"aim_mission_do|{mission_id}")])
    rows.append(back_btn("aim_real_missions"))
    return mkb(rows)


def ai_team_kb(has_team: bool, team_id=None):
    if not has_team:
        return mkb([
            [btn("🔎 پیدا کردن تیم", "aim_team_join")],
            back_btn("aim_menu"),
        ])
    return mkb([
        [btn("👥 اعضای تیم", f"aim_team_members|{team_id}")],
        [btn("🤖 بازخورد پیشرفت تیم", f"aim_team_feedback|{team_id}")],
        [btn("🚪 خروج از تیم", f"aim_team_leave|{team_id}")],
        back_btn("aim_menu"),
    ])


def ai_public_profile_kb(is_public: bool):
    return mkb([
        [btn("🔴 غیرعمومی کردن" if is_public else "🟢 عمومی کردن",
             "aim_pub_toggle")],
        [btn("📝 ویرایش معرفی کوتاه", "aim_pub_bio")],
        [btn("👁 پیش‌نمایش کارفرما", "aim_pub_preview")],
        back_btn("aim_profile"),
    ])


def ai_admin_missions_kb(missions):
    """مدیریت مأموریت‌های واقعی — ادمین."""
    rows = [[btn("➕ تعریف مأموریت جدید", "aim_a_mission_add")]]
    for m in missions[:12]:
        icon = "🟢" if m["status"] == "active" else "🔴"
        rows.append([
            btn(f"{icon} {m['title'][:26]} ({fa_num(m['reward_credits'])})",
                f"aim_a_mission_tog|{m['id']}"),
            btn("🗑", f"aim_a_mission_del|{m['id']}"),
        ])
    if len(rows) == 1:
        rows.append([btn("— مأموریتی ثبت نشده —", "aim_noop")])
    rows.append(back_btn("aim_a_menu"))
    return mkb(rows)


def ai_reports_kb(paths, reports_count=None):
    """فهرست مسیرها برای تولید یا مشاهدهٔ گزارش."""
    rows = []
    for p in paths[:10]:
        icon = {"active": "▶️", "completed": "✅"}.get(p["status"], "📦")
        rows.append([btn(f"{icon} {p['target_job'][:32]}",
                         f"aim_report_path|{p['id']}")])
    if not rows:
        rows.append([btn("— هنوز مسیری نساخته‌اید —", "aim_noop")])
    rows.append(back_btn("aim_profile"))
    return mkb(rows)


def ai_report_path_kb(path_id, has_previous=False):
    rows = [[btn("🆕 تولید گزارش جدید", f"aim_report_new|{path_id}")]]
    if has_previous:
        rows.append([btn("📚 مشاهدهٔ گزارش‌های قبلی", f"aim_report_list|{path_id}")])
    rows.append(back_btn("aim_reports"))
    return mkb(rows)


def ai_certs_kb(certs):
    rows = []
    for c in certs[:10]:
        rows.append([btn(f"🎓 {c['target_job'][:30]} — {c['certificate_id']}",
                         f"aim_cert_get|{c['id']}")])
    if not rows:
        rows.append([btn("— هنوز گواهینامه‌ای ندارید —", "aim_noop")])
    rows.append(back_btn("aim_profile"))
    return mkb(rows)


def ai_interview_start_kb(paths, has_active=False):
    """انتخاب شغل هدف برای شبیه‌سازی مصاحبه."""
    rows = []
    if has_active:
        rows.append([btn("▶️ ادامهٔ مصاحبهٔ نیمه‌تمام", "aim_sim_resume")])
    for p in paths[:6]:
        rows.append([btn(f"🎯 {p['target_job'][:34]}", f"aim_sim_go|{p['id']}")])
    rows.append([btn("✍️ نوشتن شغل دلخواه", "aim_sim_custom")])
    rows.append([btn("📊 نتایج مصاحبه‌های قبلی", "aim_sim_history")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def ai_sim_answer_kb():
    """حین مصاحبه — امکان رد کردن سؤال یا لغو."""
    return mkb([
        [btn("⏭ رد کردن این سؤال", "aim_sim_skip")],
        [btn("🛑 پایان زودهنگام", "aim_sim_stop")],
    ])


def ai_twin_kb():
    return mkb([
        [btn("🔄 شبیه‌سازی دوباره", "aim_career_twin_run")],
        back_btn("aim_profile"),
    ])


def fa_digits(n) -> str:
    """عدد فارسی با جداکنندهٔ هزارگان — از همان تابع استاندارد پروژه.

    core.fa_num از جداکنندهٔ فارسی «٬» (U+066C) استفاده می‌کند، نه کامای
    لاتین. برای یکدستی با بقیهٔ متن‌های ربات همان را صدا می‌زنیم.
    """
    return fa_num(n)


def price_label(price: int) -> str:
    """نمایش خوانای قیمت: مضرب هزار → «۵۰ هزار تومان»."""
    try:
        p = int(price)
    except Exception:
        return str(price)
    if p and p % 1000 == 0:
        return f"{fa_digits(p // 1000)} هزار تومان"
    return f"{fa_digits(p)} تومان"


def ai_pricing_kb():
    """بسته‌های اعتباری — کاملاً داینامیک از جدول ai_credit_packages.

    هیچ مقدار ثابتی در کد نیست؛ ادمین از پنل مدیریت بسته‌ها را
    اضافه/حذف/غیرفعال می‌کند.
    """
    rows = []
    for p in ai_db.list_credit_packages(only_active=True):
        rows.append([btn(
            f"💎 {fa_digits(p['amount'])} اعتبار — {price_label(p['price'])}",
            f"aim_pack|{p['id']}",
        )])
    if not rows:
        rows.append([btn("— فعلاً بسته‌ای تعریف نشده —", "aim_noop")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def ai_trends_kb(trends=None, view: str = "list"):
    """ترندهای تعاملی (فاز ۲): فیلتر نما + افزودن هر مهارت به مسیر."""
    rows = []
    # نوار فیلتر — نمای فعلی با ✅ مشخص می‌شود
    rows.append([
        btn(("✅ " if view == "list" else "") + "📊 لیست ساده", "aim_trends|list"),
        btn(("✅ " if view == "growth" else "") + "📈 نمودار رشد", "aim_trends|growth"),
    ])
    rows.append([
        btn(("✅ " if view == "full" else "") + "📝 جزئیات کامل", "aim_trends|full"),
    ])
    for t in (trends or [])[:8]:
        rows.append([btn(f"➕ افزودن «{t['skill_name']}» به مسیر",
                         f"aim_add_trend|{t['skill_name']}")])
    rows.append([btn("🔄 به‌روزرسانی فهرست", "aim_trends_refresh")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def spark(points) -> str:
    """نمودار متنی کوچک از روند تقاضا."""
    if not points or len(points) < 2:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(points), max(points)
    if hi == lo:
        return bars[3] * len(points)
    return "".join(bars[int((p - lo) / (hi - lo) * (len(bars) - 1))] for p in points)


def ai_path_progress_kb(steps):
    """فهرست گام‌های مسیر با نشانگر وضعیت."""
    rows = []
    for s in steps:
        icon = {"completed": "✅", "active": "▶️", "locked": "🔒"}.get(s.get("status"), "⬜")
        title = (s.get("title") or "")[:38]
        if s.get("status") == "locked":
            rows.append([btn(f"{icon} {title}", "aim_locked")])
        else:
            rows.append([btn(f"{icon} {title}", f"aim_step|{s['id']}")])
    rows.append([btn("📄 گزارش آمادگی شغلی", "aim_report")])
    rows.append([btn("🔁 شروع مسیر جدید", "aim_start")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def ai_challenge_kb(step_id, step_type="ai_challenge", course_id="",
                    has_exercise=False):
    """دکمه‌های یک گام.

    گام‌های نوع lesson هم می‌توانند تمرین داشته باشند (معماری تطبیقی)،
    پس دکمهٔ ارسال پاسخ برای آن‌ها هم نمایش داده می‌شود.
    """
    rows = []
    if step_type == "ai_challenge" or (step_type == "lesson" and has_exercise):
        rows.append([btn("✍️ ارسال پاسخ تمرین", f"aim_answer|{step_id}")])
    elif step_type == "course" and course_id:
        rows.append([btn("📚 رفتن به دوره", f"course|{course_id}")])
    # فاز ۲ — کمک آگاه‌از‌زمینه در همین گام
    rows.append([btn("💡 نیاز به کمک دارم", f"aim_chat_help|{step_id}")])
    rows.append([btn("✅ انجام شد", f"aim_done|{step_id}")])
    rows.append(back_btn("aim_continue"))
    return mkb(rows)


def ai_help_kb(step_id):
    """دکمه‌های صفحهٔ کمک."""
    return mkb([
        [btn("💬 پرسش دیگر", f"aim_chat_help|{step_id}")],
        [btn("🧹 پاک‌کردن تاریخچهٔ این گام", f"aim_help_clear|{step_id}")],
        back_btn(f"aim_step|{step_id}"),
    ])


def pricing_info_text() -> str:
    """متن تعرفه‌ها — از ai_settings خوانده می‌شود (فاز ۲، بهبود ۴)."""
    s = ai_db.all_ai_settings()

    def _c(key):
        v = s.get(key, "0")
        try:
            n = int(float(v))
        except Exception:
            n = 0
        return "رایگان" if n == 0 else f"{fa_num(n)} اعتبار"

    return (
        "📋 تعرفه‌های استفاده از یار هوشمند:\n"
        f"  • شروع مسیر جدید: {_c('price_roadmap')}\n"
        f"  • هر چالش: {_c('price_challenge')}\n"
        f"  • چت با منتور: {_c('price_chat')}\n"
        f"  • کمک حین آموزش: {_c('price_help')}\n"
        f"  • گزارش آمادگی: {_c('price_report')}\n"
        f"  • شبیه‌ساز مصاحبه: {_c('price_interview_sim')}\n"
        f"  • همزاد شغلی: {_c('price_twin')}\n"
        f"  • مشاهدهٔ ترندها: {_c('price_trends')}"
    )


def ai_pricing_info_kb():
    """کیبورد خرید اعتبار به‌همراه نمایش تعرفه‌ها."""
    return ai_pricing_kb()


def ai_settings_kb():
    return mkb([
        [btn("💰 مشاهدهٔ موجودی و تعرفه", "aim_balance")],
        [btn("🗂 مسیرهای قبلی من", "aim_history")],
        back_btn("aim_menu"),
    ])


def ai_learn_kb():
    return mkb([
        [btn("💬 چت با منتور", "aim_chat")],
        [btn("🔥 مهارت‌های ترند", "aim_trends")],
        back_btn("aim_menu"),
    ])


def ai_buy_hint_kb():
    """وقتی اعتبار کافی نیست."""
    return mkb([
        [btn("💳 شارژ اعتبار هوشمند", "aim_buy")],
        back_btn("aim_menu"),
    ])


def ai_pack_confirm_kb(pkg_id):
    """صفحهٔ پرداخت یک بسته — ارسال فیش یا بازگشت."""
    return mkb([
        [btn("📤 ارسال فیش پرداخت", f"aim_fiche|{pkg_id}")],
        back_btn("aim_buy"),
    ])


# ========================= ادمین =========================

def ai_admin_kb():
    """منوی مدیریت یار هوشمند (پیشوند aim_a_)."""
    return mkb([
        [btn("⚙️ تنظیمات هستهٔ AI", "aim_a_core"),
         btn("💰 تعرفه و اعتبار", "aim_a_pricing")],
        [btn("🤖 مدیریت مدل‌های AI", "aim_a_model_routing"),
         btn("📈 مدیریت ترندهای بازار", "aim_a_trends")],
        [btn("📚 محتوای یادگیری", "aim_a_content")],
        [btn("👥 مانیتورینگ کاربران", "aim_a_monitor"),
         btn("📊 گزارش هزینهٔ API", "aim_a_reports")],
        [btn("💰 مدیریت بسته‌های اعتبار", "aim_a_packs")],
        [btn("📝 مدیریت مأموریت‌های واقعی", "aim_a_missions")],
        [btn("💳 اطلاعات پرداخت", "aim_a_payment_info"),
         btn(_pending_label(), "aim_a_pending_purchases")],
        back_btn("a_panel"),
    ])


def _pending_label() -> str:
    """برچسب دکمهٔ فیش‌ها با شمارندهٔ در انتظار."""
    try:
        n = len(ai_db.get_pending_purchases(99))
    except Exception:
        n = 0
    return f"📬 فیش‌های در انتظار ({fa_num(n)})" if n else "📬 فیش‌های در انتظار"


def model_routing_admin_kb(routes=None):
    """فهرست ۶ اکشن با مدل فعلی — کلیک = ویرایش."""
    rows = []
    for r in (routes if routes is not None else ai_db.list_model_routing()):
        icon = "🟢" if r.get("is_active") else "🔴"
        label = ai_db.ACTION_FA.get(r["action_type"], r["action_type"])
        model = (r.get("primary_model") or "—").split(":")[-1][:22]
        rows.append([btn(f"{icon} {label} — {model}",
                         f"aim_a_route_view|{r['action_type']}")])
    if not rows:
        rows.append([btn("— تنظیمی ثبت نشده —", "aim_noop")])
    rows.append(back_btn("aim_a_menu"))
    return mkb(rows)


def model_routing_edit_kb(action_type: str):
    return mkb([
        [btn("✏️ مدل اصلی", f"aim_a_route_set|{action_type}|primary")],
        [btn("🔁 مدل‌های جایگزین", f"aim_a_route_set|{action_type}|fallback")],
        [btn("💵 هزینهٔ تقریبی", f"aim_a_route_set|{action_type}|cost")],
        [btn("⏯ فعال/غیرفعال", f"aim_a_route_tog|{action_type}")],
        back_btn("aim_a_model_routing"),
    ])


def ai_admin_payment_kb():
    return mkb([
        [btn("💳 شمارهٔ کارت", "aim_a_pay_set|card_number")],
        [btn("👤 نام صاحب کارت", "aim_a_pay_set|card_holder")],
        [btn("🏦 نام بانک", "aim_a_pay_set|bank_name")],
        [btn("📝 توضیح اضافه", "aim_a_pay_set|note")],
        back_btn("aim_a_menu"),
    ])


def ai_admin_pending_kb(purchases):
    """فهرست فیش‌های در انتظار تأیید."""
    rows = []
    for p in purchases[:15]:
        rows.append([btn(
            f"👤 {p.get('user_name') or p['user_id']} — {fa_digits(p['amount'])} اعتبار",
            f"aim_a_pur_view|{p['id']}",
        )])
    if not rows:
        rows.append([btn("— فیشی در انتظار نیست —", "aim_noop")])
    rows.append([btn("🔄 به‌روزرسانی", "aim_a_pending_purchases")])
    rows.append(back_btn("aim_a_menu"))
    return mkb(rows)


def ai_admin_purchase_kb(purchase_id):
    return mkb([
        [btn("✅ تأیید و شارژ", f"aim_a_pur_ok|{purchase_id}"),
         btn("❌ رد", f"aim_a_pur_no|{purchase_id}")],
        back_btn("aim_a_pending_purchases"),
    ])


def ai_admin_packs_kb(packages):
    """مدیریت بسته‌های اعتبار — هر بسته دو دکمه: تغییر وضعیت و حذف."""
    rows = [[btn("➕ افزودن بستهٔ جدید", "aim_a_pack_add")]]
    for p in packages:
        state = "🟢" if p["is_active"] else "🔴"
        rows.append([
            btn(f"{state} {fa_digits(p['amount'])} اعتبار — {price_label(p['price'])}",
                f"aim_a_pack_tog|{p['id']}"),
            btn("🗑", f"aim_a_pack_del|{p['id']}"),
        ])
    if len(rows) == 1:
        rows.append([btn("— بسته‌ای ثبت نشده —", "aim_noop")])
    rows.append(back_btn("aim_a_menu"))
    return mkb(rows)


def ai_admin_core_kb():
    # از همان منطق module_enabled استفاده می‌شود تا برچسب دکمه با
    # وضعیت واقعیِ ماژول (شامل کلید config) یکسان باشد.
    try:
        from .ai_handlers import module_enabled
        enabled = module_enabled()
    except Exception:
        enabled = str(ai_db.get_ai_setting("enabled", "1")).strip() != "0"
    return mkb([
        [btn(f"{'🟢 ماژول فعال' if enabled else '🔴 ماژول غیرفعال'} — تغییر", "aim_a_toggle")],
        [btn("🧠 تعیین مدل/پروایدر", "aim_a_set|model")],
        [btn("📝 پرامپت سفارشی", "aim_a_set|system_prompt")],
        [btn("🎁 سهمیهٔ رایگان اولیه", "aim_a_set|free_quota")],
        back_btn("aim_a_menu"),
    ])


def ai_admin_pricing_kb():
    s = ai_db.all_ai_settings()
    return mkb([
        [btn(f"🗺 نقشه راه: {s.get('price_roadmap', '?')}", "aim_a_set|price_roadmap")],
        [btn(f"💬 چت منتور: {s.get('price_chat', '?')}", "aim_a_set|price_chat")],
        [btn(f"✍️ تصحیح چالش: {s.get('price_challenge', '?')}", "aim_a_set|price_challenge")],
        [btn(f"📄 گزارش شغلی: {s.get('price_report', '?')}", "aim_a_set|price_report")],
        [btn(f"🔥 ترندها: {s.get('price_trends', '?')}", "aim_a_set|price_trends")],
        [btn(f"💡 کمک آموزش: {s.get('price_help', '?')}", "aim_a_set|price_help")],
        [btn(f"🎤 شبیه‌ساز مصاحبه: {s.get('price_interview_sim', '?')}",
             "aim_a_set|price_interview_sim")],
        [btn(f"👯‍♂️ همزاد شغلی: {s.get('price_twin', '?')}", "aim_a_set|price_twin")],
        back_btn("aim_a_menu"),
    ])


def ai_admin_trends_kb(trends):
    rows = [
        [btn("➕ افزودن مهارت", "aim_a_trend_add")],
        [btn("🌐 تنظیم منبع اسکن", "aim_a_set|trends_source")],
        [btn("🔄 به‌روزرسانی خودکار ترندها", "aim_a_trend_ai")],
    ]
    for t in trends[:15]:
        rows.append([btn(f"🗑 {t['skill_name']} ({t['demand_count']})",
                         f"aim_a_trend_del|{t['skill_name']}")])
    rows.append(back_btn("aim_a_menu"))
    return mkb(rows)


def ai_admin_back_kb(cb: str = "aim_a_menu"):
    return mkb([back_btn(cb)])


# ========================= متن‌ها =========================

def _bar(done: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "▱" * width
    filled = max(0, min(width, round(done / total * width)))
    return "▰" * filled + "▱" * (width - filled)


def progress_text(path: dict, done: int, total: int) -> str:
    pct = int(done / total * 100) if total else 0
    return (
        f"🎯 مسیر شغلی شما\n\n"
        f"🏁 هدف: {path.get('target_job', '—')}\n"
        f"📊 پیشرفت: {done} از {total} گام ({pct}٪)\n"
        f"{_bar(done, total)}\n\n"
        f"برای دیدن جزئیات هر گام روی آن بزنید:"
    )
