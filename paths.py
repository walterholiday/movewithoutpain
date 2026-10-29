"""Routine path definitions for Move Without Pain.

A "path" is a themed routine built from the existing exercise library.
Exercises are tagged with the paths they belong to (comma-separated slugs
in Exercise.paths). The Full Routine is free; all other paths require the
premium subscription ($19.99/month) — gating is enforced client-side for v1,
the API just reports which paths are premium.
"""

import json as _json
import os as _os

# Public Mux playback ids for Felix's introduction clips, written by
# tools/intro_upload.py. "app" is the general introduction shown from the home
# screen; the rest are keyed by routine slug and play when that routine is opened.
# Missing keys simply mean "no intro yet": the app shows the routine directly.
try:
    with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "intro_playback_ids.json"), encoding="utf-8") as _fh:
        INTRO_VIDEOS: dict = _json.load(_fh)
except FileNotFoundError:
    INTRO_VIDEOS = {}

APP_INTRO_PLAYBACK_ID = INTRO_VIDEOS.get("app")

# Felix's 2026-10-28 routine changes (names, order, Strength, intro videos) are
# served only to clients that send X-MWP-Api >= 3 (app 1.2.0+). Older builds
# keep getting exactly the v1.1 routine list, so this can deploy before Felix has
# signed off on the copy and before 1.2.0 is in the store. Each changed entry
# carries its pre-change fields under "legacy"; path_view() applies them.
ROUTINES_API_VERSION = 3

PATHS = [
    {
        "slug": "full",
        "max_api": ROUTINES_API_VERSION - 1,  # Felix 2026-10-29: only his five on the 1.2.0 home screen
        "legacy": {
            "order": 1,
        },
        "premium": False,
        "order": 6,
        "name_en": "Full Routine",
        "name_es": "Rutina Completa",
        "description_en": "The complete daily routine: mobility, strength, and stretches.",
        "description_es": "La rutina diaria completa: movilidad, fuerza y estiramientos.",
        "icon": "🧘",
    },
    {
        "slug": "mobility",
        "legacy": {
            "order": 2,
            "name_en": "Mobility Routine",
            "name_es": "Rutina de Movilidad",
            "description_en": "Wake up your hips with the six core mobility drills.",
            "description_es": "Despierta tus caderas con los seis ejercicios de movilidad.",
        },
        "premium": True,
        "order": 2,
        "name_en": "Mobility",
        "name_es": "Movilidad",
        "description_en": "Move your joints with more control.",
        "description_es": "Mueve tus articulaciones con control y sin dolor.",
        "icon": "🔄",
    },
    {
        "slug": "stretch",
        "legacy": {
            "order": 3,
            "name_en": "Stretch Routine",
            "name_es": "Rutina de Estiramiento",
            "description_en": "Deep, slow stretches for hips and hamstrings.",
            "description_es": "Estiramientos profundos y lentos para caderas e isquiotibiales.",
        },
        "premium": True,
        "order": 3,
        "name_en": "Stretch",
        "name_es": "Estiramiento",
        "description_en": "Explore your flexibility.",
        "description_es": "Gana flexibilidad sin forzar.",
        "icon": "🤸",
    },
    {
        "slug": "morning",
        "legacy": {
            "order": 4,
            "name_en": "Good Morning Routine",
            "name_es": "Rutina de Buenos Días",
            "description_en": "A gentle sequence to loosen up and start your day moving well.",
            "description_es": "Una secuencia suave para soltar el cuerpo y empezar bien el día.",
        },
        "premium": True,
        "order": 1,
        "name_en": "Morning Routine",
        "name_es": "Rutina de la Mañana",
        "description_en": "Start your day with movement and meditation.",
        "description_es": "Despierta tu cuerpo con suavidad.",
        "icon": "🌅",
    },
    {
        # Felix's request (2026-10-28): Strength as one of the five headline routines.
        # Built from the three existing strength exercises; nothing new is programmed.
        "slug": "strength",
        "premium": True,
        "min_api": ROUTINES_API_VERSION,
        "order": 4,
        "name_en": "Strength",
        "name_es": "Fuerza",
        "description_en": "Build strength and control.",
        "description_es": "Construye fuerza desde el control.",
        "icon": "💪",
    },
    {
        "slug": "night",
        "legacy": {
            "order": 5,
            "description_en": "Calming, long-hold stretches to release tension before sleep.",
            "description_es": "Estiramientos calmados y sostenidos para liberar tensión antes de dormir.",
        },
        "premium": True,
        "order": 5,
        "name_en": "Night Routine",
        "name_es": "Rutina de Noche",
        "description_en": "Wind down with gentle movement.",
        "description_es": "Suelta la tensión antes de dormir.",
        "icon": "🌙",
    },
    {
        "slug": "posture",
        "max_api": ROUTINES_API_VERSION - 1,  # Felix 2026-10-29: only his five on the 1.2.0 home screen
        "legacy": {
            "order": 6,
        },
        "premium": True,
        "order": 7,
        "name_en": "Good Posture",
        "name_es": "Buena Postura",
        "description_en": "Pelvic alignment and hip-flexor work to help you sit and stand taller.",
        "description_es": "Alineación pélvica y trabajo de flexores de cadera para una mejor postura.",
        "icon": "🧍",
    },
    {
        # Sandy's wall series (filmed 2026-09-17). Premium, and hidden from v1.0
        # builds (min_api) — they could not open it, it would just be an empty card.
        "slug": "wall",
        "max_api": ROUTINES_API_VERSION - 1,  # Felix 2026-10-29: only his five on the 1.2.0 home screen
        "legacy": {
            "order": 7,
        },
        "premium": True,
        "min_api": 2,
        "order": 8,
        "name_en": "Wall Routine",
        "name_es": "Rutina en la Pared",
        "description_en": "Supported stretches with your legs on the wall. Follow the timer in each video.",
        "description_es": "Estiramientos apoyados con las piernas en la pared. Sigue el temporizador de cada vídeo.",
        "icon": "🧱",
    },
]

for _p in PATHS:
    _p["intro_playback_id"] = INTRO_VIDEOS.get(_p["slug"])

PATH_SLUGS = {p["slug"] for p in PATHS}


def path_view(p: dict, api_version: int) -> dict:
    """The path as this client should see it: Felix's 2026-10-28 version for
    X-MWP-Api >= 3, the v1.1 fields (and no intro id) for everything older."""
    view = {k: v for k, v in p.items() if k not in ("legacy", "intro_playback_id", "min_api", "max_api")}
    if api_version >= ROUTINES_API_VERSION:
        view["intro_playback_id"] = p.get("intro_playback_id")
    else:
        view.update(p.get("legacy", {}))
    return view


def path_listed(p: dict, api_version: int) -> bool:
    """Whether this client may list the path at all. "min_api" hides a path from
    older builds (Strength before 1.2.0); "max_api" hides it from newer ones
    (Full Routine, Good Posture and Wall Routine from 1.2.0+, so Felix's five are
    the whole home screen). A hidden path still exists: /today?path=<slug> keeps
    working, and Full Routine stays the free one for pre-1.2.0 builds."""
    return p.get("min_api", 1) <= api_version <= p.get("max_api", 10**9)


def visible_paths(api_version: int) -> list:
    """Paths this client may list, in the order it should show them."""
    views = [path_view(p, api_version) for p in PATHS if path_listed(p, api_version)]
    return sorted(views, key=lambda v: v["order"])


def paths_field_for(paths: str, api_version: int) -> str:
    """An exercise's comma-separated routine tags, minus routines this client
    cannot list (Strength for pre-1.2.0 builds; Full, Good Posture and Wall for
    1.2.0+), so each build's /today matches its own routine list."""
    hidden = {p["slug"] for p in PATHS if not path_listed(p, api_version)}
    return ",".join(slug for slug in (paths or "").split(",") if slug and slug not in hidden)

# Exercise (name_en) → list of path slugs. Every exercise is always in "full".
EXERCISE_PATHS = {
    "Pelvic Tilts":                ["full", "mobility", "morning", "posture"],
    "Hip Circles":                 ["full", "mobility", "morning"],
    "Back Extension to the Side":  ["full", "mobility", "morning"],
    "Knee to Shoulder":            ["full", "mobility", "night"],
    "Lying Leg Raise (Battement)": ["full", "mobility"],
    "Glute Kick":                  ["full", "mobility"],
    "Glute Bridge":                ["full", "strength", "morning", "posture"],
    "Single Leg Raise (Seated)":   ["full", "strength", "posture"],
    "V-Raise (Seated)":            ["full", "strength", "posture"],
    "High Hip Flexion (Chair)":    ["full", "stretch", "morning", "posture"],
    "Standing Hamstring Stretch":  ["full", "stretch", "morning", "night"],
    "Deep Lunge":                  ["full", "stretch", "night", "posture"],
    "Low Lunge":                   ["full", "stretch", "night"],
    "Pancake Stretch":             ["full", "stretch", "night"],
}
