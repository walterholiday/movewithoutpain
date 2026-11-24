"""Guided routines, the free week and the weekly schedule (Sandy's email of
2026-11-23, "FELIXFLEX – App Improvements & Exercise Organization").

Everything here is built from exercises that already exist. A step points at an
exercise by its `order`, which is the number Sandy uses ("Exercise 17: Wall Leg
Extensions"), and the server resolves it to the stored row, so a routine never
duplicates a video and an exercise can appear in several routines.

    Exercises → Mobility → Guided Routines → Hip Mobility → Start

A guided session plays Félix's intro for the category (~1 min), then each step's
video for `duration_s` with a visible countdown, and moves on by itself.

Premium restrictions are unchanged: a routine that contains a premium exercise is
locked for a caller who cannot open that exercise (the same exercise_unlocked()
check /today and /video use). The seven free-week sessions use only the original
14 exercises, which are free, so the whole week stays free.

STATUS: Sandy's routine lists are as she sent them. Durations, the free-week day
plans, descriptions and the weekly schedule are Claude's DRAFTS: "Félix will
define and approve the final sequence, repetitions and timing." Edit here; no app
update is needed for any change in this file.

Clients see this from X-MWP-Api >= 5 (app 1.4.0) at GET /guided.
"""

from __future__ import annotations

from typing import Callable, Optional

from paths import INTRO_VIDEOS
from programs import daily_pacing

GUIDED_API_VERSION = 5

# Nominal length of Félix's intro, used only for the "10 min" label on cards.
INTRO_SECONDS = 60

# Default time on screen per exercise (seconds), by Sandy's exercise number.
# Drafted from each exercise's reps/time text; Félix to confirm.
STEP_SECONDS: dict[int, int] = {
    1: 60,    # Pelvic Tilts — 15 reps
    2: 90,    # Hip Circles — 10 per leg
    3: 90,    # Back Extension to the Side — 10 per leg
    4: 90,    # Knee to Shoulder — 15 per leg
    5: 120,   # Lying Leg Raise (Battement) — 10 per leg x 2
    6: 120,   # Glute Kick — 10 per leg x 2
    7: 120,   # Glute Bridge — 30 slow raises
    8: 120,   # Single Leg Raise — 10 per leg x 3
    9: 90,    # V-Raise — 15 x 2
    10: 90,   # High Hip Flexion — 20 x 2
    11: 120,  # Standing Hamstring Stretch — 1 min per leg
    12: 120,  # Deep Lunge — 1 min per leg
    13: 120,  # Low Lunge — 2 min per leg in the library; 1 min per leg in a session
    14: 120,  # Pancake — 1 min x 2
    15: 60,   # Wall Figure Four — 30 s per side
    16: 60,   # Hamstrings at the Wall — 30 s per side
    17: 60,   # Wall Leg Extensions — 30 s per side
    18: 45,   # Wall Butterfly — 30 s (+ time to get into it)
    19: 120,  # Psoas Lunge Pulses — 15 pulses + 30 s per side
    20: 240,  # 4-Minute Posterior Chain
}

# The three groups of the Exercises tab. `exercise_category` is the existing
# Exercise.category the "Exercises" sub-tab lists ('stretches' is Flexibility).
CATEGORIES: list[dict] = [
    {
        "slug": "mobility",
        "exercise_category": "mobility",
        "intro": "mobility",
        "icon": "🌀",
        "name_en": "Mobility",
        "name_es": "Movilidad",
        "tagline_en": "Explore the mobility of your hips and joints.",
        "tagline_es": "Explora la movilidad de tus caderas y articulaciones.",
        "card_en": "Move and free your joints.",
        "card_es": "Mueve y libera tus articulaciones.",
        "focus_en": "Fluidity, control and freedom of movement in your hips, spine and legs.",
        "focus_es": "Fluidez, control y libertad de movimiento en caderas, columna y piernas.",
    },
    {
        "slug": "flexibility",
        "exercise_category": "stretches",
        "intro": "stretch",
        "icon": "🪷",
        "name_en": "Flexibility",
        "name_es": "Flexibilidad",
        "tagline_en": "Increase your range of motion and release tension.",
        "tagline_es": "Aumenta tu rango de movimiento y suelta la tensión.",
        "card_en": "Gain range of motion and ease.",
        "card_es": "Gana rango de movimiento y soltura.",
        "focus_en": "Flexibility in your hips, hamstrings and posterior chain.",
        "focus_es": "Flexibilidad de caderas, isquiotibiales y cadena posterior.",
    },
    {
        "slug": "strength",
        "exercise_category": "strength",
        "intro": "strength",
        "icon": "💪",
        "name_en": "Strength",
        "name_es": "Fuerza",
        "tagline_en": "Develop control, stability and functional strength.",
        "tagline_es": "Desarrolla control, estabilidad y fuerza funcional.",
        "card_en": "Build control and stability.",
        "card_es": "Construye control y estabilidad.",
        "focus_en": "Glute activation, leg strength and body control.",
        "focus_es": "Activación de glúteos, fuerza de piernas y control corporal.",
    },
]

# Sandy's routines, exercise numbers exactly as in her email.
ROUTINES: list[dict] = [
    {
        "slug": "hip-mobility", "category": "mobility", "steps": [1, 2, 3, 4],
        "name_en": "Hip Mobility", "name_es": "Movilidad de Caderas",
        "description_en": "Wake up your hips with four controlled movements.",
        "description_es": "Despierta tus caderas con cuatro movimientos controlados.",
    },
    {
        "slug": "general-mobility", "category": "mobility", "steps": [5, 6, 17],
        "name_en": "General Mobility", "name_es": "Movilidad General",
        "description_en": "Free your hips and legs with kicks and wall extensions.",
        "description_es": "Libera caderas y piernas con patadas y extensiones en la pared.",
    },
    {
        "slug": "hip-flexibility", "category": "flexibility", "steps": [10, 12, 13, 19],
        "name_en": "Hip Flexibility", "name_es": "Flexibilidad de Caderas",
        "description_en": "Open the front of your hips: flexion, lunges and psoas pulses.",
        "description_es": "Abre la parte delantera de la cadera: flexión, estocadas y pulsos de psoas.",
    },
    {
        "slug": "hip-opening", "category": "flexibility", "steps": [14, 15, 18],
        "name_en": "Hip Opening", "name_es": "Apertura de Caderas",
        "description_en": "Pancake and supported wall stretches to open your hips.",
        "description_es": "Pancake y estiramientos apoyados en la pared para abrir la cadera.",
    },
    {
        "slug": "hamstrings", "category": "flexibility", "steps": [11, 16, 20],
        "name_en": "Hamstrings & Posterior Chain", "name_es": "Isquiotibiales y Cadena Posterior",
        "description_en": "Release the back of your legs, from standing to the wall.",
        "description_es": "Suelta la parte de atrás de las piernas, de pie y en la pared.",
    },
    {
        "slug": "glute-strength", "category": "strength", "steps": [7, 8, 9],
        "name_en": "Glute Strength & Control", "name_es": "Fuerza y Control de Glúteos",
        "description_en": "Activate your glutes and build control from the hips.",
        "description_es": "Activa tus glúteos y construye control desde la cadera.",
    },
]

# Week 1 · free trial: seven different sessions from the original (free) 14.
# Day N opens when Day N-1 is done (plus one calendar day when
# PROGRAM_DAILY_PACING is on, the same switch the Morning program uses).
FREE_WEEK: dict = {
    "slug": "week1",
    "name_en": "Week 1 · Free trial",
    "name_es": "Semana 1 · Prueba gratis",
    "subtitle_en": "A different session each day to build a consistent routine.",
    "subtitle_es": "Una sesión diferente cada día para crear una rutina constante.",
    "days": [
        {"day": 1, "category": "mobility", "steps": [1, 2, 3, 4],
         "title_en": "Mobility", "title_es": "Movilidad",
         "subtitle_en": "Activate your body gently.", "subtitle_es": "Activa tu cuerpo con suavidad."},
        {"day": 2, "category": "strength", "steps": [1, 7, 8, 9],
         "title_en": "Strength", "title_es": "Fuerza",
         "subtitle_en": "Build stability and control.", "subtitle_es": "Construye estabilidad y control."},
        {"day": 3, "category": "flexibility", "steps": [10, 11, 12],
         "title_en": "Stretching", "title_es": "Estiramiento",
         "subtitle_en": "Release tension and gain range.", "subtitle_es": "Suelta tensión y gana rango."},
        {"day": 4, "category": "mobility", "steps": [2, 4, 5, 6],
         "title_en": "Mobility", "title_es": "Movilidad",
         "subtitle_en": "Explore new movements.", "subtitle_es": "Explora nuevos movimientos."},
        {"day": 5, "category": "strength", "steps": [3, 6, 7, 9],
         "title_en": "Strength", "title_es": "Fuerza",
         "subtitle_en": "Activate the key muscles.", "subtitle_es": "Activa los músculos clave."},
        {"day": 6, "category": "flexibility", "steps": [11, 13, 14],
         "title_en": "Stretching", "title_es": "Estiramiento",
         "subtitle_en": "Relax and lengthen your body.", "subtitle_es": "Relaja y alarga tu cuerpo."},
        {"day": 7, "category": "integration", "steps": [1, 2, 7, 12, 14],
         "title_en": "Integration", "title_es": "Integración",
         "subtitle_en": "A complete, balanced session.", "subtitle_es": "Una sesión completa y equilibrada."},
    ],
}

# "Your session today" after Week 1: category per weekday, Monday first.
# "integration" (Sunday) replays the Day 7 session, which is all free.
WEEKLY_SCHEDULE = ["mobility", "strength", "flexibility", "mobility", "strength", "flexibility", "integration"]

# Intro clip for a session of this category (keys of intro_playback_ids.json).
_INTRO_KEY = {c["slug"]: c["intro"] for c in CATEGORIES}
_INTRO_KEY["integration"] = "app"


def intro_for(category: str) -> Optional[str]:
    return INTRO_VIDEOS.get(_INTRO_KEY.get(category, ""))


def _session(
    meta: dict,
    category: str,
    by_order: dict,
    serialise: Callable[[object], dict],
    is_unlocked: Callable[[object], bool],
) -> Optional[dict]:
    """A playable session: resolved steps, total length, lock state.

    Returns None when any exercise is missing from the database (for example a
    premium clip that is not uploaded yet), so no card ever starts a session
    with a hole in it."""
    rows = [by_order.get(n) for n in meta["steps"]]
    if any(r is None for r in rows):
        return None
    steps = [
        {"exercise": serialise(r), "duration_s": STEP_SECONDS.get(n, 60)}
        for n, r in zip(meta["steps"], rows)
    ]
    intro = intro_for(category)
    total = sum(s["duration_s"] for s in steps) + (INTRO_SECONDS if intro else 0)
    return {
        "category": category,
        "intro_playback_id": intro,
        "duration_s": total,
        "exercise_count": len(steps),
        "premium": any(getattr(r, "tier", "free") == "premium" for r in rows),
        "unlocked": all(is_unlocked(r) for r in rows),
        "steps": steps,
    }


def guided_view(
    exercises: list,
    serialise: Callable[[object], dict],
    is_unlocked: Callable[[object], bool],
) -> dict:
    """GET /guided. `exercises` are the rows this caller may see; `serialise`
    turns a row into the /today exercise payload (video ids stripped when
    locked); `is_unlocked` is exercise_unlocked() bound to the caller."""
    by_order = {}
    for ex in exercises:
        # The 20 numbered exercises have unique orders; keep the first if a
        # stray row ever shares one.
        by_order.setdefault(ex.order, ex)

    def text(meta: dict, *keys: str) -> dict:
        return {f"{k}_{lang}": meta[f"{k}_{lang}"] for k in keys for lang in ("en", "es")}

    categories = []
    for cat in CATEGORIES:
        routines = []
        for r in ROUTINES:
            if r["category"] != cat["slug"]:
                continue
            session = _session(r, cat["slug"], by_order, serialise, is_unlocked)
            if session is not None:
                routines.append({"slug": r["slug"], **text(r, "name", "description"), **session})
        categories.append({
            "slug": cat["slug"],
            "icon": cat["icon"],
            "exercise_category": cat["exercise_category"],
            "intro_playback_id": intro_for(cat["slug"]),
            **text(cat, "name", "tagline", "card", "focus"),
            "routines": routines,
        })

    days = []
    for d in FREE_WEEK["days"]:
        session = _session(d, d["category"], by_order, serialise, is_unlocked)
        if session is None:
            continue
        days.append({"day": d["day"], **text(d, "title", "subtitle"), **session})

    return {
        "daily_pacing": daily_pacing(),
        "categories": categories,
        "free_week": {
            "slug": FREE_WEEK["slug"],
            **text(FREE_WEEK, "name", "subtitle"),
            "days": days,
        },
        "weekly_schedule": WEEKLY_SCHEDULE,
    }
