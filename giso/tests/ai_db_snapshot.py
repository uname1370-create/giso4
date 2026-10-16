# -*- coding: utf-8 -*-
"""ذخیره و بازگردانی کامل جدول‌های Provider/تخصیص مدل برای تست‌های پنل AI.

تست‌های افزودن Provider ردیف واقعی در giso.db می‌سازند، تخصیص اسلات آینه گیسو
را خودکار پر می‌کنند و گاهی ردیف‌های seed شدهٔ رجیستری را پر می‌کنند. برای اینکه
تست‌های بعدی وضعیت قبلی را ببینند، این ماژول دقیقاً همان محتوای جدول‌ها را
قبل از تست ذخیره و بعد از تست برمی‌گرداند. هیچ داده‌ای در فایل نوشته نمی‌شود.
"""
from giso.base import get_giso_db_conn

TABLES = (
    "giso_ai_providers",
    "giso_ai_provider_tombstones",
    "buti_ai_model_assignments",
)


def snapshot():
    conn = get_giso_db_conn()
    try:
        snap = {}
        for table in TABLES:
            try:
                cur = conn.execute(f"SELECT * FROM {table}")
                cols = [d[0] for d in cur.description]
                snap[table] = (cols, [tuple(r) for r in cur.fetchall()])
            except Exception:
                snap[table] = None  # جدول هنوز ساخته نشده است
        return snap
    finally:
        conn.close()


def restore(snap):
    conn = get_giso_db_conn()
    try:
        for table, data in snap.items():
            if data is None:
                continue
            cols, rows = data
            conn.execute(f"DELETE FROM {table}")
            if rows:
                conn.executemany(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    rows)
        conn.commit()
    finally:
        conn.close()
