from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta
import os

from models import SessionLocal, Exercise, DailyTip
from ai_client import deepseek, DEFAULT_MODEL

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
    """Seed the exercises table on boot if it's empty, so no Railway Console step is needed."""
    db = SessionLocal()
    try:
        if db.query(Exercise).count() == 0:
            from seed import seed
            seed()
            print("✅ Auto-seeded empty exercises table on startup.")
    except Exception as e:
        print(f"⚠️ Auto-seed skipped: {e}")
    finally:
        db.close()

@app.get("/")
async def root():
    return {
        "message": "Move Without Pain API is running 🧘",
        "endpoints": ["/today", "/history", "/stats", "/ai/coach"],
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

class TodayResponse(BaseModel):
    date: str
    exercises: List[ExerciseResponse]
    tip: Optional[str]

class CoachRequest(BaseModel):
    user_message: str
    language: str = "en"
    context: Optional[str] = None

@app.get("/today", response_model=TodayResponse)
async def get_today(db: Session = Depends(get_db)):
    exercises = db.query(Exercise).order_by(Exercise.category, Exercise.order).all()
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
