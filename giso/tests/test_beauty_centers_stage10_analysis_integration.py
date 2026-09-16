# -*- coding: utf-8 -*-
"""Stage 10: complete, ownership-safe Analysis → Beauty Centers integration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_all_analysis_outputs_have_server_rendered_center_cta():
    templates = ROOT / "giso/templates"
    for name in (
        "analysis_report_hair.html", "analysis_report_skin.html",
        "analysis_plan.html", "analysis_quick_solution.html",
    ):
        source = (templates / name).read_text(encoding="utf-8")
        assert "beauty_centers/_analysis_cta.html" in source
        assert "beauty_analysis_id" in source
    cta = (ROOT / "giso/beauty_centers/templates/beauty_centers/_analysis_cta.html").read_text(encoding="utf-8")
    assert "analysis_id=beauty_analysis_id" in cta
    assert "گیسو فقط بستر معرفی است" in cta


def test_recommendations_use_owned_analysis_and_only_published_real_centers():
    service = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    assert "(user_id=? OR phone=(SELECT phone FROM giso_web_auth WHERE id=?))" in service
    assert "candidates = list_public_centers" in service
    assert "clauses = [\"status='published'\", \"is_active=1\"]" in service
    assert "score = sum(1 for tag in tags if tag in center[\"services\"])" in service
    assert "scored[:max(1, min(3, int(limit)))]" in service
    assert "analysis_impressions=analysis_impressions+1" in service


def test_analysis_context_survives_directory_filters_and_renders_related_first():
    route = (ROOT / "giso/beauty_centers/routes.py").read_text(encoding="utf-8")
    page = (ROOT / "giso/beauty_centers/templates/beauty_centers/list.html").read_text(encoding="utf-8")
    assert 'analysis_id = request.args.get("analysis_id", type=int) or 0' in route
    assert "recommended_centers(analysis_id, _user_id()" in route
    assert 'type="hidden" name="analysis_id" value="{{ analysis_id }}"' in page
    assert page.index("{% if related %}") < page.index('id="all-centers"')
    assert "نمایش به معنی تضمین کیفیت یا نتیجه نیست" in page


def test_consultant_receives_database_recommendations_without_tracking_fake_impressions():
    analysis = (ROOT / "giso/analysis.py").read_text(encoding="utf-8")
    assert "from giso.beauty_centers.services import recommended_centers" in analysis
    assert "track_impression=False" in analysis
    assert "beauty_centers=beauty_centers" in analysis
