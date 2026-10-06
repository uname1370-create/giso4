# -*- coding: utf-8 -*-
"""پنل آنالیز: جداسازی مو/پوست + Mirror History — FINBUTI سناریوی نهایی.

Route اصلی: /dashboard/analyses — یک صفحه واحد برای نتایج قدیمی و Mirror.
تب‌ها: [ابرو] [مو] [آرایش] [ناخن] — Mapping:
- ابرو = buti_ai_final_designs service_type=eyebrow
- مو = Analysis قدیمی type=hair + Mirror hair_color
- آرایش = lip_shading + محل توسعه آینده makeup + legacy skin
- ناخن = Mirror nail
داده قدیمی پوست حذف نشود؛ به‌صورت Legacy داخل همان تجربه نمایش داده شود.

کارت نتیجه: تصویر Before/After, نام خدمت, مدل انتخابی, تاریخ, خلاصه تحلیل, وضعیت AI, مشاهده نتیجه, رزرو همین خدمت.
اگر final image وجود نداشت graceful fallback و نباید تصویر جعلی تولید شود.

اولویت: Extend analyses.py و analyses.html — mirror.py فقط در صورتی ساخته شود که پس از Audit مشخص شود منطق History باعث سنگینی می‌شود.
Reuse > Extend > New — Code Truth حفظ شود.
"""
import json
import os
from datetime import datetime

from flask_login import current_user

from giso.models import Analysis, db
from giso.base import get_giso_db_conn, normalize_phone, to_shamsi
from giso.analysis_labels import metric_label


def _json(raw):
    try:
        return json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
    except Exception:
        return {}


def _decorate(row):
    report = _json(row.ai_report_json)
    problems = report.get("main_problems") or report.get("problems") or []
    if isinstance(problems, dict):
        problems = list(problems.values())
    labels = []
    for item in problems[:3]:
        labels.append(str(item.get("name") or item.get("title") or item)[:80] if isinstance(item, dict) else str(item)[:80])
    metrics = []
    source = report.get("metrics") or report.get("scores") or {}
    if isinstance(source, dict):
        for key, value in list(source.items())[:6]:
            try:
                score = max(0, min(100, int(float(value.get("value", value.get("score", 0)) if isinstance(value, dict) else value))))
            except Exception:
                continue
            metrics.append({"label": metric_label(key, value), "score": score})
    return {
        "row": row,
        "problems": labels,
        "metrics": metrics,
        "date_fa": to_shamsi(row.created_at),
        "has_plan": bool(row.plan_json),
        "has_quick": bool(row.quick_solution_json),
        "has_report": bool(report),
        "type": "analysis_old",
        "service_key": row.type,  # hair / skin
        "service_label": "آنالیز مو" if row.type == "hair" else "آنالیز پوست",
    }


def _decorate_mirror(row: dict) -> dict:
    """Decorate buti_ai_final_designs row for unified display."""
    service_type = str(row.get("service_type") or "").strip().lower()
    # Normalize service_type variants
    if service_type in ("hair-color",):
        service_type = "hair_color"
    if service_type in ("lip-shading", "lip"):
        service_type = "lip_shading"

    # Service meta from catalog if available
    service_label = service_type
    short_title = service_type
    slug = service_type
    beauty_service = ""
    try:
        from giso.buti_ai.service_catalog import get_service_meta, slug_for_service

        meta = get_service_meta(service_type) or {}
        service_label = str(meta.get("title") or service_label)
        short_title = str(meta.get("short_title") or short_title)
        slug = str(meta.get("slug") or slug_for_service(service_type) or service_type)
        beauty_service = str(meta.get("beauty_center_service") or "")
    except Exception:
        pass

    # Parse prompt_json for extra context (candidate, generation)
    prompt_data = _json(row.get("prompt_json"))
    candidate = prompt_data.get("candidate") if isinstance(prompt_data, dict) else {}
    generation = prompt_data.get("generation") if isinstance(prompt_data, dict) else {}

    # Fallbacks from candidate if prompt_json missing
    if not isinstance(candidate, dict):
        candidate = {}
    if not isinstance(generation, dict):
        generation = {}

    original_filename = str(row.get("original_filename") or candidate.get("photo_filename") or "")[:200]
    final_filename = str(row.get("final_filename") or generation.get("filename") or "")[:200]
    selected_style = str(row.get("selected_style") or candidate.get("final_style") or candidate.get("selected_style") or "")[:80]
    change_level = str(row.get("change_level") or candidate.get("change_key") or "")[:40]
    provider = str(row.get("provider") or generation.get("provider") or "")[:80]
    model = str(row.get("model") or generation.get("model") or "")[:80]
    status = str(row.get("status") or generation.get("status") or "created")[:40]

    # Date
    created_at_raw = str(row.get("created_at") or "")
    date_fa = ""
    try:
        # created_at is YYYY-MM-DD HH:MM:SS
        if created_at_raw:
            # to_shamsi expects gregorian string, try direct
            date_fa = to_shamsi(created_at_raw)
        else:
            date_fa = ""
    except Exception:
        date_fa = created_at_raw[:16]

    # Short reason / summary
    short_reason = str(candidate.get("short_reason") or "")[:200]
    if not short_reason:
        short_reason = f"مدل {selected_style} برای {short_title}"

    # AI status
    is_ai_generated = False
    try:
        is_ai_generated = bool(generation.get("is_ai_generated"))
    except Exception:
        pass
    # If provider indicates python_guided_composite, it's non-AI
    if provider in ("python_guided_composite",):
        is_ai_generated = False

    # Graceful fallback flag if final image missing
    has_final = bool(final_filename)
    has_original = bool(original_filename)

    # Build reservation params
    # final_design_id = row id, service_key = service_type, selected_style
    final_design_id = int(row.get("id") or 0)

    return {
        "row": row,
        "id": final_design_id,
        "type": "mirror",
        "service_type": service_type,
        "service_key": service_type,
        "service_label": service_label,
        "short_title": short_title,
        "slug": slug,
        "beauty_service": beauty_service,
        "original_filename": original_filename,
        "final_filename": final_filename,
        "selected_style": selected_style,
        "change_level": change_level,
        "provider": provider,
        "model": model,
        "status": status,
        "is_ai_generated": is_ai_generated,
        "has_final": has_final,
        "has_original": has_original,
        "date_fa": date_fa,
        "created_at": created_at_raw,
        "short_reason": short_reason,
        "candidate": candidate,
        "generation": generation,
        "final_design_id": final_design_id,
        "do": list(candidate.get("do") or [])[:3],
        "avoid": list(candidate.get("avoid") or [])[:3],
    }


def context():
    phone = normalize_phone(getattr(current_user, "phone", "") or "")
    user_id = int(getattr(current_user, "id", 0) or 0)

    # Old analyses via ORM
    rows = (
        Analysis.query.filter(
            db.or_(Analysis.user_id == current_user.id, Analysis.phone == phone),
            db.or_(Analysis.archived_at == "", Analysis.archived_at.is_(None)),
        )
        .order_by(Analysis.id.desc())
        .all()
    )
    archived_rows = (
        Analysis.query.filter(
            db.or_(Analysis.user_id == current_user.id, Analysis.phone == phone),
            Analysis.archived_at.isnot(None),
            Analysis.archived_at != "",
        )
        .order_by(Analysis.id.desc())
        .all()
    )
    hair = [_decorate(r) for r in rows if r.type == "hair"]
    skin = [_decorate(r) for r in rows if r.type == "skin"]
    archived = [_decorate(r) for r in archived_rows]
    latest_hair = hair[0] if hair else None
    latest_skin = skin[0] if skin else None

    # Mirror final designs via raw SQL (giso.db)
    mirror_rows_raw = []
    try:
        with get_giso_db_conn() as conn:
            # Ensure table exists (init_buti_ai_db is idempotent)
            try:
                from giso.buti_ai.schema import init_buti_ai_db

                init_buti_ai_db()
            except Exception:
                pass
            mirror_rows_raw = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM buti_ai_final_designs WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT 100",
                    (user_id,),
                ).fetchall()
            ]
    except Exception:
        mirror_rows_raw = []

    mirror_decorated = [_decorate_mirror(r) for r in mirror_rows_raw]

    # Group by service_type normalized
    mirror_eyebrow = [m for m in mirror_decorated if m["service_type"] == "eyebrow"]
    mirror_hair_color = [m for m in mirror_decorated if m["service_type"] == "hair_color"]
    mirror_nail = [m for m in mirror_decorated if m["service_type"] == "nail"]
    mirror_lip = [m for m in mirror_decorated if m["service_type"] == "lip_shading"]

    # FINBUTI Mapping:
    # ابرو = eyebrow
    # مو = Analysis hair + Mirror hair_color
    # آرایش = lip_shading + legacy skin + future makeup
    # ناخن = nail
    hair_combined = hair + mirror_hair_color
    makeup_combined = mirror_lip + skin  # lip + legacy skin as legacy
    # Sort combined by date desc (approx)
    try:
        hair_combined = sorted(hair_combined, key=lambda x: str(x.get("date_fa") or x.get("created_at") or ""), reverse=True)
    except Exception:
        pass
    try:
        makeup_combined = sorted(makeup_combined, key=lambda x: str(x.get("date_fa") or x.get("created_at") or ""), reverse=True)
    except Exception:
        pass

    # Latest per mirror service
    latest_eyebrow = mirror_eyebrow[0] if mirror_eyebrow else None
    latest_hair_color = mirror_hair_color[0] if mirror_hair_color else None
    latest_nail = mirror_nail[0] if mirror_nail else None
    latest_lip = mirror_lip[0] if mirror_lip else None

    # Recommendation (old)
    try:
        from giso.recommendation_service import get_recommendation_for_user

        recommendation = get_recommendation_for_user(getattr(current_user, "phone", ""), max_items=6)
    except Exception:
        recommendation = {"recommendations": [], "match_source": "general"}

    # Counts for tabs
    counts = {
        "overview": len(rows) + len(mirror_decorated),
        "eyebrow": len(mirror_eyebrow),
        "hair": len(hair) + len(mirror_hair_color),
        "makeup": len(mirror_lip) + len(skin),
        "nail": len(mirror_nail),
        "archive": len(archived),
        "mirror_total": len(mirror_decorated),
        "hair_old": len(hair),
        "skin_old": len(skin),
    }

    return {
        # Old (backward compat)
        "analyses": rows,
        "hair_analyses": hair,
        "skin_analyses": skin,
        "archived_analyses": archived,
        "latest_hair": latest_hair,
        "latest_skin": latest_skin,
        "analysis_products": recommendation.get("recommendations", []),
        "products_personalized": recommendation.get("match_source") != "general",
        # Mirror new
        "mirror_rows": mirror_rows_raw,
        "mirror_decorated": mirror_decorated,
        "mirror_eyebrow": mirror_eyebrow,
        "mirror_hair_color": mirror_hair_color,
        "mirror_nail": mirror_nail,
        "mirror_lip": mirror_lip,
        "mirror_lip_shading": mirror_lip,
        "latest_eyebrow": latest_eyebrow,
        "latest_hair_color": latest_hair_color,
        "latest_nail": latest_nail,
        "latest_lip": latest_lip,
        # Combined per FINBUTI tabs
        "hair_combined": hair_combined,
        "makeup_combined": makeup_combined,
        "eyebrow_combined": mirror_eyebrow,
        "nail_combined": mirror_nail,
        # Counts
        "tab_counts": counts,
        "mirror_counts": {
            "eyebrow": len(mirror_eyebrow),
            "hair_color": len(mirror_hair_color),
            "nail": len(mirror_nail),
            "lip_shading": len(mirror_lip),
            "total": len(mirror_decorated),
        },
    }
