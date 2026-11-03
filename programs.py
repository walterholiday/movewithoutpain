"""Multi-week programs (Felix's 2026-10-30 brief: Morning Routine, Week 1 · Gentle).

A program lives inside one routine card (the "morning" path). Each week has one
guided meditation and one movement video that repeat every day; what changes
from day to day is the "intention of the day". Days 1-6 are meditation, then
movement; Day 7 is meditation only (active rest).

Videos are public Mux assets for free weeks (like Felix's intro clips), uploaded
by tools/program_upload.py, which writes program_playback_ids.json:
    {"morning-w1-meditation": "<id>", "morning-w1-movement": "<id>",
     "morning-ambient": "<id>"}
A missing id means "not uploaded yet": the week is listed but not playable.

Chapters for a movement video come from program_content/<key>.txt, one per line:
    0:00 Respiración / Breathing
    1:15 Círculos de cadera / Hip circles
Text before " / " is Spanish, after it English (English is optional).

Progress is kept on the phone (like the practice dates and streak); the server
only describes the program. Clients see this from X-MWP-Api >= 4 (app 1.3.0).
"""

from __future__ import annotations

import json as _json
import os as _os
import re as _re
from typing import Optional

PROGRAMS_API_VERSION = 4

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_IDS_FILE = _os.path.join(_HERE, "program_playback_ids.json")
_CONTENT_DIR = _os.path.join(_HERE, "program_content")

# One new day per calendar day ("7-day challenge"). Off while Felix tests on
# TestFlight so all seven days can be walked through in one sitting; set the
# Railway variable PROGRAM_DAILY_PACING=1 before release. Read per request so
# flipping the variable needs no code change.
def daily_pacing() -> bool:
    return _os.environ.get("PROGRAM_DAILY_PACING", "0").strip().lower() in ("1", "true", "yes", "on")


def _load_ids() -> dict:
    try:
        with open(_IDS_FILE, encoding="utf-8") as fh:
            return _json.load(fh)
    except FileNotFoundError:
        return {}


PROGRAM_PLAYBACK_IDS: dict = _load_ids()

_TIME = _re.compile(r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*[-–—:|.)]?\s*(.+?)\s*$")


def parse_chapters(text: str) -> list:
    """Lines like "1:15 Círculos de cadera / Hip circles" -> chapters sorted by start.
    Lines without a leading timestamp are ignored (headings, blank lines)."""
    chapters = []
    for line in text.splitlines():
        m = _TIME.match(line)
        if not m:
            continue
        h, mnt, sec, title = m.groups()
        start = int(h or 0) * 3600 + int(mnt) * 60 + int(sec)
        es, _, en = title.partition(" / ")
        es, en = es.strip(), en.strip()
        chapters.append({"start_s": start, "title_es": es, "title_en": en or es})
    chapters.sort(key=lambda c: c["start_s"])
    return chapters


def chapters_for(key: str) -> list:
    path = _os.path.join(_CONTENT_DIR, f"{key}.txt")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return parse_chapters(fh.read())
    except FileNotFoundError:
        return []


# Day 7 is the active-rest day: meditation only, and it still counts for the streak.
_W1_INTENTIONS = [
    ("Hoy solo observa: no hay nada que corregir.",
     "Today, just observe: there is nothing to fix."),
    ("Respira más lento que ayer.",
     "Breathe slower than yesterday."),
    ("Haz cada movimiento un poco más pequeño y más consciente.",
     "Make each movement a little smaller and more mindful."),
    ("Fíjate qué lado de tu cuerpo se mueve con más facilidad.",
     "Notice which side of your body moves more easily."),
    ("Deja que la exhalación guíe cada movimiento.",
     "Let your exhale guide every movement."),
    ("Compara: ¿qué se siente más fácil que el Día 1?",
     "Compare: what feels easier than on Day 1?"),
    ("Hoy solo meditación. Tu cuerpo también aprende en reposo.",
     "Meditation only today. Your body also learns while resting."),
]

PROGRAMS = {
    "morning": {
        "slug": "morning",
        "path_slug": "morning",
        "name_en": "Morning Routine",
        "name_es": "Rutina de la Mañana",
        "ambient_key": "morning-ambient",
        "weeks": [
            {
                "slug": "w1",
                "number": 1,
                "name_en": "Week 1 · Gentle",
                "name_es": "Semana 1 · Suave",
                "level_en": "Beginners",
                "level_es": "Principiantes",
                # Felix: Week 1 free, later weeks premium.
                "premium": False,
                "meditation_key": "morning-w1-meditation",
                "movement_key": "morning-w1-movement",
                # Durations Mux reported on upload (2026-11-02): 5:47 and 7:25.
                # Both videos are vertical 9:16. These are for display only.
                "meditation_duration_s": 347,
                "movement_duration_s": 445,
                "affirmation_es": "Mi cuerpo despierta, y yo lo acompaño con calma.",
                "affirmation_en": "My body wakes up, and I walk alongside it with calm.",
                "days": [
                    {
                        "day": i + 1,
                        "kind": "meditation_only" if i == 6 else "full",
                        "intention_es": es,
                        "intention_en": en,
                    }
                    for i, (es, en) in enumerate(_W1_INTENTIONS)
                ],
            },
        ],
    },
}

PROGRAM_FOR_PATH = {p["path_slug"]: p["slug"] for p in PROGRAMS.values()}


def _public_hls(playback_id: Optional[str]) -> Optional[str]:
    return f"https://stream.mux.com/{playback_id}.m3u8" if playback_id else None


def week_view(week: dict, unlocked: bool) -> dict:
    """One week as the client sees it. Locked weeks carry no playback ids."""
    med_id = PROGRAM_PLAYBACK_IDS.get(week["meditation_key"])
    mov_id = PROGRAM_PLAYBACK_IDS.get(week["movement_key"])
    playable = unlocked and bool(med_id and mov_id)
    return {
        "slug": week["slug"],
        "number": week["number"],
        "name_en": week["name_en"],
        "name_es": week["name_es"],
        "level_en": week["level_en"],
        "level_es": week["level_es"],
        "premium": week["premium"],
        "unlocked": unlocked,
        # False until the videos are on Mux (or while locked): list it, don't play it.
        "available": playable,
        "meditation": {
            "hls_url": _public_hls(med_id) if playable else None,
            "duration_s": week["meditation_duration_s"],
        },
        "movement": {
            "hls_url": _public_hls(mov_id) if playable else None,
            "duration_s": week["movement_duration_s"],
            "chapters": chapters_for(week["movement_key"]),
        },
        "affirmation_es": week["affirmation_es"],
        "affirmation_en": week["affirmation_en"],
        "days": week["days"],
    }


def program_view(slug: str, premium_caller: bool) -> Optional[dict]:
    p = PROGRAMS.get(slug)
    if p is None:
        return None
    return {
        "slug": p["slug"],
        "path_slug": p["path_slug"],
        "name_en": p["name_en"],
        "name_es": p["name_es"],
        "daily_pacing": daily_pacing(),
        # Optional background track, mixed in the app under the videos (never
        # baked into them). None until Felix sends one: the app hides the toggle.
        "ambient_hls_url": _public_hls(PROGRAM_PLAYBACK_IDS.get(p["ambient_key"])),
        "weeks": [
            week_view(w, unlocked=(not w["premium"]) or premium_caller)
            for w in p["weeks"]
        ],
    }
