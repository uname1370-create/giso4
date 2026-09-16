# -*- coding: utf-8 -*-
"""Explicit, superadmin-only reset operations for monitoring reports."""
from giso.base import get_giso_db_conn

SCOPES={
    "errors":"giso_system_errors",
    "behavior":"giso_ux_events",
    "security":"giso_login_events",
    "ai_reports":"giso_monitoring_ai_reports",
}

def _table_exists(conn,name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())

def reset(scope):
    if scope not in (*SCOPES.keys(),"broadcasts"):
        return False,"بخش نامعتبر است.",0
    with get_giso_db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if scope=="broadcasts":
            if not _table_exists(conn,"giso_broadcast_campaigns"):
                conn.rollback();return True,"گزارشی برای پاک‌سازی وجود ندارد.",0
            ids=[int(r[0]) for r in conn.execute("SELECT id FROM giso_broadcast_campaigns WHERE status NOT IN ('queued','sending')").fetchall()]
            count=len(ids)
            if ids:
                marks=','.join('?' for _ in ids)
                conn.execute(f"DELETE FROM giso_broadcast_recipients WHERE campaign_id IN ({marks})",ids)
                conn.execute(f"DELETE FROM giso_broadcast_campaigns WHERE id IN ({marks})",ids)
        else:
            table=SCOPES[scope]
            if not _table_exists(conn,table):
                conn.rollback();return True,"گزارشی برای پاک‌سازی وجود ندارد.",0
            count=int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    labels={"errors":"خطاها","behavior":"رفتار کاربران","security":"تاریخچه ورود","broadcasts":"گزارش کمپین‌های پایان‌یافته","ai_reports":"گزارش‌های AI"}
    return True,f"{labels[scope]} بازنشانی شد.",count
