# -*- coding: utf-8 -*-
"""
giso/analysis_report.py — سازنده‌های خالص داده‌های گزارش نهایی آنالیز (Phase 2, Unit 1)
استخراج‌شده از giso/analysis.py بدون تغییر رفتار؛ توابع/ثابت‌ها در giso.analysis
با همین نام‌ها re-export می‌شوند بنابراین importهای خارجی (از جمله تست‌ها) سالم می‌مانند.
هیچ وابستگی به Flask/DB/request ندارد — قابل تست مستقل.
"""

_NEW_METRIC_KEY = {
    "hydration": "آبرسانی", "elasticity": "انعطاف‌پذیری", "strength": "استحکام",
    "shine": "درخشش", "scalp_health": "سلامت پوست سر", "growth_rate": "سرعت رشد",
}
_LEGACY_METRIC_KEY = {
    "رطوبت": "آبرسانی", "انعطاف": "انعطاف‌پذیری", "انعطاف‌پذیری": "انعطاف‌پذیری",
    "استحکام": "استحکام", "درخشش": "درخشش", "سلامت پوست سر": "سلامت پوست سر",
    "سرعت رشد": "سرعت رشد", "رشد": "سرعت رشد", "بافت": "استحکام",
    "تراکم": "سرعت رشد", "سلامت رنگ": "درخشش",
}


def _normalize_report_data(data, analysis_type):
    """
    نرمال‌سازی ساختار گزارش نهایی برای سازگاری با هر دو ساختار:
    - ساختار جدید (metrics با کلیدهای انگلیسی + main_problems + weaknesses +
      immediate_actions + avoid_list + summary + condition + expected_timeline)
    - ساختار قدیمی (radar_metrics با کلیدهای فارسی + concerns + routine + warnings)
    خروجی: dict با radar_metrics (کلیدهای فارسی یکسان برای کارت/رادار)،
    strengths، concerns، و فیلدهای جدید برای رندر template.
    """
    if not isinstance(data, dict):
        data = {}
    out = dict(data)

    # ── radar_metrics یکپارچه (کلیدهای فارسی جدید) ──
    radar = {}
    new_metrics = data.get("metrics")
    legacy_radar = data.get("radar_metrics")
    if isinstance(new_metrics, dict):
        for k, v in new_metrics.items():
            pk = _NEW_METRIC_KEY.get(k, k)
            try:
                radar[pk] = max(0, min(100, int(v)))
            except (TypeError, ValueError):
                radar[pk] = 0
    elif isinstance(legacy_radar, dict):
        for k, v in legacy_radar.items():
            pk = _LEGACY_METRIC_KEY.get(k, k)
            try:
                radar[pk] = max(0, min(100, int(v)))
            except (TypeError, ValueError):
                radar[pk] = 0
    out["radar_metrics"] = radar

    # ── concerns از هر دو ساختار ──
    concerns = []
    legacy_concerns = data.get("concerns")
    if isinstance(legacy_concerns, list):
        concerns = [str(c) for c in legacy_concerns]
    else:
        for mp in data.get("main_problems") or []:
            if isinstance(mp, dict):
                label = mp.get("name", "")
                desc = mp.get("description", "")
                if label and desc:
                    concerns.append(f"{label} — {desc}")
                elif label:
                    concerns.append(label)
        for w in data.get("weaknesses") or []:
            concerns.append(str(w))
    out["concerns"] = concerns

    # ── strengths ──
    if isinstance(data.get("strengths"), list):
        out["strengths"] = [str(s) for s in data["strengths"]]

    # ── وضعیت کلی ──
    if not out.get("status_label") and data.get("overall_score") is not None:
        try:
            out["status_label"] = _status_for_value(int(data["overall_score"]))[0]
        except (TypeError, ValueError):
            pass

    return out

# ============================================================
# آماده‌سازی داده‌های گزارش نهایی
# ============================================================

_METRIC_META = {
    "hair": [
        {"key": "آبرسانی", "icon": "💧", "desc": "میزان رطوبت و آب داخل ساقه مو که به نرمی و انعطاف‌پذیری کمک می‌کنه. کمبود آبرسانی باعث خشکی و شکنندگی می‌شه."},
        {"key": "انعطاف‌پذیری", "icon": "🌀", "desc": "توانایی مو در خم شدن و برگشتن به حالت اولیه بدون شکستن. مو منعطف، مقاوم‌تر و سالم‌تره."},
        {"key": "استحکام", "icon": "🛡️", "desc": "مقاومت تارهای مو در برابر کشش و آسیب‌های فیزیکی. استحکام بالا نشانه سلامت ساختار پروتئینی موئه."},
        {"key": "درخشش", "icon": "✨", "desc": "میزان بازتاب نور از سطح مو که نشون‌دهنده سلامت کوتیکل و بستن پولک‌های موست. مو درخشان، مو سالمه."},
        {"key": "سلامت پوست سر", "icon": "🧬", "desc": "وضعیت پوست سر که پایه‌ی رشد سالم موست. پوست سالم بدون التهاب، شوره و چربی اضافی، رشد بهتری می‌ده."},
        {"key": "سرعت رشد", "icon": "🌿", "desc": "میزان رشد مو در بازه زمانی که نشان‌دهنده سلامت فولیکول‌ها و گردش خون پوست سره."},
    ],
    "skin": [
        {"key": "هیدراسیون", "icon": "💧", "desc": "میزان رطوبت پوست که به شادابی و انعطاف‌پذیری کمک می‌کنه. پوست هیدراته‌شده، جوان‌تر به نظر می‌اد."},
        {"key": "یکنواختی", "icon": "🎯", "desc": "یکدست بودن رنگ و بافت پوست. یکنواختی نشون‌دهنده سلامت سلول‌ها و نبود مشکلات پیگمانتاسیون شدیده."},
        {"key": "منافذ", "icon": "🔬", "desc": "اندازه و وضعیت منافذ پوست. منافذ کوچک و بسته نشون‌دهنده تولید متعادل چربی و پوست تمیزه."},
        {"key": "التهاب", "icon": "🩹", "desc": "میزان قرمزی و التهاب پوست. پوست بدون التهاب، سالم و آرومه."},
        {"key": "خطوط ریز", "icon": "📏", "desc": "وجود چین و چروک‌های ریز که نشون‌دهنده سطح کلاژن پوستن. جلوگیری از خطوط ریز با آبرسانی و ضدآفتاب ممکنه."},
        {"key": "لک", "icon": "🌟", "desc": "شواهد لک، پیگمانتاسیون و تیرگی موضعی. پوست یکدست و بدون لک، جوان‌تر به نظر می‌اد."},
    ],
}

# پیش‌فرض‌های اقدام برای نقاط قوت و راه‌حل برای نگرانی‌ها
_STRENGTH_DEFAULTS = {
    "hair": ["این نقطه قوت رو با روتین منظم حفظ کن", "برای ماندگاری بیشتر، از محصولات مناسب استفاده کن"],
    "skin": ["این وضعیت رو با آبرسانی مستمر حفظ کن", "برای بهتر شدن، به مراقبت روزانه ادامه بده"],
}
_CONCERN_DEFAULT = "با رعایت روتین پیشنهادی و مراقبت منظم، این مورد بهبود پیدا می‌کنه."


def _status_for_value(v):
    """برچسب و کلاس وضعیت بر اساس درصد."""
    if v >= 90:
        return "عالی", "good"
    if v >= 70:
        return "خوب", "ok"
    if v >= 50:
        return "متوسط", "mid"
    return "نیاز به توجه", "low"


def _build_metric_cards(data, analysis_type):
    """ساخت ۶ کارت متریک با آیکون، وضعیت و توضیح."""
    metrics = data.get("radar_metrics") or {}
    meta_list = _METRIC_META.get(analysis_type, _METRIC_META["hair"])
    cards = []
    for meta in meta_list:
        key = meta["key"]
        try:
            v = max(0, min(100, int(metrics.get(key, 0) or 0)))
        except (TypeError, ValueError):
            v = 0
        label, cls = _status_for_value(v)
        cards.append({
            "key": key, "icon": meta["icon"], "desc": meta["desc"],
            "value": v, "status_label": label, "status_class": cls,
        })
    return cards


def _build_strength_items(data, analysis_type):
    """نقاط قوت + پیشنهاد اقدام برای حفظ."""
    strengths = data.get("strengths") or []
    defaults = _STRENGTH_DEFAULTS.get(analysis_type, _STRENGTH_DEFAULTS["hair"])
    items = []
    for i, s in enumerate(strengths):
        items.append({"text": s, "action": defaults[i % len(defaults)] if defaults else ""})
    return items


def _build_concern_items(data):
    """نگرانی‌ها + راه‌حل عملی."""
    concerns = data.get("concerns") or []
    return [{"text": c, "solution": _CONCERN_DEFAULT} for c in concerns]


def _build_routine_cards(data, analysis_type):
    """کارت‌های روتین زیر هم (صبح/ظهر/شب/هفتگی)."""
    rt = data.get("routine") or {}
    # سازگاری: مو daily_morning/daily_evening/weekly | پوست morning/evening/weekly
    morning = rt.get("daily_morning") or rt.get("morning") or ""
    evening = rt.get("daily_evening") or rt.get("evening") or ""
    weekly = rt.get("weekly") or ""
    noon = rt.get("noon") or ""
    cards = [
        {"icon": "🌅", "title": "روتین صبح", "text": morning, "cls": "morning"},
        {"icon": "☀️", "title": "روتین ظهر", "text": noon, "cls": "noon"},
        {"icon": "🌙", "title": "روتین شب", "text": evening, "cls": "evening"},
        {"icon": "📅", "title": "روتین هفتگی", "text": weekly, "cls": "weekly"},
    ]
    return [c for c in cards if c["text"]]


def _build_radar_points(data, analysis_type="hair"):
    """
    تولید مختصات SVG برای نمودار رادار ۶ محوره.
    خروجی: {'pts': [...], 'order': [...], 'grids': [...], 'ax_lines': [...], 'labels': [...], 'rings':[...]}
    """
    metrics = data.get("radar_metrics") or {}
    order = ["هیدراسیون", "یکنواختی", "منافذ", "التهاب", "خطوط ریز", "لک"] \
        if analysis_type == "skin" else \
        ["آبرسانی", "انعطاف‌پذیری", "استحکام", "درخشش", "سلامت پوست سر", "سرعت رشد"]
    # مختصات ۶ نقطه روی دایره (شروع از راست، پادساعت‌نما برای RTL)
    import math
    cx = cy = 200.0
    R = 140.0
    dirs = []
    for i in range(6):
        ang = math.radians(90 - i * 60)  # شروع از بالا (12 ساعت)
        dirs.append((math.cos(ang), math.sin(ang)))
    vals = []
    for k in order:
        v = metrics.get(k)
        try:
            v = max(0, min(100, int(v)))
        except (TypeError, ValueError):
            v = 0
        vals.append(v)
    # مختصات داده
    pts = []
    for i in range(6):
        vv = vals[i]
        pts.append((cx + (R * vv / 100) * dirs[i][0], cy + (R * vv / 100) * dirs[i][1]))
    pts_str = " ".join(f"{round(p[0],1)},{round(p[1],1)}" for p in pts)
    # شبکه حلقه‌ها
    rings = []
    for ring in (1, 2, 3):
        rr = R * ring / 3
        ring_pts = " ".join(
            f"{round(cx + rr * d[0],1)},{round(cy + rr * d[1],1)}" for d in dirs
        )
        rings.append(ring_pts)
    # خطوط محور
    ax_lines = [{"x1": round(cx,1), "y1": round(cy,1),
                 "x2": round(cx + R * d[0],1), "y2": round(cy + R * d[1],1)} for d in dirs]
    # نقاط
    dots = [{"x": round(pts[i][0],1), "y": round(pts[i][1],1)} for i in range(6)]
    # لیبل‌ها
    labels = [{"x": round(cx + (R + 30) * dirs[i][0],1),
               "y": round(cy + (R + 30) * dirs[i][1] + 4,1), "text": order[i]} for i in range(6)]
    return {"pts_str": pts_str, "rings": rings, "ax_lines": ax_lines,
            "dots": dots, "labels": labels, "values": list(zip(order, vals))}
