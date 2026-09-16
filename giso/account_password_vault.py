# -*- coding: utf-8 -*-
"""رمز فعلی حساب برای نمایش سوپرادمین — رمزگذاری‌شده، فقط اگر با هش ورود یکی باشد.

هش pbkdf2 یک‌طرفه است؛ رمز ناشناختهٔ کاربر قابل بازیابی نیست.
این خزانه فقط رمزی را نگه می‌دارد که در لحظهٔ ست‌شدن روی همان حساب نوشته شده
و هنگام نمایش با password_hash تطبیق داده می‌شود تا رمز قدیمی سوپر نشان داده نشود.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger("giso_pass_vault")

_PREFIX = "v1."
_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS giso_super_visible_pass("
    "user_id INTEGER PRIMARY KEY, password TEXT NOT NULL DEFAULT '', updated_at TEXT DEFAULT '')"
)


def _vault_secret() -> bytes:
    raw = (os.environ.get("SECRET_KEY") or os.environ.get("GISO_SECRET_KEY") or "").strip()
    if not raw:
        try:
            from giso.config import Config
            raw = str(getattr(Config, "SECRET_KEY", "") or "").strip()
        except Exception:
            raw = ""
    return raw.encode("utf-8") if raw else b""


def _derive_key(secret: bytes) -> bytes:
    return hashlib.sha256(b"giso-acct-pass-v1|" + secret).digest()


def seal_password(plain: str, secret: bytes | None = None) -> str:
    secret = secret if secret is not None else _vault_secret()
    text = str(plain or "")
    if not secret or not text:
        return ""
    key = _derive_key(secret)
    iv = os.urandom(16)
    data = text.encode("utf-8")
    stream = bytearray()
    n = 0
    while len(stream) < len(data):
        stream.extend(hashlib.sha256(key + iv + n.to_bytes(4, "big")).digest())
        n += 1
    ct = bytes(a ^ b for a, b in zip(data, stream[: len(data)]))
    mac = hmac.new(key, iv + ct, hashlib.sha256).digest()
    return _PREFIX + base64.urlsafe_b64encode(iv + mac + ct).decode("ascii")


def unseal_password(blob: str, secret: bytes | None = None) -> str:
    blob = str(blob or "").strip()
    if not blob:
        return ""
    if not blob.startswith(_PREFIX):
        return blob  # ردیف قدیمیِ plaintext
    secret = secret if secret is not None else _vault_secret()
    if not secret:
        return ""
    try:
        raw = base64.urlsafe_b64decode(blob[len(_PREFIX):].encode("ascii"))
        if len(raw) < 16 + 32:
            return ""
        iv, mac, ct = raw[:16], raw[16:48], raw[48:]
        key = _derive_key(secret)
        expect = hmac.new(key, iv + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expect):
            return ""
        stream = bytearray()
        n = 0
        while len(stream) < len(ct):
            stream.extend(hashlib.sha256(key + iv + n.to_bytes(4, "big")).digest())
            n += 1
        return bytes(a ^ b for a, b in zip(ct, stream[: len(ct)])).decode("utf-8")
    except Exception:
        return ""


def _ensure_table(conn) -> None:
    conn.execute(_TABLE_SQL)


def remember_account_password(user_id, password: str) -> None:
    """پس از هر نوشتن موفق رمز روی حساب، نسخهٔ رمزگذاری‌شده را برای سوپر نگه می‌دارد."""
    try:
        uid = int(user_id or 0)
        pwd = str(password or "")
        if uid <= 0 or not pwd:
            return
        sealed = seal_password(pwd)
        if not sealed:
            return
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            _ensure_table(conn)
            conn.execute(
                "INSERT INTO giso_super_visible_pass(user_id, password, updated_at) "
                "VALUES(?,?,datetime('now')) "
                "ON CONFLICT(user_id) DO UPDATE SET password=excluded.password, "
                "updated_at=excluded.updated_at",
                (uid, sealed),
            )
            conn.commit()
    except Exception as e:
        logger.error("remember_account_password: %s", e)


def load_stored_password(user_id) -> str:
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            _ensure_table(conn)
            row = conn.execute(
                "SELECT password FROM giso_super_visible_pass WHERE user_id=?",
                (int(user_id),),
            ).fetchone()
        if not row:
            return ""
        return unseal_password(row[0] if not hasattr(row, "keys") else row["password"])
    except Exception as e:
        logger.error("load_stored_password: %s", e)
        return ""


def current_password_if_matches(password_hash: str, candidate: str) -> str:
    """فقط اگر candidate همان رمز فعلیِ هش‌شده روی حساب باشد برمی‌گردد."""
    cand = str(candidate or "")
    ph = str(password_hash or "")
    if not cand or not ph:
        return ""
    try:
        from werkzeug.security import check_password_hash
        if check_password_hash(ph, cand):
            return cand
    except Exception:
        return ""
    return ""
