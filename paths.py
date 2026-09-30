"""Routine path definitions for Move Without Pain.

A "path" is a themed routine built from the existing exercise library.
Exercises are tagged with the paths they belong to (comma-separated slugs
in Exercise.paths). The Full Routine is free; all other paths require the
premium subscription ($19.99/month) — gating is enforced client-side for v1,
the API just reports which paths are premium.
"""

PATHS = [
    {
        "slug": "full",
        "premium": False,
        "order": 1,
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
        "name_en": "Mobility Routine",
        "name_es": "Rutina de Movilidad",
        "description_en": "Wake up your hips with the six core mobility drills.",
        "description_es": "Despierta tus caderas con los seis ejercicios de movilidad.",
        "icon": "🔄",
    },
    {
        "slug": "stretch",
        "premium": True,
        "order": 3,
        "name_en": "Stretch Routine",
        "name_es": "Rutina de Estiramiento",
        "description_en": "Deep, slow stretches for hips and hamstrings.",
        "description_es": "Estiramientos profundos y lentos para caderas e isquiotibiales.",
        "icon": "🤸",
    },
    {
        "slug": "morning",
        "premium": True,
        "order": 4,
        "name_en": "Good Morning Routine",
        "name_es": "Rutina de Buenos Días",
        "description_en": "A gentle sequence to loosen up and start your day moving well.",
        "description_es": "Una secuencia suave para soltar el cuerpo y empezar bien el día.",
        "icon": "🌅",
    },
    {
        "slug": "night",
        "premium": True,
        "order": 5,
        "name_en": "Night Routine",
        "name_es": "Rutina de Noche",
        "description_en": "Calming, long-hold stretches to release tension before sleep.",
        "description_es": "Estiramientos calmados y sostenidos para liberar tensión antes de dormir.",
        "icon": "🌙",
    },
    {
        "slug": "posture",
        "premium": True,
        "order": 6,
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
        "order": 7,
        "name_en": "Wall Routine",
        "name_es": "Rutina en la Pared",
        "description_en": "Supported stretches with your legs on the wall. Follow the timer in each video.",
        "description_es": "Estiramientos apoyados con las piernas en la pared. Sigue el temporizador de cada vídeo.",
        "icon": "🧱",
    },
]

PATH_SLUGS = {p["slug"] for p in PATHS}

# Exercise (name_en) → list of path slugs. Every exercise is always in "full".
EXERCISE_PATHS = {
    "Pelvic Tilts":                ["full", "mobility", "morning", "posture"],
    "Hip Circles":                 ["full", "mobility", "morning"],
    "Back Extension to the Side":  ["full", "mobility", "morning"],
    "Knee to Shoulder":            ["full", "mobility", "night"],
    "Lying Leg Raise (Battement)": ["full", "mobility"],
    "Glute Kick":                  ["full", "mobility"],
    "Glute Bridge":                ["full", "morning", "posture"],
    "Single Leg Raise (Seated)":   ["full", "posture"],
    "V-Raise (Seated)":            ["full", "posture"],
    "High Hip Flexion (Chair)":    ["full", "stretch", "morning", "posture"],
    "Standing Hamstring Stretch":  ["full", "stretch", "morning", "night"],
    "Deep Lunge":                  ["full", "stretch", "night", "posture"],
    "Low Lunge":                   ["full", "stretch", "night"],
    "Pancake Stretch":             ["full", "stretch", "night"],
}
