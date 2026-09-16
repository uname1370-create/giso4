#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ابزار مهاجرت SQLite → PostgreSQL (گام DB فاز ۱).

کارها:
  1) ساخت کامل schema روی PG (جداول + ایندکس‌ها) با ترجمهٔ DDL از sqlite_master
  2) انتقال ۱۰۰٪ داده‌ها از فایل SQLite (دسته‌ای، با درج شناسهٔ صریح)
  3) تنظیم دنباله‌های IDENTITY بعد از کپی (تا شناسهٔ جدید با دادهٔ موجود نسازد)
  4) راستی‌آزمایی تعداد رکوردها، جدول به جدول

معماری طبق سناریوی مصوب: giso.db → giso_db و bot_edu/data/bot.db → bot_edu_db
با اعتبارنامهٔ جدا (GISO_PG_DSN / BOT_EDU_PG_DSN). SQLite برای تست/توسعهٔ
لوکال دست‌نخورده می‌ماند؛ سوئیچ پروداکشن فقط با GISO_DB_ENGINE=postgres است.

اجرا:
  python -m giso.db_pg_tools --migrate-all          # هر دو دیتابیس از env
  python -m giso.db_pg_tools --src FILE --dsn DSN   # یک دیتابیس مشخص
  python -m giso.db_pg_tools --src FILE --dsn DSN --verify-only
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - روی سرور بدون psycopg2 پیام واضح بده
    psycopg2 = None

from giso.db_engine import (
    SQLITE_COMPAT_PG_FUNCTIONS,
    dsn_for,
    translate_ddl_sqlite_to_pg,
)

BATCH = 500


# ── خواندن schema و داده از SQLite ────────────────────────────────────
def sqlite_tables(src: sqlite3.Connection) -> list[str]:
    rows = src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def _split_top_level(body: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


_FK_INLINE = re.compile(
    r"\bREFERENCES\s+[A-Za-z_][\w]*\s*(?:\([^)]*\))?"
    r"(?:\s+ON\s+(?:DELETE|UPDATE)\s+[A-Z ]+?)*", re.I)


def extract_fks(name: str, ddl: str) -> tuple[str, list[str]]:
    """CREATE TABLE را بدون FK برمی‌گرداند + لیست ALTER TABLE ADD CONSTRAINT.
    دلیل: چرخهٔ FK (مثل hair_listings ↔ buyer_offers) با ترتیب‌دهی حل نمی‌شود؛
    FKها بعد از کپی داده اضافه و در همان لحظه اعتبارسنجی می‌شوند."""
    start, end = ddl.index("("), ddl.rindex(")")
    body, tail = ddl[start + 1:end], ddl[end:]
    keep, alters = [], []
    for i, seg in enumerate(_split_top_level(body)):
        st = seg.strip()
        if re.match(r"(?i)^FOREIGN\s+KEY\b", st):
            alters.append(f'ALTER TABLE "{name}" ADD CONSTRAINT "fk_{name}_{i}" {st}')
        elif _FK_INLINE.search(st):
            col = st.split()[0]
            m = _FK_INLINE.search(st)
            alters.append(
                f'ALTER TABLE "{name}" ADD CONSTRAINT "fk_{name}_{i}" '
                f'FOREIGN KEY ("{col}") {m.group(0).strip()}')
            keep.append(seg[:m.start()].rstrip())
        else:
            keep.append(seg)
    return ddl[:start + 1] + ",".join(keep) + tail, alters


def sqlite_ddls(src: sqlite3.Connection) -> tuple[list[tuple[str, str]], list[str]]:
    """[(نام، DDL بدون FK)] به ترتیب الفبا + همهٔ ALTERهای FK."""
    rows = src.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY name").fetchall()
    ddls, alters = [], []
    for name, sql in rows:
        d, a = extract_fks(name, sql)
        ddls.append((name, d))
        alters.extend(a)
    return ddls, alters


def sqlite_indexes(src: sqlite3.Connection) -> list[str]:
    rows = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' "
        "AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()
    return [r[0] for r in rows]


def table_columns(src: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in src.execute(f'PRAGMA table_info("{table}")').fetchall()]


# ── ساخت schema روی PG ────────────────────────────────────────────────
def create_tables(pg, src: sqlite3.Connection) -> int:
    cur = pg.cursor()
    # توابع سازگاری datetime اول ساخته شوند تا DEFAULTهای بیان‌محور کار کنند
    cur.execute(SQLITE_COMPAT_PG_FUNCTIONS)
    ddls, _ = sqlite_ddls(src)
    for _name, ddl in ddls:
        cur.execute(translate_ddl_sqlite_to_pg(ddl))
    pg.commit()
    return len(ddls)


def add_fks(pg, src: sqlite3.Connection) -> tuple[int, list[str]]:
    """FKها بعد از کپی داده اضافه می‌شوند → کل داده یک‌جا اعتبارسنجی می‌شود.
    اگر دادهٔ قدیمی یتیم داشته باشد (SQLite هرگز FK را چک نمی‌کرد)، داده حذف
    نمی‌شود: آن FK به‌صورت NOT VALID ساخته می‌شود (روی نوشتن جدید فعال است)."""
    _, alters = sqlite_ddls(src)
    cur = pg.cursor()
    not_valid: list[str] = []
    for a in alters:
        try:
            cur.execute("SAVEPOINT fk_sp")
            cur.execute(a)
            cur.execute("RELEASE SAVEPOINT fk_sp")
        except psycopg2.errors.ForeignKeyViolation:
            cur.execute("ROLLBACK TO SAVEPOINT fk_sp")
            cur.execute(a + " NOT VALID")
            name = a.split('"')[1] if '"' in a else a[:40]
            not_valid.append(name)
    pg.commit()
    return len(alters), not_valid


def create_indexes(pg, src: sqlite3.Connection) -> int:
    cur = pg.cursor()
    n = 0
    for idx in sqlite_indexes(src):
        cur.execute(translate_ddl_sqlite_to_pg(idx))
        n += 1
    pg.commit()
    return n


def _fk_triggers_off(pg) -> bool:
    """برای کپی دادهٔ دارای چرخهٔ FK؛ فقط کاربر ادمین (superuser) می‌تواند.
    روی سرور، مهاجرت را با کاربر postgres اجرا کنید (راهنمای deploy)."""
    try:
        cur = pg.cursor()
        cur.execute("SET session_replication_role = replica")
        return True
    except Exception:
        pg.rollback()
        return False


def _fk_triggers_on(pg) -> None:
    try:
        cur = pg.cursor()
        cur.execute("SET session_replication_role = origin")
        pg.commit()
    except Exception:
        pg.rollback()


# ── کپی داده ──────────────────────────────────────────────────────────
def _adapt(v):
    if isinstance(v, (bytes, bytearray, memoryview)):
        return psycopg2.Binary(bytes(v))
    return v


def _pg_col_types(pg, table: str) -> dict[str, str]:
    cur = pg.cursor()
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name=%s", (table,))
    return {r[0]: r[1] for r in cur.fetchall()}


def _coerce(v, pgtype: str):
    """SQLite بی‌نوع است؛ هم‌ترازی امن با نوع ستون PG."""
    if v is None:
        return None
    if pgtype == "boolean":
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "t", "yes", "on")
        return bool(v)
    if pgtype in ("text", "character varying", "character"):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(int(v)) if isinstance(v, int) else str(v)
    if pgtype in ("bigint", "integer", "smallint") and isinstance(v, str):
        t = v.strip()
        if t.lstrip("-").isdigit():
            return int(t)
    return v


def copy_table(src: sqlite3.Connection, pg, table: str) -> int:
    cols = table_columns(src, table)
    if not cols:
        return 0
    pgtypes = _pg_col_types(pg, table)
    collist = ",".join(f'"{c}"' for c in cols)
    marks = ",".join(["%s"] * len(cols))
    ins = f'INSERT INTO "{table}" ({collist}) VALUES ({marks})'
    sel = f'SELECT {collist} FROM "{table}"'
    total = 0
    cur_pg = pg.cursor()
    rows: list = []
    for row in src.execute(sel):
        rows.append(tuple(_adapt(_coerce(v, pgtypes.get(c, "")))
                          for c, v in zip(cols, row)))
        if len(rows) >= BATCH:
            cur_pg.executemany(ins, rows)
            total += len(rows)
            rows = []
    if rows:
        cur_pg.executemany(ins, rows)
        total += len(rows)
    pg.commit()
    return total


def copy_all(src: sqlite3.Connection, pg) -> dict[str, int]:
    return {t: copy_table(src, pg, t) for t in sqlite_tables(src)}


# ── دنباله‌های IDENTITY ───────────────────────────────────────────────
def fix_sequences(pg, tables: list[str]) -> int:
    cur = pg.cursor()
    fixed = 0
    for t in tables:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=%s AND is_identity='YES'", (t,))
        for (col,) in cur.fetchall():
            cur.execute(
                "SELECT setval(pg_get_serial_sequence(%s, %s), "
                "COALESCE((SELECT MAX(%s) FROM %s), 1), "
                "(SELECT MAX(%s) FROM %s) IS NOT NULL)"
                % ('%s', '%s', f'"{col}"', f'"{t}"', f'"{col}"', f'"{t}"'),
                (t, col))
            fixed += 1
    pg.commit()
    return fixed


# ── راستی‌آزمایی ──────────────────────────────────────────────────────
def verify(src: sqlite3.Connection, pg) -> list[tuple[str, int, int]]:
    """[(جدول، تعداد sqlite، تعداد pg)] — فقط موارد نامطابق در خروجی گزارش."""
    cur = pg.cursor()
    bad: list[tuple[str, int, int]] = []
    for t in sqlite_tables(src):
        s_count = src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        p_count = cur.fetchone()[0]
        if int(s_count) != int(p_count):
            bad.append((t, int(s_count), int(p_count)))
    return bad


# ── خط لولهٔ کامل یک دیتابیس ──────────────────────────────────────────
def migrate(sqlite_path: str, dsn: str, label: str) -> bool:
    if psycopg2 is None:
        print("❌ psycopg2 نصب نیست: pip install psycopg2-binary")
        return False
    if not os.path.exists(sqlite_path):
        print(f"❌ فایل SQLite پیدا نشد: {sqlite_path}")
        return False
    t0 = time.time()
    src = sqlite3.connect(sqlite_path)
    pg = psycopg2.connect(dsn)
    try:
        n_tables = create_tables(pg, src)
        replica = _fk_triggers_off(pg)
        try:
            copied = copy_all(src, pg)
        finally:
            if replica:
                _fk_triggers_on(pg)
        n_fks, not_valid = add_fks(pg, src)
        create_indexes(pg, src)
        fix_sequences(pg, sqlite_tables(src))
        mismatches = verify(src, pg)
        total = sum(copied.values())
        print(f"✅ {label}: {n_tables} جدول، {n_fks} FK، {total} رکورد کپی شد "
              f"({time.time() - t0:.1f}s)")
        if mismatches:
            print(f"🔴 {label}: عدم تطابق تعداد در {len(mismatches)} جدول:")
            for t, s_c, p_c in mismatches:
                print(f"   {t}: sqlite={s_c} pg={p_c}")
            return False
        if not_valid:
            print(f"🟡 {label}: {len(not_valid)} FK به‌دلیل ردیف‌های یتیمِ دادهٔ قدیمی "
                  f"به‌صورت NOT VALID ساخته شد (داده‌ای حذف نشد؛ نوشتن جدید کنترل می‌شود):")
            for n in not_valid:
                print(f"   {n}")
        print(f"🟢 {label}: راستی‌آزمایی تعداد — همهٔ جدول‌ها مطابقت دارند")
        return True
    finally:
        src.close()
        pg.close()


def verify_only(sqlite_path: str, dsn: str, label: str) -> bool:
    src = sqlite3.connect(sqlite_path)
    pg = psycopg2.connect(dsn)
    try:
        mismatches = verify(src, pg)
        if mismatches:
            print(f"🔴 {label}: {mismatches}")
            return False
        print(f"🟢 {label}: داده‌ها مطابقت دارند")
        return True
    finally:
        src.close()
        pg.close()


def migrate_all() -> bool:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok = True
    ok &= migrate(os.path.join(base, "giso", "data", "giso.db"),
                  dsn_for("giso"), "giso_db")
    ok &= migrate(os.path.join(base, "bot_edu", "data", "bot.db"),
                  dsn_for("bot"), "bot_edu_db")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="مهاجرت SQLite → PostgreSQL")
    ap.add_argument("--migrate-all", action="store_true",
                    help="هر دو دیتابیس با DSNهای env")
    ap.add_argument("--src", help="مسیر فایل SQLite")
    ap.add_argument("--dsn", help="DSN مقصد PostgreSQL")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--label", default="db")
    a = ap.parse_args(argv)
    if a.migrate_all:
        return 0 if migrate_all() else 1
    if not a.src or not a.dsn:
        ap.error("یا --migrate-all یا هر دوِ --src و --dsn لازم است")
    fn = verify_only if a.verify_only else migrate
    return 0 if fn(a.src, a.dsn, a.label) else 1


if __name__ == "__main__":
    sys.exit(main())
