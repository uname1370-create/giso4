# -*- coding: utf-8 -*-
"""پنل آنالیز: جداسازی مو/پوست، خلاصه واقعی و متریک‌های گزارش."""
import json
from flask_login import current_user
from giso.models import Analysis, db
from giso.base import normalize_phone, to_shamsi
from giso.analysis_labels import metric_label


def _json(raw):
    try: return json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
    except Exception: return {}


def _decorate(row):
    report=_json(row.ai_report_json)
    problems=report.get("main_problems") or report.get("problems") or []
    if isinstance(problems,dict): problems=list(problems.values())
    labels=[]
    for item in problems[:3]: labels.append(str(item.get("name") or item.get("title") or item)[:80] if isinstance(item,dict) else str(item)[:80])
    metrics=[]
    source=report.get("metrics") or report.get("scores") or {}
    if isinstance(source,dict):
        for key,value in list(source.items())[:6]:
            try: score=max(0,min(100,int(float(value.get("value",value.get("score",0)) if isinstance(value,dict) else value))))
            except Exception: continue
            metrics.append({"label":metric_label(key,value),"score":score})
    return {"row":row,"problems":labels,"metrics":metrics,"date_fa":to_shamsi(row.created_at),"has_plan":bool(row.plan_json),"has_quick":bool(row.quick_solution_json),"has_report":bool(report)}


def context():
    phone=normalize_phone(current_user.phone)
    rows=(Analysis.query.filter(db.or_(Analysis.user_id==current_user.id,Analysis.phone==phone),db.or_(Analysis.archived_at=="",Analysis.archived_at.is_(None))).order_by(Analysis.id.desc()).all())
    archived_rows=(Analysis.query.filter(db.or_(Analysis.user_id==current_user.id,Analysis.phone==phone),Analysis.archived_at.isnot(None),Analysis.archived_at!="").order_by(Analysis.id.desc()).all())
    hair=[_decorate(r) for r in rows if r.type=="hair"]
    skin=[_decorate(r) for r in rows if r.type=="skin"]
    archived=[_decorate(r) for r in archived_rows]
    latest_hair=hair[0] if hair else None;latest_skin=skin[0] if skin else None
    try:
        from giso.recommendation_service import get_recommendation_for_user
        recommendation=get_recommendation_for_user(current_user.phone,max_items=6)
    except Exception: recommendation={"recommendations":[],"match_source":"general"}
    return {"analyses":rows,"hair_analyses":hair,"skin_analyses":skin,"archived_analyses":archived,"latest_hair":latest_hair,"latest_skin":latest_skin,"analysis_products":recommendation.get("recommendations",[]),"products_personalized":recommendation.get("match_source")!="general"}
