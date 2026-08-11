from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta
import os

from models import SessionLocal, Exercise, DailyTip, engine
from ai_client import deepseek, DEFAULT_MODEL
from paths import PATHS, PATH_SLUGS, EXERCISE_PATHS
from neuro import neuro_for

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def auto_seed():
    """Seed the exercises table on boot if it's empty, so no Railway Console step is needed.
    Also auto-migrates columns added after the original schema (`paths`, 2026-08-06;
    the neuro layer, 2026-08-10) and backfills them on existing rows."""
    from sqlalchemy import inspect, text
    # 1. Add any columns the live table predates (dialect-agnostic check).
    MIGRATIONS = [
        ("paths", "VARCHAR(120)"),
        ("neuro_tag", "VARCHAR(40)"),
        ("neuro_why_en", "TEXT"),
        ("neuro_why_es", "TEXT"),
    ]
    try:
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("exercises")}
        for col_name, col_type in MIGRATIONS:
            if col_name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE exercises ADD COLUMN {col_name} {col_type}"))
                print(f"✅ Migrated: added exercises.{col_name} column.")
    except Exception as e:
        print(f"⚠️ Column migration skipped: {e}")
    # 2. Seed if empty, then always backfill any rows missing paths or neuro fields.
    db = SessionLocal()
    try:
        if db.query(Exercise).count() == 0:
            from seed import seed
            seed()
            print("✅ Auto-seeded empty exercises table on startup.")

        paths_filled = 0
        for ex in db.query(Exercise).filter(Exercise.paths.is_(None)).all():
            ex.paths = ",".join(EXERCISE_PATHS.get(ex.name_en, ["full"]))
            paths_filled += 1

        neuro_filled = 0
        for ex in db.query(Exercise).filter(Exercise.neuro_why_en.is_(None)).all():
            tag, why_en, why_es = neuro_for(ex.name_en)
            ex.neuro_tag, ex.neuro_why_en, ex.neuro_why_es = tag, why_en, why_es
            neuro_filled += 1

        if paths_filled or neuro_filled:
            db.commit()
            print(f"✅ Backfilled paths on {paths_filled} and neuro fields on {neuro_filled} exercises.")
    except Exception as e:
        print(f"⚠️ Auto-seed skipped: {e}")
    finally:
        db.close()

@app.get("/")
async def root():
    return {
        "message": "Move Without Pain API is running 🧘",
        "endpoints": ["/today", "/paths", "/history", "/stats", "/ai/coach"],
        "docs": "/docs"
    }

class ExerciseResponse(BaseModel):
    id: int
    category: str
    order: int
    name_en: str
    name_es: str
    description_en: str
    description_es: str
    reps_or_time_en: str
    reps_or_time_es: str
    tips_en: Optional[str]
    tips_es: Optional[str]
    youtube_video_id: Optional[str]
    paths: Optional[str]  # comma-separated path slugs, e.g. "full,mobility,morning"
    neuro_tag: Optional[str] = None
    neuro_why_en: Optional[str] = None
    neuro_why_es: Optional[str] = None

class TodayResponse(BaseModel):
    date: str
    exercises: List[ExerciseResponse]
    tip: Optional[str]

class CoachRequest(BaseModel):
    user_message: str
    language: str = "en"
    context: Optional[str] = None

@app.get("/paths")
async def get_paths(db: Session = Depends(get_db)):
    """List the 6 routine paths with bilingual metadata, premium flag, and exercise counts."""
    exercises = db.query(Exercise).all()
    counts = {slug: 0 for slug in PATH_SLUGS}
    for ex in exercises:
        for slug in (ex.paths or "full").split(","):
            if slug in counts:
                counts[slug] += 1
    return {
        "paths": [{**p, "exercise_count": counts.get(p["slug"], 0)} for p in sorted(PATHS, key=lambda p: p["order"])],
        "subscription": {
            # v1.0 ships free: every path is unlocked and the client shows no lock badges
            # or paywall. Flipping this to True in v1.1 (once real IAP is wired up and the
            # Paid Applications Agreement is active) re-enables gating server-side.
            "enabled": False,
            "product_id": "com.brigbrednich.movewithoutpain.premium.monthly",
            "price_usd": 19.99,
            "period": "monthly",
            "unlocks": sorted(p["slug"] for p in PATHS if p["premium"]),
        },
    }

@app.get("/today", response_model=TodayResponse)
async def get_today(path: Optional[str] = None, db: Session = Depends(get_db)):
    """Daily routine. Optional ?path=slug filters to one routine path (default: full)."""
    if path is not None and path not in PATH_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown path '{path}'. Valid: {sorted(PATH_SLUGS)}")
    exercises = db.query(Exercise).order_by(Exercise.category, Exercise.order).all()
    if path and path != "full":
        exercises = [ex for ex in exercises if path in (ex.paths or "").split(",")]
    tip_record = db.query(DailyTip).filter(DailyTip.tip_date == date.today()).first()
    tip = tip_record.content_en if tip_record else None
    return {
        "date": date.today().isoformat(),
        "exercises": exercises,
        "tip": tip,
    }

@app.get("/history")
async def get_history(db: Session = Depends(get_db)):
    tips = db.query(DailyTip).order_by(DailyTip.tip_date.desc()).limit(30).all()
    return [{"date": t.tip_date.isoformat(), "content_en": t.content_en, "content_es": t.content_es} for t in tips]

@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_exercises = db.query(Exercise).count()
    return {"total_exercises": total_exercises, "version": "1.0"}

@app.post("/ai/coach")
async def ai_coach(request: CoachRequest, db: Session = Depends(get_db)):
    system_prompt = (
        "You are Félix, a compassionate mobility coach. Your philosophy is: "
        "1. Breath is key. 2. Maintain muscle awareness. 3. Control posture and alignment. "
        "4. Don't force, respect your body. 5. Consistency makes the difference. "
        "You give concise, safe, and encouraging advice. Never give medical diagnoses. "
        f"Respond in {request.language}. Keep it under 200 words."
    )
    user_prompt = request.user_message
    if request.context:
        user_prompt = f"The user is asking about '{request.context}'. Question: {request.user_message}"

    if deepseek is None:
        raise HTTPException(status_code=503, detail="AI coach is not configured (DEEPSEEK_API_KEY is missing).")

    try:
        response = await deepseek.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

from fastapi.responses import HTMLResponse

PRIVACY_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Privacy Policy - Move Without Pain</title>
<style>body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#2B2B2B;line-height:1.6}h1{color:#2A7D6D}h2{color:#1F5F53;margin-top:28px}</style></head>
<body>
<h1>Privacy Policy - Move Without Pain</h1>
<p><i>Effective August 1, 2026</i></p>
<p>Move Without Pain ("the app") is a bilingual mobility training app. We keep things simple: <b>the app has no user accounts and collects no personal information.</b></p>
<h2>What stays on your device</h2>
<p>Your practice history, streaks, language preference, and reminder settings are stored only on your device. They are never uploaded to our servers.</p>
<h2>What is sent to our servers</h2>
<p>The app fetches the daily exercise list and daily tip from our server. When you ask the AI coach a question, the text of your question is sent to our server and forwarded to an AI provider (DeepSeek) to generate a response. Questions are not linked to your identity, are not used for advertising, and are never sold.</p>
<h2>Third-party content</h2>
<p>Exercise demo videos are provided through YouTube, which may collect data according to Google's privacy policy when videos play.</p>
<h2>Not medical advice</h2>
<p>The app offers general mobility guidance and is not a substitute for professional medical advice. Consult a healthcare professional for injuries or medical conditions.</p>
<h2>Contact</h2>
<p>Questions? Email <a href='mailto:brigbrednich@gmail.com'>brigbrednich@gmail.com</a>.</p>
<p><i>Politica de privacidad: la app no tiene cuentas de usuario y no recopila informacion personal. Tu historial de practica se guarda solo en tu dispositivo. Las preguntas al coach de IA se envian a nuestro servidor y a DeepSeek para generar la respuesta, sin vincularse a tu identidad ni venderse. Contacto: brigbrednich@gmail.com.</i></p>
</body></html>"""

@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return PRIVACY_HTML

SUPPORT_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Support - Move Without Pain</title>
<style>body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#2B2B2B;line-height:1.6}h1{color:#2A7D6D}h2{color:#1F5F53;margin-top:28px;font-size:18px}a{color:#2A7D6D}.q{font-weight:600;margin-top:18px}hr{border:0;border-top:1px solid #E3E9E7;margin:34px 0}</style></head>
<body>
<h1>Support - Move Without Pain</h1>
<p>Questions, bugs, or feedback? Email <a href='mailto:brigbrednich@gmail.com'>brigbrednich@gmail.com</a> and we'll get back to you.</p>

<h2>Frequently asked questions</h2>
<div class='q'>Do I need an account?</div>
<p>No. There is no sign-up, no email, and no login. Open the app and start moving.</p>

<div class='q'>Why do the videos open outside the app?</div>
<p>Exercise demonstrations are hosted on YouTube and open in a Safari window so they play reliably on every device. Close the window to return to your routine.</p>

<div class='q'>I can't hear the guided session.</div>
<p>Guided sessions use your iPhone's built-in speech. Check that the silent/ringer switch on the side of your phone is not set to silent, and turn the volume up while a session is playing.</p>

<div class='q'>How do I switch between English and Spanish?</div>
<p>Tap the EN/ES button at the top of the screen. Everything changes, including the spoken narration.</p>

<div class='q'>Is my practice history stored anywhere?</div>
<p>Only on your device. Deleting the app deletes your history and streak.</p>

<div class='q'>Is this medical advice?</div>
<p>No. The app offers general mobility guidance and is not a substitute for professional medical advice. If you have an injury or a medical condition, speak with a healthcare professional first. Stop if something hurts.</p>

<hr>
<p><b>Soporte en español</b></p>
<p>Para preguntas, errores o comentarios, escribe a <a href='mailto:brigbrednich@gmail.com'>brigbrednich@gmail.com</a>.</p>
<p><b>No necesitas cuenta:</b> no hay registro ni inicio de sesion. <b>Los videos se abren en Safari</b> para reproducirse de forma confiable; cierra la ventana para volver. <b>Si no escuchas la sesion guiada,</b> revisa que el interruptor de silencio de tu iPhone no este activado y sube el volumen durante la sesion. <b>Para cambiar de idioma,</b> toca el boton EN/ES. <b>Tu historial</b> se guarda solo en tu dispositivo. <b>Esto no es consejo medico:</b> consulta a un profesional de la salud si tienes una lesion o condicion medica.</p>
<p><a href='/privacy'>Privacy Policy / Politica de privacidad</a></p>
</body></html>"""

@app.get("/support", response_class=HTMLResponse)
async def support():
    return SUPPORT_HTML

@app.get("/embed/{video_id}", response_class=HTMLResponse)
async def embed_video(video_id: str):
    if not all(c.isalnum() or c in "-_" for c in video_id) or len(video_id) > 20:
        raise HTTPException(status_code=404, detail="Not found")
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{margin:0;background:#000;height:100%;overflow:hidden}#p{width:100%;height:100%}#err{color:#fff;font-family:sans-serif;padding:12px;text-align:center}</style></head>
<body><div id="p"></div><div id="err"></div>
<script>
var tag=document.createElement('script');tag.src='https://www.youtube.com/iframe_api';document.head.appendChild(tag);
function onYouTubeIframeAPIReady(){
  new YT.Player('p',{videoId:'VIDEO_ID',
    playerVars:{playsinline:1,rel:0,origin:'https://movewithoutpain-production.up.railway.app'},
    events:{onError:function(e){document.getElementById('err').textContent='Video error '+e.data;}}});
}
</script></body></html>""".replace("VIDEO_ID", video_id)
