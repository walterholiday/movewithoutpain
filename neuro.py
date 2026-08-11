"""Neuroscience layer for Move Without Pain.

Adds a short, defensible "why this works" explanation to every exercise,
plus a hashtag-style neuro tag, in both English and Spanish.

Design note (2026-08-10): Sandy's architecture doc proposed neurotransmitter
tags such as "#GABA". Neurotransmitter-level claims about a hip stretch are
not well supported, and health claims in App Store metadata invite reviewer
scrutiny. The tags below stay on defensible ground — proprioception,
reciprocal inhibition, autogenic inhibition, vagal tone via slow exhalation —
and every blurb is educational rather than medical. Nothing here claims to
treat, cure, or diagnose anything.

Keyed on Exercise.name_en, matching the pattern already proven in paths.py.
"""

# name_en → (tag, why_en, why_es)
NEURO = {
    "Pelvic Tilts": (
        "#Proprioception",
        "Small, slow pelvic movements sharpen your brain's sense of where your "
        "lower back actually is — the position awareness that guards your posture all day.",
        "Los movimientos pélvicos lentos y pequeños afinan la percepción de tu cerebro "
        "sobre dónde está tu zona lumbar: la conciencia de posición que protege tu postura todo el día.",
    ),
    "Hip Circles": (
        "#MotorControl",
        "Moving a joint through its full circle refreshes the movement map your brain "
        "keeps for the hip, so that range stays available when you need it.",
        "Mover la articulación en un círculo completo actualiza el mapa de movimiento que tu "
        "cerebro guarda de la cadera, para que ese rango siga disponible cuando lo necesites.",
    ),
    "Back Extension to the Side": (
        "#FascialGlide",
        "Side-bending loads the connective tissue along your flank, helping the layers "
        "glide over one another instead of sticking.",
        "La flexión lateral carga el tejido conectivo del costado y ayuda a que las capas "
        "se deslicen entre sí en lugar de pegarse.",
    ),
    "Knee to Shoulder": (
        "#VagalTone",
        "Lying down and breathing out slowly as you draw the knee in leans on the body's "
        "rest-and-digest side — the reason this one tends to feel calming.",
        "Acostarte y exhalar lentamente mientras acercas la rodilla apoya el sistema de "
        "descanso del cuerpo: por eso este ejercicio suele sentirse calmante.",
    ),
    "Lying Leg Raise (Battement)": (
        "#ReciprocalInhibition",
        "When the front of the hip contracts to lift the leg, the hamstring behind it is "
        "signalled to release. You stretch one side by contracting the other.",
        "Cuando la parte frontal de la cadera se contrae para levantar la pierna, se le indica "
        "al isquiotibial que se relaje. Estiras un lado contrayendo el opuesto.",
    ),
    "Glute Kick": (
        "#MotorRecruitment",
        "Glutes often go quiet after long hours of sitting. Deliberate kicks remind the "
        "nervous system to call on them again.",
        "Los glúteos suelen apagarse tras muchas horas sentado. Las patadas deliberadas "
        "recuerdan al sistema nervioso que vuelva a usarlos.",
    ),
    "Glute Bridge": (
        "#PosteriorChain",
        "Lifting the hips trains the back of the body to fire in sequence — the coordination "
        "that lets your hips, rather than your lower back, do the work.",
        "Levantar las caderas entrena la parte posterior del cuerpo a activarse en secuencia: "
        "la coordinación que permite que trabajen las caderas y no la zona lumbar.",
    ),
    "Single Leg Raise (Seated)": (
        "#Proprioception",
        "Holding one leg up while seated forces constant small corrections, which is how "
        "balance and joint position sense actually improve.",
        "Sostener una pierna en alto sentado obliga a correcciones pequeñas constantes: así es "
        "como realmente mejoran el equilibrio y el sentido de posición articular.",
    ),
    "V-Raise (Seated)": (
        "#MotorControl",
        "Opening both legs under control teaches your hips to own the wide range, rather than "
        "just passively falling into it.",
        "Abrir ambas piernas con control enseña a tus caderas a dominar el rango amplio, en vez "
        "de solo caer pasivamente en él.",
    ),
    "High Hip Flexion (Chair)": (
        "#PsoasRelease",
        "The psoas links your spine to your leg and shortens with sitting. Loading it in flexion "
        "is the first step toward letting it lengthen.",
        "El psoas une tu columna con la pierna y se acorta al estar sentado. Cargarlo en flexión "
        "es el primer paso para que se alargue.",
    ),
    "Standing Hamstring Stretch": (
        "#StretchReflex",
        "Move in slowly. A fast pull triggers a protective reflex that tightens the muscle — the "
        "opposite of what you want.",
        "Entra lentamente. Un tirón rápido dispara un reflejo protector que tensa el músculo: lo "
        "contrario de lo que buscas.",
    ),
    "Deep Lunge": (
        "#PsoasRelease",
        "A long hold gives the hip flexor time to stop guarding. Length comes from the nervous "
        "system letting go, not from force.",
        "Un mantenimiento largo da tiempo al flexor de cadera a dejar de protegerse. La longitud "
        "viene de que el sistema nervioso suelte, no de la fuerza.",
    ),
    "Low Lunge": (
        "#Interoception",
        "Sink in and pay attention to what you actually feel. Reading your own sensation precisely "
        "is a trainable skill, and it's what keeps you from overdoing it.",
        "Baja y presta atención a lo que realmente sientes. Leer tu propia sensación con precisión "
        "es una habilidad entrenable, y es lo que evita que te excedas.",
    ),
    "Pancake Stretch": (
        "#AutogenicInhibition",
        "Hold past roughly 30 seconds and tension sensors in the tendon signal the muscle to "
        "release. That's why range is won in the long holds.",
        "Mantén más de unos 30 segundos y los sensores de tensión del tendón indican al músculo "
        "que se relaje. Por eso el rango se gana en los mantenimientos largos.",
    ),
}

NEURO_FALLBACK = (
    None,
    "Move slowly and breathe out as you go — steady, unhurried movement is what teaches the "
    "nervous system that a new range is safe.",
    "Muévete despacio y exhala mientras lo haces: el movimiento constante y sin prisa es lo que "
    "enseña al sistema nervioso que un nuevo rango es seguro.",
)


def neuro_for(name_en: str):
    """Return (tag, why_en, why_es) for an exercise, falling back to a generic blurb."""
    return NEURO.get(name_en, NEURO_FALLBACK)
