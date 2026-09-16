# -*- coding: utf-8 -*-
"""Public and authenticated hair marketplace routes on the existing Giso app/auth."""
import logging
import re
import traceback

from flask import Blueprint


_SENSITIVE_LOG_PATTERNS = (
    (re.compile(r"(?<!\d)(?:\+?98|0098|0)?9\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(?i)(?:/bot)[^/\s]+"), "/bot[REDACTED_TOKEN]"),
    (re.compile(r"(?i)\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(
        r"(?i)(\b(?:phone|mobile|address|full_name|name|token|password|passwd|api[_-]?key|"
        r"session(?:[_-]?token|[_-]?id)?|secret)\b\s*[:=]\s*)[^\n,;&]+"
    ), r"\1[REDACTED]"),
    (re.compile(
        r"((?:شماره(?:\s+(?:تلفن|تماس|همراه))?|آدرس|نام\s+کامل|توکن|رمز\s+عبور|کلید\s+API)\s*[:=]\s*)[^\n,;]+"
    ), r"\1[حذف‌شده]"),
)


def redact_sensitive_log_text(value) -> str:
    """Remove common credentials and personal identifiers before log formatting."""
    text = str(value or "")
    for pattern, replacement in _SENSITIVE_LOG_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _install_sensitive_log_record_factory() -> None:
    """Install once so future application logs cannot emit common raw secrets/PII."""
    if getattr(logging, "_giso_sensitive_log_factory_installed", False):
        return
    previous_factory = logging.getLogRecordFactory()

    def safe_factory(*args, **kwargs):
        record = previous_factory(*args, **kwargs)
        try:
            record.msg = redact_sensitive_log_text(record.getMessage())
            record.args = ()
            if record.exc_info:
                rendered = "".join(traceback.format_exception(*record.exc_info))
                record.msg += "\n" + redact_sensitive_log_text(rendered)
                record.exc_text = None
                record.exc_info = None
        except Exception:
            record.msg = "[REDACTED_LOG_RECORD]"
            record.args = ()
            record.exc_info = None
        return record

    logging.setLogRecordFactory(safe_factory)
    logging._giso_sensitive_log_factory_installed = True


_install_sensitive_log_record_factory()

marketplace_bp = Blueprint("marketplace", __name__)

from giso.marketplace import routes  # noqa: E402,F401

__all__ = ["marketplace_bp", "redact_sensitive_log_text"]
