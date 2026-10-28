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

PATHS = [
    {
        "slug": "full",
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
        "premium": True,
        "order": 2,
        "name_en": "Mobility",
        "name_es": "Movilidad",
        "description_en": "Move your joints with more control.",
        "description_es": "Mueve tus articulaciones con más control.",
        "icon": "🔄",
    },
    {
        "slug": "stretch",
        "premium": True,
        "order": 3,
        "name_en": "Stretch",
        "name_es": "Estiramiento",
        "description_en": "Explore your flexibility.",
        "description_es": "Explora tu flexibilidad.",
        "icon": "🤸",
    },
    {
        "slug": "morning",
        "premium": True,
        "order": 1,
        "name_en": "Morning Routine",
        "name_es": "Rutina de la Mañana",
        "description_en": "Start your day with movement and meditation.",
        "description_es": "Empieza tu día con movimiento y meditación.",
        "icon": "🌅",
    },
    {
        # Felix's request (2026-10-28): Strength as one of the five headline routines.
        # Built from the three existing strength exercises; nothing new is programmed.
        "slug": "strength",
        "premium": True,
        "order": 4,
        "name_en": "Strength",
        "name_es": "Fuerza",
        "description_en": "Build strength and control.",
        "description_es": "Desarrolla fuerza y control.",
        "icon": "💪",
    },
    {
        "slug": "night",
        "premium": True,
        "order": 5,
        "name_en": "Night Routine",
        "name_es": "Rutina de Noche",
        "description_en": "Wind down with gentle movement.",
        "description_es": "Relájate con movimiento suave.",
        "icon": "🌙",
    },
    {
        "slug": "posture",
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
