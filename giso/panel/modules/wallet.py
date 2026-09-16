# -*- coding: utf-8 -*-
"""مرکز مالی سوپرادمین: مأموریت، شارژ، تسویه، رتبه‌ها، اعتبار خدمات و تنظیمات."""
import logging

from flask import request

from giso.wallet import (
    get_admin_financial_summary, get_financial_settings,
    list_missions_admin, list_topups, list_withdrawals,
    MISSION_EVENTS, get_service_fees,
    get_rank_settings, get_weekly_leaderboard,
    get_service_credit_settings, service_charge_report, SERVICE_CREDIT_DEFS,
)

logger = logging.getLogger("giso_panel_wallet")

VALID_TABS = {"overview", "users", "shop", "marketplace", "beauty", "ai", "discrepancies", "missions", "ranks", "topups", "settlements", "service_credits", "settings"}


def _rank_daily_report(limit: int = 20):
    """گزارش خواندنی واریزهای روزانهٔ رتبه (تاریخ/تعداد/مبلغ) — بدون اجرای واریز."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT substr(created_at,1,10) AS day, COUNT(*) AS n, SUM(amount) AS total "
                "FROM wallet_transactions WHERE kind='rank_daily' "
                "GROUP BY day ORDER BY day DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(day=r["day"], count=int(r["n"] or 0), total=int(r["total"] or 0)) for r in rows]
    except Exception as exc:  # pragma: no cover - مسیر امن
        logger.warning("rank daily report failed: %s", exc)
        return []


def context():
    tab = (request.args.get("tab") or "overview").strip().lower()
    if tab not in VALID_TABS:
        tab = "missions"
    from giso.panel.modules.finance_overview import context as overview_context
    ctx = {
        **overview_context(),
        "finance_tab": tab,
        "finance_summary": get_admin_financial_summary(),
        "wallet_missions": list_missions_admin(),
        "topup_requests": list_topups(limit=250),
        "withdrawals": list_withdrawals(limit=250),
        "financial_settings": get_financial_settings(),
        "mission_events": MISSION_EVENTS,
        "service_fees": get_service_fees(),
    }
    # ── تب «🏅 رتبه‌ها» ──
    try:
        ctx["rank_settings"] = get_rank_settings()
        ctx["weekly_leaderboard"] = get_weekly_leaderboard(10)
        ctx["rank_daily_report"] = _rank_daily_report()
    except Exception as exc:  # pragma: no cover - مسیر امن
        logger.warning("rank context failed: %s", exc)
        ctx["rank_settings"] = {"daily_credit_enabled": False, "levels": []}
        ctx["weekly_leaderboard"] = []
        ctx["rank_daily_report"] = []
    # ── تب «🎫 اعتبار خدمات» ──
    try:
        settings = get_service_credit_settings() or {}
        items = list(settings.get("items") or [])
        ctx["service_credit_settings"] = settings
        ctx["service_credit_items"] = items
        ctx["service_credit_defs"] = [
            {"key": k, "label": lbl}
            for k, lbl, _en, _fee, _d in SERVICE_CREDIT_DEFS
        ]
        ctx["service_charge_report"] = service_charge_report(limit=100) or {"items": [], "counts": []}
    except Exception as exc:  # pragma: no cover - مسیر امن
        logger.warning("service credit context failed: %s", exc)
        ctx["service_credit_settings"] = {"items": []}
        ctx["service_credit_items"] = []
        ctx["service_credit_defs"] = []
        ctx["service_charge_report"] = {"items": [], "counts": []}
    return ctx
