# -*- coding: utf-8 -*-
"""Read-only financial aggregation over existing Giso ledgers and purchase tables."""
from giso.base import get_giso_db_conn


def _one(conn, sql, params=()):
    try:return int((conn.execute(sql,params).fetchone()[0] or 0))
    except Exception:return 0


def _rows(conn, sql, params=()):
    try:return [dict(r) for r in conn.execute(sql,params).fetchall()]
    except Exception:return []


def context():
    with get_giso_db_conn() as conn:
        summary={
            "shop_sales":_one(conn,"SELECT COALESCE(SUM(gross_amount),0) FROM shop_checkouts WHERE status NOT IN ('cancelled','rejected')"),
            "shop_wallet":_one(conn,"SELECT COALESCE(SUM(wallet_used),0) FROM shop_checkouts WHERE status NOT IN ('cancelled','rejected')"),
            "shop_cod":_one(conn,"SELECT COALESCE(SUM(cod_amount),0) FROM shop_checkouts WHERE status NOT IN ('cancelled','rejected')"),
            "market_revenue":_one(conn,"SELECT COALESCE(SUM(amount),0) FROM marketplace_promotion_purchases WHERE status<>'cancelled'") + _one(conn,"SELECT COALESCE(SUM(-t.amount),0) FROM wallet_transactions t WHERE t.idempotency_key LIKE 'offer_bonus:%' AND t.amount<0"),
            "beauty_revenue":_one(conn,"SELECT COALESCE(SUM(amount),0) FROM beauty_center_promotions WHERE status<>'cancelled'"),
            "ai_used":_one(conn,"SELECT COALESCE(SUM(total_used),0) FROM giso_ai_credit_accounts"),
        }
        users=_rows(conn,"""SELECT u.id,u.phone,u.name,COALESCE(SUM(CASE WHEN COALESCE(NULLIF(t.balance_scope,''),'cash')='cash' THEN t.amount ELSE 0 END),0) cash_balance,COALESCE(SUM(CASE WHEN t.balance_scope='spend' THEN t.amount ELSE 0 END),0) spend_balance,COUNT(t.id) tx_count FROM giso_web_auth u LEFT JOIN wallet_transactions t ON t.user_id=u.id AND t.status IN ('approved','paid','completed','success','used','pending') GROUP BY u.id ORDER BY tx_count DESC,u.id DESC LIMIT 200""")
        shop=_rows(conn,"SELECT id,user_id,gross_amount total_amount,wallet_used,cod_amount cod_due,status,created_at FROM shop_checkouts ORDER BY id DESC LIMIT 100")
        marketplace=_rows(conn,"SELECT 'ارتقای فروشنده' kind,listing_id source_id,user_id,package_key,amount,status,created_at FROM marketplace_promotion_purchases UNION ALL SELECT 'پیشنهاد اضافه',0,b.user_id,'offer_bonus',COALESCE((SELECT SUM(-t.amount) FROM wallet_transactions t WHERE t.idempotency_key LIKE b.transaction_key||':%' AND t.amount<0),0),'active',b.created_at FROM marketplace_offer_bonus_purchases b ORDER BY created_at DESC LIMIT 100")
        beauty=_rows(conn,"SELECT p.id,p.center_id,c.name center_name,p.owner_user_id,p.package_key,p.amount,p.status,p.created_at FROM beauty_center_promotions p LEFT JOIN beauty_centers c ON c.id=p.center_id ORDER BY p.id DESC LIMIT 100")
        ai=_rows(conn,"SELECT a.user_id,u.phone,u.name,a.balance,a.total_used,a.updated_at FROM giso_ai_credit_accounts a LEFT JOIN giso_web_auth u ON u.id=a.user_id ORDER BY a.total_used DESC,a.user_id DESC LIMIT 200")
        discrepancies={
            "negative_balances":_rows(conn,"SELECT user_id,COALESCE(NULLIF(balance_scope,''),'cash') scope,SUM(amount) balance FROM wallet_transactions WHERE status IN ('approved','paid','completed','success','used','pending') GROUP BY user_id,COALESCE(NULLIF(balance_scope,''),'cash') HAVING SUM(amount)<0"),
            "orphan_transactions":_rows(conn,"SELECT t.id,t.user_id,t.amount,t.description,t.created_at FROM wallet_transactions t LEFT JOIN giso_web_auth u ON u.id=t.user_id WHERE u.id IS NULL ORDER BY t.id DESC LIMIT 100"),
            "duplicate_keys":_rows(conn,"SELECT idempotency_key,COUNT(*) count FROM wallet_transactions WHERE idempotency_key<>'' GROUP BY idempotency_key HAVING COUNT(*)>1"),
        }
    summary["known_revenue"]=summary["shop_sales"]+summary["market_revenue"]+summary["beauty_revenue"]
    return {"finance_overview":summary,"finance_users":users,"finance_shop":shop,"finance_marketplace":marketplace,"finance_beauty":beauty,"finance_ai":ai,"finance_discrepancies":discrepancies}
