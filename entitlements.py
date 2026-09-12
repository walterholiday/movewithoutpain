"""Server-side subscription entitlements for Move Without Pain.

Design notes
------------
The app has no user accounts. Identity is an anonymous, app-generated UUID
("app user id") stored in the iOS keychain via expo-secure-store, passed to
RevenueCat as the appUserID and sent to this API as the `X-Device-Id` header.

RevenueCat is the source of truth for entitlements. This module keeps a local
cache so the hot path (`/today`) does not make a network call on every request:

  1. RevenueCat webhooks POST to /billing/revenuecat/webhook. We do not trust
     the event body's entitlement fields — we take the app_user_id(s) out of it
     and re-fetch authoritative state from the RevenueCat REST API. That means
     we never have to model every event type correctly.
  2. Reads fall back to a lazy refresh when the cached row is missing, stale, or
     past its expiry. This covers dropped webhooks and the first-purchase race
     (app finishes purchase and calls us before the webhook lands).
  3. If RevenueCat is unreachable, a previously-active subscriber keeps access
     for GRACE_DAYS. Never lock out a paying customer because of our outage.

Backwards compatibility
-----------------------
v1.0 is live on the App Store with every routine free and no device header.
Gating is applied ONLY to clients that send `X-MWP-Api: 2` (v1.1 and later).
Older builds keep the exact behaviour they shipped with.

Environment variables
---------------------
  REVENUECAT_SECRET_API_KEY   required to enable gating (RevenueCat "secret" key, sk_...)
  REVENUECAT_WEBHOOK_AUTH     required; value RevenueCat sends in the Authorization header
  SUBSCRIPTIONS_ENABLED       "true" to turn gating on (default false — safe deploys)
  PREMIUM_ENTITLEMENT_ID      RevenueCat entitlement identifier (default "premium")
  RC_PRODUCT_MONTHLY          App Store product id for the monthly plan
  RC_PRODUCT_ANNUAL           App Store product id for the annual plan
"""

import os
import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Iterable
from urllib.parse import quote

import httpx
from fastapi import Header, HTTPException
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import Session

from models import Base, engine, SessionLocal

log = logging.getLogger("entitlements")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

RC_SECRET_KEY = os.getenv("REVENUECAT_SECRET_API_KEY", "").strip()
RC_WEBHOOK_AUTH = os.getenv("REVENUECAT_WEBHOOK_AUTH", "").strip()
RC_WEBHOOK_HMAC_SECRET = os.getenv("REVENUECAT_WEBHOOK_HMAC_SECRET", "").strip()
PREMIUM_ENTITLEMENT_ID = os.getenv("PREMIUM_ENTITLEMENT_ID", "premium").strip()

PRODUCT_MONTHLY = os.getenv(
    "RC_PRODUCT_MONTHLY", "com.brigbrednich.movewithoutpain.premium.monthly"
).strip()
PRODUCT_ANNUAL = os.getenv(
    "RC_PRODUCT_ANNUAL", "com.brigbrednich.movewithoutpain.premium.annual"
).strip()

# Master switch. Gating also requires a secret key to be present — without one
# we cannot verify anything, so we fail OPEN rather than locking everyone out.
SUBSCRIPTIONS_ENABLED = (
    os.getenv("SUBSCRIPTIONS_ENABLED", "false").strip().lower() in ("1", "true", "yes")
    and bool(RC_SECRET_KEY)
)

# Only clients sending this API version get gated. v1.0 builds send nothing.
GATED_API_VERSION = 2

POSITIVE_TTL = timedelta(hours=6)     # re-check an active subscriber this often
NEGATIVE_TTL = timedelta(minutes=5)   # re-check a non-subscriber this often
GRACE = timedelta(days=3)             # keep access this long if RevenueCat is down

RC_API_BASE = "https://api.revenuecat.com/v1"
RC_TIMEOUT = 6.0


# --------------------------------------------------------------------------- #
# Cache table
# --------------------------------------------------------------------------- #

class SubscriberEntitlement(Base):
    """Local cache of one app-user's premium entitlement, per RevenueCat."""

    __tablename__ = "subscriber_entitlements"

    app_user_id = Column(String(191), primary_key=True)
    is_active = Column(Boolean, nullable=False, default=False)
    product_id = Column(String(191), nullable=True)
    store = Column(String(32), nullable=True)
    environment = Column(String(20), nullable=True)      # SANDBOX | PRODUCTION
    expires_at = Column(DateTime(timezone=True), nullable=True)  # None = non-expiring
    checked_at = Column(DateTime(timezone=True), nullable=False)


# models.py already ran create_all() for its own tables at import time; this
# picks up the new one without touching models.py.
Base.metadata.create_all(engine)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Postgres may hand back naive datetimes depending on driver/column type."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# RevenueCat REST
# --------------------------------------------------------------------------- #

def _parse_rc_datetime(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_from_revenuecat(app_user_id: str) -> Optional[dict]:
    """GET /subscribers/{id}. Returns a normalised dict, or None on failure.

    None means "could not determine" (network/auth problem) — NOT "not
    subscribed". Callers must distinguish the two.
    """
    if not RC_SECRET_KEY:
        return None
    # App user ids are ours (UUIDs), but RevenueCat anonymous ids contain ':' and '$'.
    url = f"{RC_API_BASE}/subscribers/{quote(app_user_id, safe='')}"
    try:
        with httpx.Client(timeout=RC_TIMEOUT) as client:
            resp = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {RC_SECRET_KEY}",
                    "Accept": "application/json",
                },
            )
        if resp.status_code != 200:
            log.warning("RevenueCat %s for %s: %s", resp.status_code, app_user_id, resp.text[:300])
            return None
        subscriber = resp.json().get("subscriber", {}) or {}
    except Exception as exc:  # network, JSON, anything
        log.warning("RevenueCat fetch failed for %s: %s", app_user_id, exc)
        return None

    ent = (subscriber.get("entitlements") or {}).get(PREMIUM_ENTITLEMENT_ID)
    if not ent:
        return {
            "is_active": False,
            "product_id": None,
            "expires_at": None,
            "store": None,
            "environment": None,
        }

    expires_at = _parse_rc_datetime(ent.get("expires_date"))
    product_id = ent.get("product_identifier")
    sub = (subscriber.get("subscriptions") or {}).get(product_id, {}) or {}

    return {
        # expires_date == None means a non-expiring entitlement (lifetime / granted)
        "is_active": expires_at is None or expires_at > _now(),
        "product_id": product_id,
        "expires_at": expires_at,
        "store": sub.get("store"),
        "environment": (sub.get("is_sandbox") and "SANDBOX") or "PRODUCTION",
    }


def _upsert(db: Session, app_user_id: str, data: dict) -> SubscriberEntitlement:
    row = db.get(SubscriberEntitlement, app_user_id)
    if row is None:
        row = SubscriberEntitlement(app_user_id=app_user_id)
        db.add(row)
    row.is_active = bool(data["is_active"])
    row.product_id = data.get("product_id")
    row.store = data.get("store")
    row.environment = data.get("environment")
    row.expires_at = data.get("expires_at")
    row.checked_at = _now()
    db.commit()
    return row


def _refresh(db: Session, app_user_id: str):
    """Returns (row, fetch_ok). fetch_ok distinguishes "RevenueCat said no" from
    "we could not reach RevenueCat" — only the latter earns a grace period."""
    data = fetch_from_revenuecat(app_user_id)
    if data is None:
        return db.get(SubscriberEntitlement, app_user_id), False
    return _upsert(db, app_user_id, data), True


def refresh(db: Session, app_user_id: str) -> Optional[SubscriberEntitlement]:
    row, _ = _refresh(db, app_user_id)
    return row


# --------------------------------------------------------------------------- #
# The question everything else asks
# --------------------------------------------------------------------------- #

def is_premium(db: Session, app_user_id: Optional[str]) -> bool:
    if not app_user_id:
        return False

    row = db.get(SubscriberEntitlement, app_user_id)
    now = _now()

    if row is not None:
        checked_at = _aware(row.checked_at)
        expires_at = _aware(row.expires_at)
        unexpired = expires_at is None or expires_at > now
        age = now - checked_at if checked_at else GRACE * 10
        ttl = POSITIVE_TTL if row.is_active else NEGATIVE_TTL
        if age < ttl and (unexpired or not row.is_active):
            return bool(row.is_active)

    row, fetch_ok = _refresh(db, app_user_id)
    if row is None:
        return False

    expires_at = _aware(row.expires_at)
    if row.is_active and (expires_at is None or expires_at > now):
        return True

    if fetch_ok:
        # RevenueCat answered and the answer is no. Cancelled, expired, refunded.
        return False

    # We could NOT reach RevenueCat. Hold the door open for a recently-active
    # subscriber rather than locking out a paying customer during our outage.
    checked_at = _aware(row.checked_at)
    if row.is_active and checked_at and (now - checked_at) < GRACE:
        if expires_at is None or expires_at > (now - GRACE):
            log.warning("Serving %s on grace — RevenueCat unreachable", app_user_id)
            return True
    return False


# --------------------------------------------------------------------------- #
# FastAPI plumbing
# --------------------------------------------------------------------------- #

class Caller:
    """Who is asking, and whether their build understands gating."""

    __slots__ = ("app_user_id", "api_version", "premium")

    def __init__(self, app_user_id: Optional[str], api_version: int, premium: bool):
        self.app_user_id = app_user_id
        self.api_version = api_version
        self.premium = premium

    @property
    def gated(self) -> bool:
        """True when this caller's build opted in to server-side gating."""
        return SUBSCRIPTIONS_ENABLED and self.api_version >= GATED_API_VERSION

    def may_access(self, path_is_premium: bool) -> bool:
        return (not path_is_premium) or (not self.gated) or self.premium


def caller(
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
    x_mwp_api: Optional[str] = Header(default=None, alias="X-MWP-Api"),
) -> Caller:
    """Sync dependency — FastAPI runs it in a threadpool, so the RevenueCat
    round-trip never blocks the event loop."""
    try:
        api_version = int(x_mwp_api) if x_mwp_api else 1
    except (TypeError, ValueError):
        api_version = 1

    device_id = (x_device_id or "").strip()[:191] or None

    if not (SUBSCRIPTIONS_ENABLED and api_version >= GATED_API_VERSION and device_id):
        return Caller(device_id, api_version, False)

    db = SessionLocal()
    try:
        return Caller(device_id, api_version, is_premium(db, device_id))
    finally:
        db.close()


def subscription_block(c: Caller) -> dict:
    """The `subscription` object returned by /paths."""
    return {
        # Legacy (v1.0) clients must keep seeing enabled:false — they render lock
        # badges off that field and shipped with every routine free.
        "enabled": c.gated,
        "entitlement_id": PREMIUM_ENTITLEMENT_ID,
        "products": {"monthly": PRODUCT_MONTHLY, "annual": PRODUCT_ANNUAL},
        "active": bool(c.premium),
        # Prices deliberately absent: the client reads localized priceString from
        # RevenueCat offerings. Hardcoding USD is a 3.1.2 rejection in Spain.
    }


# --------------------------------------------------------------------------- #
# Webhook
# --------------------------------------------------------------------------- #

def _candidate_ids(event: dict) -> Iterable[str]:
    seen = set()
    for key in ("app_user_id", "original_app_user_id"):
        val = event.get(key)
        if val and val not in seen:
            seen.add(val)
            yield val
    for key in ("aliases", "transferred_from", "transferred_to"):
        for val in event.get(key) or []:
            if val and val not in seen:
                seen.add(val)
                yield val


def verify_webhook(request_body: bytes, authorization: Optional[str], signature: Optional[str]) -> None:
    """Raise 401 unless the request proves it came from RevenueCat."""
    if not RC_WEBHOOK_AUTH:
        raise HTTPException(status_code=503, detail="Webhook auth not configured")

    if not authorization or not hmac.compare_digest(authorization, RC_WEBHOOK_AUTH):
        raise HTTPException(status_code=401, detail="Bad webhook authorization")

    if RC_WEBHOOK_HMAC_SECRET:
        # Header form: t=<unix_ts>,v1=<hex hmac of "<t>.<raw body>">
        parts = dict(
            piece.split("=", 1) for piece in (signature or "").split(",") if "=" in piece
        )
        ts, provided = parts.get("t"), parts.get("v1")
        if not ts or not provided:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        expected = hmac.new(
            RC_WEBHOOK_HMAC_SECRET.encode(),
            f"{ts}.".encode() + request_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise HTTPException(status_code=401, detail="Bad webhook signature")


def handle_webhook(db: Session, payload: dict) -> dict:
    """Re-fetch authoritative state for every user id the event touches.

    We deliberately ignore the event's own entitlement fields. Fetching is one
    extra call per event at this volume and removes a whole class of bugs around
    TRANSFER, PRODUCT_CHANGE, billing retry and refund semantics.
    """
    event = payload.get("event") or {}
    ids = list(_candidate_ids(event))
    refreshed = []
    for app_user_id in ids:
        row = refresh(db, app_user_id)
        if row is not None:
            refreshed.append({"app_user_id": app_user_id, "is_active": bool(row.is_active)})
    log.info("RevenueCat webhook %s → refreshed %s", event.get("type"), refreshed)
    return {"ok": True, "event_type": event.get("type"), "refreshed": refreshed}
