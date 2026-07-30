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

# --- Root endpoint (fixes 404) ---
@app.get("/")
async def root():
    return {
        "message": "Move Without Pain API is running 🧘",
        "endpoints": ["/today", "/history", "/stats", "/ai/coach"],
        "docs": "/docs"
    }

# --- Pydantic models ---
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

# --- Endpoints ---

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
