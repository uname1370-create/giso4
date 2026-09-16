# -*- coding: utf-8 -*-
"""
monitoring_insights — موتور آفلاین «بازرس هوشمند» گیسو.

دو کار، هر دو در شغل دوره‌ای ربات (نه در لحظهٔ درخواست کاربر) اجرا می‌شوند:
  ۱) L0 عیب‌یابی: خطاهای باز giso_system_errors خوشه‌بندی و با AI تحلیل می‌شوند؛
     نتیجه در فیلد ai_triage همان خطا و یک ردیف در giso_insights ذخیره می‌گردد.
  ۲) L0 بازرس بهبود: از تجمیع‌های بدون حریم خصوصی (aggregate/report) یافته‌های
     بهبود استخراج و در giso_insights ذخیره می‌شود.

اصول:
  • هیچ تغییری در جدول‌های موجود جز افزودن ستون ai_triage (idempotent) نیست.
  • فقط دادهٔ تجمیعی/خطا به AI می‌رود؛ رکورد خام کاربر و توکن هرگز.
  • همهٔ خطاهای این ماژول بلعیده می‌شوند تا شغل ربات نشکند.
  • تحلیل فقط وقتی ذخیره می‌شود که خروجی معتبر باشد (ضد توهم).
"""
from __future__ import annotations

import json
import logging

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_insights")

ERRORS_TABLE = "giso_system_errors"
INSIGHTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_insights(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT '',
  severity TEXT DEFAULT 'info',
  title TEXT DEFAULT '',
  detail TEXT DEFAULT '',
  evidence TEXT DEFAULT '',
  suggestion TEXT DEFAULT '',
  code_hint TEXT DEFAULT '',
  confidence REAL DEFAULT 0,
  status TEXT DEFAULT 'new',
  error_fp TEXT DEFAULT '',
  source_run_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_insights_status ON giso_insights(status, severity);
CREATE INDEX IF NOT EXISTS idx_insights_kind ON giso_insights(kind);
"""


def ensure(conn=None) -> None:
    """ساخت جدول insights + افزودن ستون ai_triage به جدول خطاها (idempotent)."""
    own = conn is None
    c = conn or get_giso_db_conn()
    try:
        # جدول خطاها از ماژول monitoring_errors ساخته می‌شود؛ اول آن را تضمین کن.
        # SCHEMA همین ماژول خطاها را هم می‌سازد تا به اتصال دیگری وابسته نباشیم.
        try:
            from giso import monitoring_errors
            c.executescript(monitoring_errors.SCHEMA)
        except Exception:
            pass
        c.executescript(INSIGHTS_SCHEMA)
        # افزودن ستون تحلیل هوشمند به جدول خطاها — اگر از قبل بود بی‌اثر
        try:
            cols = {r[1] for r in c.execute("PRAGMA table_info(giso_system_errors)")}
            if cols and "ai_triage" not in cols:
                c.execute("ALTER TABLE giso_system_errors ADD COLUMN ai_triage TEXT DEFAULT ''")
            if cols and "ai_triage_at" not in cols:
                c.execute("ALTER TABLE giso_system_errors ADD COLUMN ai_triage_at TEXT DEFAULT ''")
        except Exception as exc:
            logger.debug("ai_triage column: %s", exc)
        if own:
            c.commit()
    except Exception as exc:
        logger.debug("insights ensure: %s", exc)
    finally:
        if own:
            try:
                c.close()
            except Exception:
                pass


def _sanitize(text: str, limit: int = 600) -> str:
    """حذف توکن/رمز/شماره تلفن قبل از ارسال به AI."""
    import re
    s = str(text or "")
    s = re.sub(r"(?i)(token|password|api[_-]?key|secret)\s*[=:]\s*\S+", r"\1=[حذف]", s)
    s = re.sub(r"09\d{9}", "09[حذف]", s)
    s = re.sub(r"\b\d{8,}:[\w-]+\b", "[bot-token]", s)
    return s[-limit:]


def _tables(c) -> set:
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


# ───────────────────────── L0: عیب‌یابی خطا ─────────────────────────

TRIAGE_PROMPT = (
    "تو مهندس پشتیبان ارشد هستی. فقط بر اساس اطلاعات خطای زیر تحلیل کن. "
    "حدس بی‌اطلاع نزن؛ اگر traceback کافی نبود needs_action=false بده. "
    "هیچ اقدام نوشتاری یا تغییر تنظیم پیشنهاد نده. داده خصوصی تکرار نکن. "
    "خروجی را فقط JSON معتبر با این کلیدها بده:\n"
    '{"root_cause":"یک جمله علت ریشه‌ای","location":"file.py:خط یا """,'
    '"severity":"low|medium|high","needs_action":true/false,'
    '"suggested_fix":"یک جمله راهکار کم‌ریسک","code_hint":"قطعه کد کوتاه متنی یا """,'
    '"confidence":0.0تا1.0}\n\n'
    "خطاها:\n"
)


def _collect_open_error_clusters(limit: int = 5):
    """خطاهای بازِ تحلیل‌نشده/داغ را برمی‌گرداند (خوشه = یک ردیف fingerprint)."""
    with get_giso_db_conn() as c:
        ensure(c)
        rows = c.execute(
            "SELECT fingerprint,service,section,severity,summary,count,first_seen,last_seen "
            "FROM giso_system_errors WHERE status='open' AND COALESCE(ai_triage,'')='' "
            "ORDER BY count DESC, last_seen DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]


async def triage_open_errors(max_errors: int = 5) -> int:
    """تحلیل هوشمند خطاهای باز؛ تعداد خطاهای تحلیل‌شده را برمی‌گرداند."""
    try:
        clusters = _collect_open_error_clusters(max_errors)
    except Exception as exc:
        logger.debug("triage collect: %s", exc)
        return 0
    if not clusters:
        return 0
    from giso.ai_runtime import chat_with_managed_ai
    from giso.async_compat import run_async_safe  # noqa: F401 (برای ارجاع آینده)

    done = 0
    for cl in clusters:
        payload = [{
            "service": cl.get("service"),
            "section": cl.get("section"),
            "error": _sanitize(cl.get("summary")),
            "count": cl.get("count"),
            "first_seen": cl.get("first_seen"),
            "last_seen": cl.get("last_seen"),
        }]
        try:
            res = await chat_with_managed_ai(
                [{"role": "user", "content": TRIAGE_PROMPT + json.dumps(payload, ensure_ascii=False)}],
                actor_key="monitoring:triage", role="super", channel="monitoring",
                section="reports", question_text="error triage", max_tokens=350,
            )
            if not res.get("ok"):
                continue
            triage = _parse_json_loose(res.get("text") or "")
            if not isinstance(triage, dict) or not triage.get("root_cause"):
                continue
            _persist_triage(cl, triage)
            done += 1
        except Exception as exc:
            logger.debug("triage one error failed: %s", exc)
    return done


def _persist_triage(cl: dict, triage: dict) -> None:
    """نتیجه تحلیل را روی خطا و در قفسهٔ insights ذخیره می‌کند."""
    try:
        sev = str(triage.get("severity") or "low").lower()
        if sev not in ("low", "medium", "high"):
            sev = "low"
        conf = float(triage.get("confidence") or 0)
        conf = max(0.0, min(1.0, conf))
        title = str(triage.get("root_cause") or "")[:160]
        detail = f"{cl.get('service','')} | {cl.get('section','')} | تکرار {cl.get('count')}"
        suggestion = str(triage.get("suggested_fix") or "")[:300]
        code_hint = str(triage.get("code_hint") or "")[:600]
        location = str(triage.get("location") or "")[:120]
        needs = bool(triage.get("needs_action"))
        ev = json.dumps({
            "service": cl.get("service"), "section": cl.get("section"),
            "count": cl.get("count"), "last_seen": cl.get("last_seen"),
            "location": location, "needs_action": needs,
        }, ensure_ascii=False)
        with get_giso_db_conn() as c:
            ensure(c)
            c.execute(
                "UPDATE giso_system_errors SET ai_triage=?, ai_triage_at=datetime('now','localtime') "
                "WHERE fingerprint=?",
                (json.dumps(triage, ensure_ascii=False)[:1500], cl.get("fingerprint")),
            )
            c.execute(
                "INSERT INTO giso_insights(kind,severity,title,detail,evidence,suggestion,code_hint,"
                "confidence,status,error_fp,source_run_at) VALUES('bug',?,?,?,?,?,?,?, 'new', ?, "
                "datetime('now','localtime'))",
                ("high" if (sev == "high" or needs) else sev, title,
                 f"{detail} | محل: {location or '—'}", ev, suggestion, code_hint, conf,
                 str(cl.get("fingerprint") or "")),
            )
            c.commit()
    except Exception as exc:
        logger.debug("persist triage: %s", exc)


# ───────────────────── L0: بازرس بهبود (insights) ─────────────────────

INSIGHTS_PROMPT = (
    "تو تحلیلگر محصول/UX هستی و فقط روی اعداد تجمیعی زیر کار می‌کنی (داده خصوصی نیست). "
    "حداکثر ۵ یافتهٔ عملی و کم‌هزینه بده. یافته بدون پشتوانهٔ عددی نده. "
    "اگر چیز مهمی نیست آرایهٔ خالی بده. تغییر بنیادی نده. "
    "خروجی فقط آرایهٔ JSON معتبر با این کلیدها برای هر مورد:\n"
    '{"kind":"ux_dropoff|traffic|bot_usage|queue|opportunity|content_gap|bug_trend",'
    '"severity":"info|suggestion|important","title":"...","detail":"...",'
    '"evidence":{اعداد مرجع},"suggestion":"اقدام مشخص","code_hint":"",'
    '"confidence":0.0تا1.0}\n\n'
    "داده:\n"
)


def _collect_improvement_data() -> dict:
    """تجمیع سبک و بدون هویت از منابع موجود."""
    data: dict = {}
    try:
        from giso import monitoring_ai
        data["stats"] = monitoring_ai.aggregate()
    except Exception:
        data["stats"] = {}
    try:
        from giso import monitoring_events
        beh = monitoring_events.report()
        data["top_pages"] = (beh.get("pages") or [])[:12]
        data["form_funnels"] = (beh.get("forms") or [])[:12]
        data["event_totals"] = (beh.get("totals") or [])[:12]
    except Exception:
        pass
    # شمارش صف‌های کاری (سبک)
    try:
        with get_giso_db_conn() as c:
            t = _tables(c)
            def one(sql):
                try:
                    return int(c.execute(sql).fetchone()[0] or 0)
                except Exception:
                    return 0
            queues = {}
            if "hair_orders" in t:
                queues["hair_pending"] = one("SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')")
            if "product_orders" in t:
                queues["shop_pending"] = one("SELECT COUNT(*) FROM product_orders WHERE status='pending'")
            if "giso_support_tickets" in t:
                queues["tickets_open"] = one("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')")
            if "consultant_requests" in t:
                queues["consults_open"] = one("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')")
            data["queues"] = queues
    except Exception:
        data["queues"] = {}
    return data


async def collect_improvement_insights(max_items: int = 5) -> int:
    """تحلیل اعداد تجمیعی و ذخیرهٔ یافته‌های جدید (ضد تکرار). تعداد ذخیره‌شده."""
    try:
        data = _collect_improvement_data()
    except Exception as exc:
        logger.debug("insights collect: %s", exc)
        return 0
    if not data:
        return 0
    from giso.ai_runtime import chat_with_managed_ai
    try:
        res = await chat_with_managed_ai(
            [{"role": "user", "content": INSIGHTS_PROMPT + json.dumps(data, ensure_ascii=False)[:3000]}],
            actor_key="monitoring:insights", role="super", channel="monitoring",
            section="reports", question_text="improvement insights", max_tokens=600,
        )
        if not res.get("ok"):
            return 0
        items = _parse_json_loose(res.get("text") or "")
        if not isinstance(items, list):
            return 0
    except Exception as exc:
        logger.debug("insights ai failed: %s", exc)
        return 0

    saved = 0
    for it in items[:max_items]:
        try:
            if not isinstance(it, dict) or not it.get("title") or not it.get("evidence"):
                continue
            if _save_insight(it):
                saved += 1
        except Exception as exc:
            logger.debug("save insight: %s", exc)
    return saved


def _save_insight(it: dict) -> bool:
    kind = str(it.get("kind") or "opportunity")[:30]
    sev = str(it.get("severity") or "info").lower()
    if sev not in ("info", "suggestion", "important"):
        sev = "info"
    title = str(it.get("title") or "")[:160]
    detail = str(it.get("detail") or "")[:400]
    suggestion = str(it.get("suggestion") or "")[:300]
    code_hint = str(it.get("code_hint") or "")[:600]
    ev = json.dumps(it.get("evidence") or {}, ensure_ascii=False)[:800]
    try:
        conf = max(0.0, min(1.0, float(it.get("confidence") or 0)))
    except Exception:
        conf = 0.0
    with get_giso_db_conn() as c:
        ensure(c)
        # ضد تکرار: همان kind+title در ۷ روز اخیر؟
        dup = c.execute(
            "SELECT id FROM giso_insights WHERE kind=? AND title=? "
            "AND source_run_at>=datetime('now','localtime','-7 days') LIMIT 1",
            (kind, title),
        ).fetchone()
        if dup:
            return False
        c.execute(
            "INSERT INTO giso_insights(kind,severity,title,detail,evidence,suggestion,code_hint,"
            "confidence,status,source_run_at) VALUES(?,?,?,?,?,?,?, 'new', datetime('now','localtime'))",
            (kind, sev, title, detail, ev, suggestion, code_hint, conf),
        )
        c.commit()
    return True


# ───────────────────── خواندن برای دستیار/گزارش ─────────────────────

def list_insights(status: str = "new", limit: int = 20):
    try:
        with get_giso_db_conn() as c:
            ensure(c)
            rows = c.execute(
                "SELECT * FROM giso_insights WHERE status=? ORDER BY "
                "CASE severity WHEN 'important' THEN 0 WHEN 'high' THEN 0 "
                "WHEN 'suggestion' THEN 1 ELSE 2 END, id DESC LIMIT ?",
                (status, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def set_insight_status(insight_id: int, status: str) -> bool:
    if status not in ("new", "seen", "applied", "dismissed"):
        return False
    try:
        with get_giso_db_conn() as c:
            ensure(c)
            cur = c.execute("UPDATE giso_insights SET status=? WHERE id=?", (status, int(insight_id)))
            c.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def incidents_report(limit: int = 8) -> str:
    """گزارش متنی قطعی خطایابی برای دستیار (بدون تماس AI در لحظه)."""
    try:
        from giso import monitoring_errors
        with get_giso_db_conn() as c:
            ensure(c)
            rows = c.execute(
                "SELECT service,section,severity,summary,count,last_seen,status,ai_triage "
                "FROM giso_system_errors WHERE status='open' ORDER BY count DESC,last_seen DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        if not rows:
            return "✅ خطای بازی ثبت نشده است. همه‌چیز در وضعیت عادی به نظر می‌رسد."
        lines = [f"🐞 عیب‌یابی — {len(rows)} مورد باز:"]
        # تشخیص سریع‌تر: موارد تازه‌تر از ۶۰ دقیقه را اول برجسته کن
        try:
            from datetime import datetime as _dt
            hot = []
            now = _dt.now()
            for r in rows:
                ls = str(r["last_seen"] or "")[:19]
                try:
                    age = (now - _dt.strptime(ls, "%Y-%m-%d %H:%M:%S")).total_seconds()
                except Exception:
                    age = 10**9
                if age <= 3600:
                    hot.append(r)
            if hot:
                lines.append(f"⚡ تازه‌ترین (۶۰ دقیقه): {len(hot)} مورد")
        except Exception:
            pass
        for i, r in enumerate(rows, 1):
            triage = {}
            try:
                triage = json.loads(r["ai_triage"] or "{}")
            except Exception:
                triage = {}
            sev = triage.get("severity") or r["severity"] or "error"
            lines.append(f"{i}) [{sev}] {r['section'] or r['service']} — تکرار {r['count']}، آخرین {r['last_seen']}")
            if triage.get("root_cause"):
                lines.append(f"   علت: {triage['root_cause']}")
                if triage.get("location"):
                    lines.append(f"   محل: {triage['location']}")
                if triage.get("suggested_fix"):
                    lines.append(f"   راه‌حل: {triage['suggested_fix']}")
            else:
                lines.append(f"   {str(r['summary'] or '')[:140]}")
                lines.append("   (تحلیل هوشمند این مورد هنوز آماده نشده — در اجرای بعدی شغل تکمیل می‌شود)")
        return "\n".join(lines)
    except Exception as exc:
        return f"خطا در ساخت گزارش خطایابی: {str(exc)[:120]}"


def health_report() -> str:
    """گزارش سلامت سرویس‌ها و آمار روز (قطعی، بدون AI در لحظه)."""
    try:
        from giso import monitoring_ai
        d = monitoring_ai.aggregate()
        lines = ["📊 سلامت و وضعیت سیستم:"]
        lines.append(f"• خطاهای باز: {d.get('open_errors',0)} | خطای ۲۴ساعت: {d.get('errors_24h',0)}")
        lines.append(f"• رخدادهای رفتاری ۲۴ساعت: {d.get('events_24h',0)} | ورود مشکوک: {d.get('suspicious_24h',0)}")
        lines.append(f"• پروایدر AI: {d.get('ai_providers_ok',0)} سالم")
        q = _collect_improvement_data().get("queues", {})
        if q:
            lines.append("• صف‌های کاری: " + " | ".join(f"{k}: {v}" for k, v in q.items() if v))
        return "\n".join(lines)
    except Exception as exc:
        return f"خطا در گزارش سلامت: {str(exc)[:120]}"


def improvements_report(limit: int = 8) -> str:
    """گزارش متنی پیشنهادهای بهبود جدید برای دستیار."""
    items = list_insights(status="new", limit=limit)
    if not items:
        return "💡 پیشنهاد بهبود جدیدی در انتظار نیست."
    lines = [f"💡 پیشنهادهای بهبود ({len(items)} مورد جدید):"]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}) [{it['severity']}] {it['title']}")
        if it.get("detail"):
            lines.append(f"   {it['detail'][:160]}")
        if it.get("suggestion"):
            lines.append(f"   ↳ {it['suggestion'][:160]}")
    return "\n".join(lines)


def _parse_json_loose(text: str):
    """استخراج JSON از پاسخ مدل (حتی اگر متن اضافه احاطه کرده باشد)."""
    import re
    s = str(text or "").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        i = s.find(opener)
        j = s.rfind(closer)
        if i >= 0 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except Exception:
                continue
    return None
