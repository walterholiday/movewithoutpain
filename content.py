"""Content tiering, grandfathering, and Mux signed playback.

The model, per Sandy's decision of 2026-09-18:

- Every exercise carries a `tier`: "free" or "premium".
- Exercises that shipped in v1.0 are flagged `in_v1_library`. Devices that were
  already using the app before v1.1 keep ALL of those permanently, whatever their
  tier — "they should keep access to the content that was available to them when
  they joined."
- New users get only `tier == "free"` exercises until they subscribe.
- New filmed content is `tier == "premium"` and is NOT in the v1 library, so
  grandfathered users do not get it for free.

Locked exercises are still returned by the API so the app can show them with a
lock badge — people pay for what they can see — but their video identifiers are
stripped, so a locked row never leaks a playable URL.

Video lives in two places and that is deliberate:
- The original 14 stay on unlisted YouTube. v1.0 is live and reads
  `youtube_video_id` from `/today`; removing it would break video for every
  phone in the field. They are free content anyway, so signing them buys nothing.
- New premium content is on Mux with **signed** playback. A leaked URL expires in
  minutes instead of never.

Environment variables
---------------------
  MUX_SIGNING_KEY_ID        Mux signing key id
  MUX_SIGNING_KEY_PRIVATE   the base64-encoded RSA private key Mux gave you
  MUX_TOKEN_TTL_SECONDS     optional, default 600
"""

import base64
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import Session

from models import Base, engine

log = logging.getLogger("content")

TIER_FREE = "free"
TIER_PREMIUM = "premium"

MUX_SIGNING_KEY_ID = os.getenv("MUX_SIGNING_KEY_ID", "").strip()
MUX_SIGNING_KEY_PRIVATE = os.getenv("MUX_SIGNING_KEY_PRIVATE", "").strip()
MUX_TOKEN_TTL = int(os.getenv("MUX_TOKEN_TTL_SECONDS", "600"))

MUX_STREAM_BASE = "https://stream.mux.com"
MUX_IMAGE_BASE = "https://image.mux.com"

# A device may only claim grandfathered status if it can show practice history
# older than this. v1.0 shipped in August 2026; anything claiming to predate this
# is a device that really was using the app before the paywall existed.
V1_CUTOFF = datetime(2026, 9, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Grandfathered devices
# --------------------------------------------------------------------------- #

class LegacyDevice(Base):
    """A device that was using the app before v1.1 and keeps the v1 library."""

    __tablename__ = "legacy_devices"

    app_user_id = Column(String(191), primary_key=True)
    claimed_at = Column(DateTime(timezone=True), nullable=False)
    earliest_practice = Column(DateTime(timezone=True), nullable=True)


Base.metadata.create_all(engine)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_grandfathered(db: Session, app_user_id: Optional[str]) -> bool:
    if not app_user_id:
        return False
    return db.get(LegacyDevice, app_user_id) is not None


def claim_legacy(db: Session, app_user_id: str, earliest_practice_iso: Optional[str]) -> dict:
    """Record a device as pre-v1.1, on the strength of its own practice history.

    Honest limitation: v1.0 never sent a device id, so the server has no record
    of who existed before v1.1 — the client's claim is the only evidence there is.
    It is accepted once and then fixed, and the claimed date must predate the
    cutoff. Someone determined could forge it; the exposure is one free library
    on one device, which is not worth defending against harder than this.
    """
    existing = db.get(LegacyDevice, app_user_id)
    if existing is not None:
        return {"granted": True, "already_claimed": True}

    earliest = _parse_iso(earliest_practice_iso)
    if earliest is None or earliest >= V1_CUTOFF:
        return {"granted": False, "already_claimed": False}

    db.add(
        LegacyDevice(
            app_user_id=app_user_id,
            claimed_at=datetime.now(timezone.utc),
            earliest_practice=earliest,
        )
    )
    db.commit()
    log.info("Granted legacy access to %s (earliest practice %s)", app_user_id, earliest)
    return {"granted": True, "already_claimed": False}


# --------------------------------------------------------------------------- #
# Who may see what
# --------------------------------------------------------------------------- #

def exercise_unlocked(exercise, *, gated: bool, premium: bool, grandfathered: bool) -> bool:
    """Whether this caller may actually open this exercise.

    `gated` is False for v1.0 clients and whenever the subscription system is
    switched off — both of which mean everything stays open, exactly as today.
    """
    if not gated:
        return True
    if (exercise.tier or TIER_FREE) == TIER_FREE:
        return True
    if premium:
        return True
    # Grandfathered devices keep everything that shipped in v1.0, tier regardless.
    return bool(grandfathered and getattr(exercise, "in_v1_library", False))


def public_exercise(exercise, unlocked: bool) -> dict:
    """Serialise an exercise, stripping video identifiers when it is locked."""
    data = {
        "id": exercise.id,
        "category": exercise.category,
        "order": exercise.order,
        "name_en": exercise.name_en,
        "name_es": exercise.name_es,
        "description_en": exercise.description_en,
        "description_es": exercise.description_es,
        "reps_or_time_en": exercise.reps_or_time_en,
        "reps_or_time_es": exercise.reps_or_time_es,
        "tips_en": exercise.tips_en,
        "tips_es": exercise.tips_es,
        "youtube_video_id": exercise.youtube_video_id,
        "mux_playback_id": getattr(exercise, "mux_playback_id", None),
        "paths": exercise.paths,
        # Sandy ruled the "why this works" notes free for everyone, so they are
        # deliberately NOT stripped on locked rows — they are the shop window.
        "neuro_tag": exercise.neuro_tag,
        "neuro_why_en": exercise.neuro_why_en,
        "neuro_why_es": exercise.neuro_why_es,
        "tier": exercise.tier or TIER_FREE,
        "unlocked": unlocked,
    }
    if not unlocked:
        data["youtube_video_id"] = None
        data["mux_playback_id"] = None
    return data


# --------------------------------------------------------------------------- #
# Mux signed playback
# --------------------------------------------------------------------------- #

MUX_CONFIGURED = bool(MUX_SIGNING_KEY_ID and MUX_SIGNING_KEY_PRIVATE)


def _private_key_pem() -> bytes:
    """Mux hands you the RSA private key base64-encoded. Accept either form."""
    raw = MUX_SIGNING_KEY_PRIVATE
    if "BEGIN" in raw:
        return raw.encode()
    return base64.b64decode(raw)


def sign_playback(playback_id: str, audience: str = "v", ttl: Optional[int] = None) -> Optional[str]:
    """Mint a short-lived RS256 JWT for one Mux playback id.

    Claims per Mux's spec: sub = playback id, aud = "v" for video or "t" for
    thumbnails, exp = unix expiry, kid = signing key id.
    """
    if not MUX_CONFIGURED:
        return None
    try:
        import jwt  # pyjwt[crypto]
    except ImportError:
        log.error("pyjwt[crypto] is not installed — cannot sign Mux playback")
        return None

    try:
        return jwt.encode(
            {
                "sub": playback_id,
                "aud": audience,
                "exp": int(time.time()) + (ttl or MUX_TOKEN_TTL),
                "kid": MUX_SIGNING_KEY_ID,
            },
            _private_key_pem(),
            algorithm="RS256",
            headers={"kid": MUX_SIGNING_KEY_ID},
        )
    except Exception as exc:
        log.error("Mux token signing failed: %s", exc)
        return None


def playback_urls(playback_id: str, ttl: Optional[int] = None) -> Optional[dict]:
    """Signed HLS + thumbnail URLs for a Mux asset, or None if unsigned."""
    video_token = sign_playback(playback_id, "v", ttl)
    if video_token is None:
        return None
    thumb_token = sign_playback(playback_id, "t", ttl)
    return {
        "hls_url": f"{MUX_STREAM_BASE}/{playback_id}.m3u8?token={video_token}",
        "thumbnail_url": f"{MUX_IMAGE_BASE}/{playback_id}/thumbnail.jpg?token={thumb_token}",
        "expires_in": ttl or MUX_TOKEN_TTL,
    }
