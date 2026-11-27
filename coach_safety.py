"""AI Coach safety for pain and injury questions (Sandy, 2026-11-23).

When someone asks about pain, an injury or symptoms that will not go away, the
Coach recommends a qualified healthcare professional and never diagnoses or
prescribes treatment. COACH_SAFETY_RULES goes into the system prompt; the
keyword check below makes sure the recommendation is in the reply even when the
model leaves it out.
"""

from __future__ import annotations

import re
import unicodedata

COACH_SAFETY_RULES = (
    "Safety rule: if the user mentions pain, an injury, numbness, tingling, swelling, "
    "or symptoms that persist or get worse, do not guess the cause, do not diagnose, "
    "and do not prescribe treatment, medication or rehabilitation exercises for it. "
    "Say kindly that they should consult a qualified healthcare professional, such as "
    "a physician or a physical therapist, before continuing, and that they should stop "
    "any movement that hurts. You may still give general, gentle mobility guidance "
    "that does not target the painful area."
)

SAFETY_NOTE = {
    "en": "Important: for pain, injuries or symptoms that don't go away, please consult a "
          "qualified healthcare professional, such as a physician or a physical therapist. "
          "Stop any movement that hurts.",
    "es": "Importante: si tienes dolor, una lesión o síntomas que no desaparecen, consulta a un "
          "profesional de la salud cualificado, como un médico o un fisioterapeuta. "
          "Detén cualquier movimiento que te duela.",
}

# Word stems, matched on accent-free lower-case text at the start of a word.
_PAIN_STEMS = [
    # English
    "pain", "painful", "hurt", "ache", "aching", "sore", "injur", "sprain", "strain",
    "tear", "torn", "numb", "tingl", "swell", "swollen", "sciatic", "hernia",
    "inflam", "tendinit", "bursit", "arthrit", "surgery", "fracture", "dislocat",
    "pinched", "pinch",
    # Spanish
    "dolor", "duele", "duelen", "dolia", "molest", "lesion", "lesiona", "esguince",
    "desgarr", "rotura", "hormigue", "entumec", "adormec", "hinchaz", "hinchad",
    "inflamac", "ciatic", "operac", "cirugia", "fractur", "luxac", "pinzamiento",
    "tendinitis", "contractura",
]
_PAIN_RE = re.compile(r"\b(" + "|".join(_PAIN_STEMS) + r")")


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def mentions_pain(text: str) -> bool:
    return bool(_PAIN_RE.search(_plain(text)))


def _already_recommends(reply: str) -> bool:
    t = _plain(reply)
    return any(
        k in t
        for k in (
            "healthcare professional", "health professional", "physical therapist",
            "physiotherapist", "physician", "doctor",
            "profesional de la salud", "profesional sanitario", "fisioterapeuta", "medico",
        )
    )


def ensure_safety_note(reply: str, language: str) -> str:
    if _already_recommends(reply):
        return reply
    note = SAFETY_NOTE["es" if (language or "").lower().startswith("es") else "en"]
    return f"{reply.rstrip()}\n\n{note}"
