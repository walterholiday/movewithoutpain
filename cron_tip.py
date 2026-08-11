import os
import asyncio
from datetime import date
from models import SessionLocal, DailyTip
from ai_client import deepseek, DEFAULT_MODEL

async def generate_tip():
    response = await deepseek.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are a mobility coach who understands the nervous system. Write a short, "
                "poetic, 1-sentence daily tip grounded in these 5 principles: breathe, feel, "
                "align, don't force, be consistent. Where it fits naturally, draw on how the "
                "nervous system governs flexibility — that slow movement and long holds signal "
                "safety and let muscles release, that a fast pull triggers a protective reflex, "
                "that attention sharpens body awareness. Keep it plain and human, never clinical. "
                "Never claim to treat, cure, or diagnose anything, and never name specific "
                "neurotransmitters or make medical claims. Inspire the user to move without pain."
            )},
            {"role": "user", "content": "Give me today's tip in both English and Spanish, formatted as: EN: ... ES: ..."}
        ],
        temperature=0.9,
    )
    raw = response.choices[0].message.content
    parts = raw.split("ES:")
    en_part = parts[0].replace("EN:", "").strip()
    es_part = parts[1].strip() if len(parts) > 1 else en_part

    db = SessionLocal()
    try:
        existing = db.query(DailyTip).filter(DailyTip.tip_date == date.today()).first()
        if existing:
            existing.content_en = en_part
            existing.content_es = es_part
        else:
            tip = DailyTip(tip_date=date.today(), content_en=en_part, content_es=es_part, generated_by_ai=True)
            db.add(tip)
        db.commit()
        print(f"✅ Tip generated for {date.today()}")
    except Exception as e:
        db.rollback()
        print(f"❌ Cron failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(generate_tip())
