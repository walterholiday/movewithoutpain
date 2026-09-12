#!/usr/bin/env python3
'''Move Without Pain - install server-side subscription gating.

ONE file to move to the Mac. Run it from the backend repo root:

    cd ~/dev/movewithoutpain
    python3 mwp_backend_subscriptions.py

It writes entitlements.py and patches main.py in place, asserting every anchor
so a mismatch fails loudly instead of silently mangling a file. Re-running is a
no-op. main.py.bak is written before any change and restored if the result does
not compile. The embedded entitlements.py is checksummed, so a transfer that
corrupts this file is caught before anything is written.
'''

import hashlib
import os
import shutil
import sys

MAIN = "main.py"
ENTITLEMENTS_SHA256 = "8a591f1d2637d9f8334820c4575bda05715d3c458cfccfee4d0648f1b2fa1493"

ENTITLEMENTS_SOURCE = r'''"""Server-side subscription entitlements for Move Without Pain.

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
'''


def fail(msg):
    print("\n[FAILED] " + msg + "\n   Nothing was modified.")
    sys.exit(1)


actual = hashlib.sha256(ENTITLEMENTS_SOURCE.encode()).hexdigest()
if actual != ENTITLEMENTS_SHA256:
    fail("this script was corrupted in transfer (entitlements checksum mismatch).")

if not os.path.exists(MAIN):
    fail("main.py not found. Run this from the backend repo root (~/dev/movewithoutpain).")

# 0. Write entitlements.py ---------------------------------------------------
if os.path.exists("entitlements.py"):
    if open("entitlements.py", encoding="utf-8").read() != ENTITLEMENTS_SOURCE:
        shutil.copy2("entitlements.py", "entitlements.py.bak")
        print("  i  existing entitlements.py backed up to entitlements.py.bak")
with open("entitlements.py", "w", encoding="utf-8") as fh:
    fh.write(ENTITLEMENTS_SOURCE)
print("  ok entitlements.py written")

with open(MAIN, encoding="utf-8") as fh:
    src = fh.read()

if "from entitlements import" in src:
    print("Already patched - entitlements.py refreshed, nothing else to do.")
    sys.exit(0)


def sub(old, new, label):
    global src
    count = src.count(old)
    assert count == 1, "[" + label + "] expected exactly 1 match in main.py, found " + str(count)
    src = src.replace(old, new, 1)
    print("  ok " + label)


print("Patching main.py ...")

# 1. Import ------------------------------------------------------------------
sub(
    "from paths import PATHS, PATH_SLUGS, EXERCISE_PATHS\n",
    "from paths import PATHS, PATH_SLUGS, EXERCISE_PATHS\n"
    "from entitlements import (\n"
    "    Caller,\n"
    "    caller,\n"
    "    subscription_block,\n"
    "    verify_webhook,\n"
    "    handle_webhook,\n"
    "    refresh as refresh_entitlement,\n"
    ")\n",
    "import entitlements",
)

# 2. /paths signature --------------------------------------------------------
sub(
    "async def get_paths(db: Session = Depends(get_db)):",
    "async def get_paths(db: Session = Depends(get_db), c: Caller = Depends(caller)):",
    "/paths signature",
)

# 3. /paths response ---------------------------------------------------------
sub(
    """    return {
        "paths": [{**p, "exercise_count": counts.get(p["slug"], 0)} for p in sorted(PATHS, key=lambda p: p["order"])],
        "subscription": {
            # v1.0 ships free: every path is unlocked and the client shows no lock badges
            # or paywall. Flipping this to True in v1.1 (once real IAP is wired up and the
            # Paid Applications Agreement is active) re-enables gating server-side.
            "enabled": False,
            "product_id": "com.brigbrednich.movewithoutpain.premium.monthly",
            "price_usd": 19.99,
            "period": "monthly",
            "unlocks": sorted(p["slug"] for p in PATHS if p["premium"]),
        },
    }
""",
    """    return {
        "paths": [
            {
                **p,
                "exercise_count": counts.get(p["slug"], 0),
                # `unlocked` is what the client should render off. Legacy (v1.0)
                # builds ignore it and stay fully unlocked; v1.1+ builds send
                # X-MWP-Api: 2 and get honest values.
                "unlocked": c.may_access(p["premium"]),
            }
            for p in sorted(PATHS, key=lambda p: p["order"])
        ],
        "subscription": {
            **subscription_block(c),
            "unlocks": sorted(p["slug"] for p in PATHS if p["premium"]),
        },
    }
""",
    "/paths response",
)

# 4. /today signature --------------------------------------------------------
sub(
    "async def get_today(path: Optional[str] = None, db: Session = Depends(get_db)):",
    "async def get_today(\n"
    "    path: Optional[str] = None,\n"
    "    db: Session = Depends(get_db),\n"
    "    c: Caller = Depends(caller),\n"
    "):",
    "/today signature",
)

# 5. /today gate -------------------------------------------------------------
sub(
    """    if path is not None and path not in PATH_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown path '{path}'. Valid: {sorted(PATH_SLUGS)}")
""",
    """    if path is not None and path not in PATH_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown path '{path}'. Valid: {sorted(PATH_SLUGS)}")
    if path:
        requested = next((p for p in PATHS if p["slug"] == path), None)
        if requested and not c.may_access(requested["premium"]):
            raise HTTPException(
                status_code=403,
                detail={"error": "premium_required", "path": path},
            )
""",
    "/today gate",
)

# 6. Billing endpoints -------------------------------------------------------
src += '''

# --------------------------------------------------------------------------- #
# Billing (RevenueCat)
# --------------------------------------------------------------------------- #

@app.post("/billing/revenuecat/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_revenuecat_webhook_signature: Optional[str] = Header(
        default=None, alias="X-RevenueCat-Webhook-Signature"
    ),
    db: Session = Depends(get_db),
):
    """RevenueCat posts subscription lifecycle events here.

    We ignore the event's entitlement fields and re-fetch authoritative state
    from RevenueCat for every app_user_id the event mentions. Always answer 200
    on success — anything else makes RevenueCat retry (5x, backing off).
    """
    body = await request.body()
    verify_webhook(body, authorization, x_revenuecat_webhook_signature)
    payload = await request.json()
    return handle_webhook(db, payload)


@app.get("/billing/status")
async def billing_status(c: Caller = Depends(caller)):
    """What the server believes about the calling device. Used by the app after a
    purchase or restore, and by you for debugging a support ticket."""
    return {
        "app_user_id": c.app_user_id,
        "api_version": c.api_version,
        "gating_active": c.gated,
        "premium": c.premium,
    }


@app.post("/billing/refresh")
async def billing_refresh(c: Caller = Depends(caller), db: Session = Depends(get_db)):
    """Force a RevenueCat re-check for the calling device. The app calls this
    immediately after a successful purchase or restore so the server does not
    wait on the webhook."""
    if not c.app_user_id:
        raise HTTPException(status_code=400, detail="Missing X-Device-Id header")
    row = refresh_entitlement(db, c.app_user_id)
    return {
        "app_user_id": c.app_user_id,
        "premium": bool(row.is_active) if row else False,
        "expires_at": row.expires_at.isoformat() if row and row.expires_at else None,
    }
'''
print("  ✓ billing endpoints appended")

# 7. Make sure Request / Header are importable -------------------------------
if "from fastapi import FastAPI, HTTPException, Depends\n" in src:
    src = src.replace(
        "from fastapi import FastAPI, HTTPException, Depends\n",
        "from fastapi import FastAPI, HTTPException, Depends, Request, Header\n",
        1,
    )
    print("  ✓ fastapi imports extended")
else:
    fail("could not extend the fastapi import line — check main.py line 1")

# --------------------------------------------------------------------------- #

shutil.copy2(MAIN, MAIN + ".bak")
with open(MAIN, "w", encoding="utf-8") as fh:
    fh.write(src)

import py_compile

try:
    py_compile.compile(MAIN, doraise=True)
    py_compile.compile("entitlements.py", doraise=True)
except py_compile.PyCompileError as exc:
    shutil.move(MAIN + ".bak", MAIN)
    fail(f"patched file does not compile, reverted: {exc}")

print(f"\n✅ {MAIN} patched and compiles. Backup at {MAIN}.bak")
print("   Next: git add entitlements.py main.py && git commit && push, then DEPLOY on Railway")
print("   (the dashboard Deploy button — Redeploy re-runs the old commit).")
