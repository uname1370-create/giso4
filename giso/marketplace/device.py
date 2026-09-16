# -*- coding: utf-8 -*-
"""Privacy-aware cookie device tracking and practical marketplace anti-abuse rules."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime

from flask import current_app, g, request

from giso.models import (
    db, BuyerProfile, MarketplaceDevice, MarketplaceDeviceLink,
    MarketplacePhoneObservation, MarketplaceRiskEvent,
)

COOKIE_NAME = "giso_device_id"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _secret_bytes() -> bytes:
    secret = str(current_app.config.get("SECRET_KEY") or "giso-device-fallback")
    return secret.encode("utf-8", "ignore")


def _hash_private(value: str, purpose: str) -> str:
    payload = (purpose + "|" + str(value or "")).encode("utf-8", "ignore")
    return hmac.new(_secret_bytes(), payload, hashlib.sha256).hexdigest()


def current_device_token() -> tuple:
    """Return one stable token per request; the raw token is never persisted."""
    pending = str(getattr(g, "marketplace_new_device_cookie", "") or "").strip()
    if _TOKEN_RE.match(pending):
        return pending, True
    token = str(request.cookies.get(COOKIE_NAME) or "").strip()
    if not _TOKEN_RE.match(token):
        token = secrets.token_urlsafe(32)
        g.marketplace_new_device_cookie = token
        return token, True
    return token, False


def device_key_hash() -> str:
    token, _new = current_device_token()
    return _hash_private(token, "marketplace-device")


def browser_fingerprint_hash() -> str:
    """A low-entropy supporting signal, never a claim of unique hardware identity."""
    parts = [
        request.headers.get("User-Agent", "")[:400],
        request.headers.get("Accept-Language", "")[:120],
        request.headers.get("Sec-CH-UA", "")[:200],
        request.headers.get("Sec-CH-UA-Platform", "")[:80],
        request.headers.get("Sec-CH-UA-Mobile", "")[:20],
    ]
    return _hash_private("|".join(parts), "marketplace-browser")


def ip_hash() -> str:
    raw = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    raw = raw or request.remote_addr or "unknown"
    return _hash_private(raw, "marketplace-ip")


def _merge_flag(existing: str, flag: str) -> str:
    flags = [x.strip() for x in str(existing or "").split(",") if x.strip()]
    if flag and flag not in flags:
        flags.append(flag)
    return ",".join(flags[:12])


def _risk_for_counts(users: int, phones: int) -> str:
    """Apply the simple superadmin policy without replacing existing risk logic."""
    user_threshold = 3
    phone_threshold = 3
    try:
        from giso.marketplace.settings import marketplace_settings
        policy = marketplace_settings()
        user_threshold = int(policy.get("risk_user_threshold") or 3)
        phone_threshold = int(policy.get("risk_phone_threshold") or 3)
    except Exception:
        pass
    if users >= user_threshold or phones >= phone_threshold:
        return "suspicious_multi_account"
    if users > 1 and phones > 1:
        return "multiple_phones"
    if users > 1 or phones > 1:
        return "reused_device"
    return "clean"


def _device_correlation(device, user=None) -> tuple:
    """Return (flags, device_ids) using only clear supporting overlaps.

    Fingerprint/IP are never hard identity. We flag either a combined fingerprint+IP
    overlap, or an IP/fingerprint overlap tied to the same known user/phone.
    """
    if not device or not device.id:
        return [], []
    fp_matches = []
    ip_matches = []
    if device.fingerprint_hash:
        fp_matches = MarketplaceDevice.query.filter(
            MarketplaceDevice.id != device.id,
            MarketplaceDevice.fingerprint_hash == device.fingerprint_hash,
        ).order_by(MarketplaceDevice.id.desc()).limit(25).all()
    if device.last_ip_hash:
        ip_matches = MarketplaceDevice.query.filter(
            MarketplaceDevice.id != device.id,
            MarketplaceDevice.last_ip_hash == device.last_ip_hash,
        ).order_by(MarketplaceDevice.id.desc()).limit(25).all()

    fp_ids = {row.id for row in fp_matches}
    ip_ids = {row.id for row in ip_matches}
    both_ids = fp_ids & ip_ids
    same_identity_ids = set()
    if user is not None and getattr(user, "id", None):
        phone = str(getattr(user, "phone", "") or "")[:20]
        candidate_ids = fp_ids | ip_ids
        if candidate_ids:
            links = MarketplaceDeviceLink.query.filter(
                MarketplaceDeviceLink.device_id.in_(candidate_ids)
            ).all()
            same_identity_ids = {
                link.device_id for link in links
                if link.user_id == user.id or (phone and link.phone_snapshot == phone)
            }

    flags = []
    if both_ids:
        flags.append("fingerprint_ip_overlap")
    if same_identity_ids & fp_ids and not both_ids:
        flags.append("fingerprint_identity_overlap")
    if same_identity_ids & ip_ids and not both_ids:
        flags.append("ip_identity_overlap")
    evidence_ids = sorted(both_ids | same_identity_ids)
    return flags, evidence_ids


def touch_device(user=None, event: str = "visit"):
    """Upsert privacy-aware device evidence and optional user/phone history."""
    now = _now()
    key = device_key_hash()
    correlation_event = None
    try:
        device = MarketplaceDevice.query.filter_by(device_key_hash=key).first()
        if not device:
            device = MarketplaceDevice(
                device_key_hash=key,
                fingerprint_hash=browser_fingerprint_hash(),
                last_ip_hash=ip_hash(),
                first_seen_at=now,
                last_seen_at=now,
                risk_level="clean",
                correlation_flags="",
                correlation_evidence="",
                correlated_device_count=0,
            )
            db.session.add(device)
            db.session.flush()
        else:
            device.last_seen_at = now
            device.fingerprint_hash = browser_fingerprint_hash()
            device.last_ip_hash = ip_hash()

        previous_risk = device.risk_level or "clean"
        previous_correlation = f"{device.correlation_flags or ''}|{device.correlation_evidence or ''}"
        phone = ""
        if user is not None and getattr(user, "id", None):
            phone = str(getattr(user, "phone", "") or "")[:20]
            link = MarketplaceDeviceLink.query.filter_by(device_id=device.id, user_id=user.id).first()
            if not link:
                link = MarketplaceDeviceLink(
                    device_id=device.id,
                    user_id=user.id,
                    phone_snapshot=phone,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_event=str(event or "visit")[:40],
                )
                db.session.add(link)
            else:
                link.last_seen_at = now
                link.last_event = str(event or "visit")[:40]
                if phone:
                    link.phone_snapshot = phone

            if phone:
                observation = MarketplacePhoneObservation.query.filter_by(
                    device_id=device.id, user_id=user.id, phone_snapshot=phone,
                ).first()
                if not observation:
                    observation = MarketplacePhoneObservation(
                        device_id=device.id, user_id=user.id, phone_snapshot=phone,
                        first_seen_at=now, last_seen_at=now, observation_count=1,
                        last_event=str(event or "visit")[:40],
                    )
                    db.session.add(observation)
                else:
                    observation.last_seen_at = now
                    observation.last_event = str(event or "visit")[:40]
                    observation.observation_count = int(observation.observation_count or 0) + 1
            db.session.flush()

        links = MarketplaceDeviceLink.query.filter_by(device_id=device.id).all()
        observations = MarketplacePhoneObservation.query.filter_by(device_id=device.id).all()
        user_count = len({int(link.user_id) for link in links if link.user_id})
        phone_count = len({str(row.phone_snapshot) for row in observations if row.phone_snapshot})
        direct_risk = _risk_for_counts(user_count, phone_count)

        correlation_flags, correlated_ids = _device_correlation(device, user)
        evidence = ",".join(str(item) for item in correlated_ids)
        device.linked_user_count = user_count
        device.linked_phone_count = phone_count
        device.correlation_flags = ",".join(correlation_flags)
        device.correlation_evidence = evidence
        device.correlated_device_count = len(correlated_ids)
        if direct_risk != "clean":
            device.risk_level = direct_risk
        elif "fingerprint_ip_overlap" in correlation_flags:
            device.risk_level = "fingerprint_ip_overlap"
        elif correlation_flags:
            device.risk_level = "cookie_reset_signal"
        else:
            device.risk_level = "clean"

        correlation_signature = f"{device.correlation_flags or ''}|{evidence}"
        if correlation_flags and correlation_signature != previous_correlation:
            correlation_event = MarketplaceRiskEvent(
                event_type="device_correlation",
                status="flagged",
                user_id=(getattr(user, "id", None) if user is not None else None),
                phone_snapshot=phone,
                device_id=device.id,
                device_hash_short=(device.device_key_hash or "")[:12],
                fingerprint_hash=device.fingerprint_hash or "",
                ip_hash=device.last_ip_hash or "",
                risk_level=device.risk_level,
                reason=correlation_flags[0],
                reason_detail="Supporting cookie-reset correlation; never a hard identity.",
                correlation_evidence=evidence,
                created_at=now,
            )
            db.session.add(correlation_event)

        if user is not None and getattr(user, "id", None):
            profile = BuyerProfile.query.filter_by(user_id=user.id).first()
            if profile:
                profile.latest_device_key = key
                if phone:
                    profile.phone_snapshot = phone
                profile.updated_at = now
                if device.risk_level != "clean":
                    profile.risk_flags = _merge_flag(profile.risk_flags, device.risk_level)

        db.session.commit()
        setattr(device, "risk_changed", previous_risk != device.risk_level)
        if correlation_event and correlation_event.id and event != "offer":
            try:
                from giso.marketplace.services import notify_risk
                notify_risk(
                    device, user_id=getattr(user, "id", 0) if user is not None else 0,
                    reason=correlation_event.reason, event_id=correlation_event.id,
                    event_type=correlation_event.event_type,
                )
            except Exception:
                pass
        return device
    except Exception:
        db.session.rollback()
        return None


def set_device_cookie(response):
    token = getattr(g, "marketplace_new_device_cookie", "")
    if token:
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=bool(request.is_secure),
            samesite="Lax",
            path="/",
        )
    return response


def device_summary(device) -> dict:
    if not device:
        return {"signature": "—", "risk_level": "unknown", "linked_users": 0, "linked_phones": 0}
    return {
        "signature": (device.device_key_hash or "")[:12],
        "fingerprint": (device.fingerprint_hash or "")[:12],
        "risk_level": device.risk_level or "clean",
        "linked_users": int(device.linked_user_count or 0),
        "linked_phones": int(device.linked_phone_count or 0),
        "correlation_flags": device.correlation_flags or "",
        "correlated_devices": int(device.correlated_device_count or 0),
    }


__all__ = [
    "COOKIE_NAME", "current_device_token", "device_key_hash", "touch_device",
    "set_device_cookie", "device_summary",
]
