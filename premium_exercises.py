"""Sandy's new filmed exercises (shot 2026-09-17/18), served from Mux.

PREMIUM_EXERCISES are upserted on every boot (main.auto_seed), matched by Mux
playback id first and by `name_en` second, and are always stored tier="premium",
in_v1_library=False: never free, never part of what grandfathered v1.0 devices
keep. An entry with an empty mux_playback_id is skipped, so deploying this file
before the upload shows nothing half-finished.

RENAMING AN EXERCISE: change `name_en` (and the other text) here, and the paywall
copy in the app if the name appears there. Do NOT change `video`: it is the key
the clip was uploaded under, the key in mux_playback_ids.json and in the MANIFEST
of tools/mux_upload.py. Because rows are matched by playback id, the existing row
is updated in place: no re-upload, no second row. (Renaming and re-uploading the
same exercise in one deploy is the one case that would leave the old row behind.)

V1_VIDEO_UPGRADES gives two of the original free exercises Sandy's new footage.
They stay free and keep their YouTube id for v1.0 builds.

Playback ids come from mux_playback_ids.json, written by tools/mux_upload.py.
They must be SIGNED playback ids, never public ones (the script refuses public).

TEXT STATUS: DRAFT written from the footage by Claude on 2026-09-30, not yet
approved by Sandy. Names, instructions, reps and the "why" notes all need her
sign-off before release. Uploaded 2026-10-02 under the draft names so the flow
could be tested on TestFlight; her edits are applied as described above.
"""

import json
import os

PREMIUM_EXERCISES: list[dict] = [
    # ------------------------------------------------------------ Wall Routine
    {   # source: pared1.mp4
        "category": "stretches", "order": 15, "paths": "full,wall",
        "video": "Wall Figure Four",
        "name_en": "Wall Figure Four", "name_es": "Figura 4 en la Pared",
        "description_en": "Lie on your back with your hips close to the wall and your feet on it. "
            "Cross one ankle over the opposite knee and let that knee open gently. "
            "Stay relaxed and breathe out slowly.",
        "description_es": "Acostado boca arriba, con la cadera cerca de la pared y los pies apoyados en ella. "
            "Cruza un tobillo sobre la rodilla contraria y deja que esa rodilla se abra suavemente. "
            "Mantente relajado y exhala despacio.",
        "reps_or_time_en": "30 s per side", "reps_or_time_es": "30 s por lado",
        "tips_en": "Slide closer to the wall to go deeper.", "tips_es": "Acércate a la pared para ir más profundo.",
        "neuro_tag": "#SafetySignal",
        "neuro_why_en": "With the wall holding your legs there is nothing to balance, so your nervous "
            "system can stop guarding and let the deep hip rotators lengthen.",
        "neuro_why_es": "Con la pared sosteniendo tus piernas no hay nada que equilibrar, así que tu sistema "
            "nervioso deja de protegerse y permite que los rotadores profundos de la cadera se alarguen.",
    },
    {   # source: Pared2Left.mp4 + Pared3Right.mp4, joined
        "category": "stretches", "order": 16, "paths": "full,wall",
        "video": "Legs Up the Wall Hamstring Stretch",
        "name_en": "Legs Up the Wall Hamstring Stretch", "name_es": "Isquiotibiales en la Pared",
        "description_en": "Lie with your glutes close to the wall and both legs straight up it. "
            "Keep the backs of your knees long and flex your feet toward you. "
            "Follow the timer, first one side and then the other.",
        "description_es": "Acostado con los glúteos cerca de la pared y las dos piernas estiradas hacia arriba. "
            "Mantén la parte de atrás de las rodillas larga y flexiona los pies hacia ti. "
            "Sigue el temporizador, primero un lado y luego el otro.",
        "reps_or_time_en": "30 s per side", "reps_or_time_es": "30 s por lado",
        "tips_en": "", "tips_es": "",
        "neuro_tag": "#VagalTone",
        "neuro_why_en": "Legs supported above your hips plus slow exhalations nudge your body toward its "
            "rest mode, which makes it easier for the hamstrings to let go.",
        "neuro_why_es": "Las piernas apoyadas por encima de la cadera y las exhalaciones lentas llevan a tu "
            "cuerpo hacia su modo de descanso, y así los isquiotibiales se sueltan con más facilidad.",
    },
    {   # source: pared4.mp4
        "category": "mobility", "order": 17, "paths": "full,wall",
        "video": "Wall Leg Extensions",
        "name_en": "Wall Leg Extensions", "name_es": "Extensiones de Pierna en la Pared",
        "description_en": "Keep one foot on the wall. Bend the other knee toward your chest, then "
            "straighten that leg up toward the ceiling. Move slowly and with control.",
        "description_es": "Mantén un pie apoyado en la pared. Lleva la otra rodilla hacia el pecho y luego "
            "estira esa pierna hacia el techo. Muévete despacio y con control.",
        "reps_or_time_en": "30 s per side", "reps_or_time_es": "30 s por lado",
        "tips_en": "", "tips_es": "",
        "neuro_tag": "#MotorControl",
        "neuro_why_en": "Straightening the leg under your own control teaches your brain to use the new "
            "hamstring range, so flexibility turns into movement you can actually use.",
        "neuro_why_es": "Estirar la pierna con tu propio control enseña a tu cerebro a usar el nuevo rango "
            "del isquiotibial, para que la flexibilidad se convierta en movimiento útil.",
    },
    {   # source: Pared5.mp4
        "category": "stretches", "order": 18, "paths": "full,wall",
        "video": "Wall Butterfly",
        "name_en": "Wall Butterfly", "name_es": "Mariposa en la Pared",
        "description_en": "From legs up the wall, bring the soles of your feet together and let them slide "
            "down the wall as your knees open to the sides. Let gravity do the work.",
        "description_es": "Desde las piernas en la pared, junta las plantas de los pies y deja que bajen por "
            "la pared mientras las rodillas se abren hacia los lados. Deja que la gravedad trabaje.",
        "reps_or_time_en": "30 s", "reps_or_time_es": "30 s",
        "tips_en": "", "tips_es": "",
        "neuro_tag": "#StretchTolerance",
        "neuro_why_en": "A gentle hold that you don't have to fight lets the stretch receptors in your inner "
            "thighs settle, so the muscles accept more length over time.",
        "neuro_why_es": "Una postura suave que no tienes que forzar deja que los receptores de estiramiento "
            "de la cara interna del muslo se calmen, y con el tiempo el músculo acepta más longitud.",
    },
    # ------------------------------------------------------------ Other new premium
    {   # source: Psoas.mp4
        "category": "stretches", "order": 19, "paths": "full,stretch,posture",
        "video": "Psoas Lunge Pulses",
        "name_en": "Psoas Lunge Pulses", "name_es": "Pulsos de Psoas en Estocada",
        "description_en": "From a low lunge with your back knee on the mat and hands on your hips, gently "
            "push your hips forward and back 15 times. Then hold for 30 seconds, reaching the arm on "
            "the back-leg side up overhead.",
        "description_es": "Desde una estocada baja con la rodilla de atrás en la esterilla y las manos en la "
            "cadera, lleva la cadera suavemente hacia delante y atrás 15 veces. Luego sostén 30 segundos "
            "estirando hacia arriba el brazo del lado de la pierna de atrás.",
        "reps_or_time_en": "15 pulses + 30 s hold per side",
        "reps_or_time_es": "15 pulsos + 30 s sostenido por lado",
        "tips_en": "Keep your chest tall; don't arch your lower back.",
        "tips_es": "Mantén el pecho alto; no arquees la zona lumbar.",
        "neuro_tag": "#DynamicStretch",
        "neuro_why_en": "Rhythmic pulses warm up the hip flexors and gradually raise how far your nervous "
            "system lets them lengthen, which makes the final hold deeper.",
        "neuro_why_es": "Los pulsos rítmicos calientan los flexores de cadera y aumentan poco a poco cuánto "
            "les permite alargarse tu sistema nervioso, así el sostenido final es más profundo.",
    },
    {   # source: 4min CadenaPosterior.mp4
        "category": "stretches", "order": 20, "paths": "full,stretch,night",
        "video": "4-Minute Posterior Chain",
        "name_en": "4-Minute Posterior Chain", "name_es": "Cadena Posterior en 4 Minutos",
        "description_en": "A follow-along flow for your calves, hamstrings and back: seated forward folds "
            "with your feet flexed, reaching for your toes, and single-leg holds. Move with the video "
            "and never force the fold.",
        "description_es": "Una secuencia para seguir con el vídeo que trabaja gemelos, isquiotibiales y "
            "espalda: flexiones hacia delante sentado con los pies flexionados, alcanzando los dedos, y "
            "posturas a una pierna. Sigue el vídeo y nunca fuerces la flexión.",
        "reps_or_time_en": "4 min", "reps_or_time_es": "4 min",
        "tips_en": "Bend your knees a little if your lower back rounds.",
        "tips_es": "Flexiona un poco las rodillas si se te redondea la zona lumbar.",
        "neuro_tag": "#PosteriorChain",
        "neuro_why_en": "Calves, hamstrings and back are linked by continuous connective tissue. Working "
            "them together spreads the stretch along the whole line instead of one sore spot.",
        "neuro_why_es": "Gemelos, isquiotibiales y espalda están unidos por tejido conectivo continuo. "
            "Trabajarlos juntos reparte el estiramiento por toda la línea en vez de en un solo punto.",
    },
]

# ORIGINAL (free) exercises that get Sandy's new footage. Sources:
#   Lying Leg Raise (Battement) <- battemanAcostadox10 + BattemanAcostaoIzq, joined
#   Glute Kick                  <- bettemanAtrasAcostado + BattemanAtrasIzqAcostado, joined
_V1_UPGRADE_NAMES = ("Lying Leg Raise (Battement)", "Glute Kick")

# Playback ids live in mux_playback_ids.json ({name_en: playback_id}), written by
# tools/mux_upload.py, so uploading never means hand-editing this file.
_IDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mux_playback_ids.json")
try:
    with open(_IDS_FILE, encoding="utf-8") as fh:
        MUX_IDS: dict[str, str] = json.load(fh)
except FileNotFoundError:
    MUX_IDS = {}

for _entry in PREMIUM_EXERCISES:
    # `video` is a lookup key, not a column: pop it so main.auto_seed never copies it.
    _entry["mux_playback_id"] = MUX_IDS.get(_entry.pop("video"), "")

V1_VIDEO_UPGRADES: dict[str, str] = {name: MUX_IDS.get(name, "") for name in _V1_UPGRADE_NAMES}
