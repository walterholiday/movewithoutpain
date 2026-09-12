from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta
import os

from models import SessionLocal, Exercise, DailyTip, engine
from ai_client import deepseek, DEFAULT_MODEL
from paths import PATHS, PATH_SLUGS, EXERCISE_PATHS
from entitlements import (
    Caller,
    caller,
    subscription_block,
    verify_webhook,
    handle_webhook,
    refresh as refresh_entitlement,
)
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
async def get_paths(db: Session = Depends(get_db), c: Caller = Depends(caller)):
    """List the 6 routine paths with bilingual metadata, premium flag, and exercise counts."""
    exercises = db.query(Exercise).all()
    counts = {slug: 0 for slug in PATH_SLUGS}
    for ex in exercises:
        for slug in (ex.paths or "full").split(","):
            if slug in counts:
                counts[slug] += 1
    return {
        "paths": [
            {
                **p,
                "exercise_count": counts.get(p["slug"], 0),
                # `unlocked` is what the client should render off. Legacy (v1.0)
                # builds ignore it and stay fully unlocked; v1.1+ builds send
                # X-MWP-Api: 2 and get honest values.
                "unlocked": c.may_access(p["premium"]),
            }
            for p in sorted(PATHS, key=lambda p: p["order"])
        ],
        "subscription": {
            **subscription_block(c),
            "unlocks": sorted(p["slug"] for p in PATHS if p["premium"]),
        },
    }

@app.get("/today", response_model=TodayResponse)
async def get_today(
    path: Optional[str] = None,
    db: Session = Depends(get_db),
    c: Caller = Depends(caller),
):
    """Daily routine. Optional ?path=slug filters to one routine path (default: full)."""
    if path is not None and path not in PATH_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown path '{path}'. Valid: {sorted(PATH_SLUGS)}")
    if path:
        requested = next((p for p in PATHS if p["slug"] == path), None)
        if requested and not c.may_access(requested["premium"]):
            raise HTTPException(
                status_code=403,
                detail={"error": "premium_required", "path": path},
            )
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
<p><i>Effective September 12, 2026</i></p>
<p>Move Without Pain ("the app") is a bilingual mobility training app. We keep things simple: <b>the app has no user accounts, and we do not collect your name, email address, or any information that identifies you personally.</b></p>
<h2>What stays on your device</h2>
<p>Your practice history, streaks, language preference, and reminder settings are stored only on your device. They are never uploaded to our servers.</p>
<h2>What is sent to our servers</h2>
<p>The app fetches the daily exercise list and daily tip from our server. When you ask the AI coach a question, the text of your question is sent to our server and forwarded to an AI provider (DeepSeek) to generate a response. Questions are not linked to your identity, are not used for advertising, and are never sold.</p>
<p>The app also creates a random identifier for your device the first time you open it. It is a random string, not derived from your name, email, phone number, or any Apple identifier, and it is what tells our server whether this device has an active subscription. It is stored on your device and sent with requests to our server. We cannot use it to identify you.</p>
<h2>Subscriptions and payment</h2>
<p>Move Without Pain Premium is an auto-renewing subscription, available as a monthly or an
annual plan. The price is shown in your local currency on the subscription screen in the app
before you are asked to confirm anything.</p>
<p>Payment is charged to your Apple Account when you confirm the purchase. The subscription
renews automatically for the same period and price unless it is cancelled at least 24 hours
before the end of the current period. Your Apple Account is charged for the renewal within 24
hours of the end of the current period.</p>
<p>You can manage or cancel your subscription at any time in Settings on your device, under
your Apple Account, then Subscriptions. Deleting the app does not cancel your subscription.</p>
<p>Purchases are processed by Apple. We never see or store your payment card details. We use
RevenueCat, a subscription management service, to verify with Apple whether a subscription is
active. RevenueCat receives the random device identifier described above and the purchase
receipt from Apple - not your name, email address, or payment details.</p>
<p>Terms of use for the subscription are Apple's standard licence agreement, available at
<a href='https://www.apple.com/legal/internet-services/itunes/dev/stdeula/'>apple.com/legal/internet-services/itunes/dev/stdeula</a>.</p>

<h2>Third-party content</h2>
<p>Exercise demo videos are provided through YouTube, which may collect data according to Google's privacy policy when videos play.</p>
<h2>Not medical advice</h2>
<p>The app offers general mobility guidance and is not a substitute for professional medical advice. Consult a healthcare professional for injuries or medical conditions.</p>
<h2>Contact</h2>
<p>Questions? Email <a href='mailto:brigbrednich@gmail.com'>brigbrednich@gmail.com</a>.</p>
<hr>
<h2>Politica de privacidad (resumen en espanol)</h2>
<p>La app no tiene cuentas de usuario y no recopila tu nombre, correo electronico ni ningun dato
que te identifique personalmente. Tu historial de practica se guarda solo en tu dispositivo. Las
preguntas al coach de IA se envian a nuestro servidor y a DeepSeek para generar la respuesta, sin
vincularse a tu identidad ni venderse.</p>
<p>La app crea un identificador aleatorio para tu dispositivo la primera vez que la abres. Es una
cadena aleatoria, no derivada de tu nombre, correo ni de ningun identificador de Apple, y sirve
para saber si este dispositivo tiene una suscripcion activa.</p>
<h2>Suscripciones y pago</h2>
<p>Move Without Pain Premium es una suscripcion de renovacion automatica, disponible en plan
mensual o anual. El precio se muestra en tu moneda local en la pantalla de suscripcion antes de
confirmar la compra.</p>
<p>El pago se carga a tu cuenta de Apple al confirmar la compra. La suscripcion se renueva
automaticamente por el mismo periodo y precio salvo que se cancele al menos 24 horas antes del
final del periodo actual. Puedes gestionarla o cancelarla cuando quieras en Ajustes, en tu cuenta
de Apple, apartado Suscripciones. Borrar la app no cancela la suscripcion.</p>
<p>Las compras las procesa Apple. Nunca vemos ni almacenamos los datos de tu tarjeta. Usamos
RevenueCat para verificar con Apple si una suscripcion esta activa; RevenueCat recibe el
identificador aleatorio del dispositivo y el recibo de compra de Apple, no tu nombre, correo ni
datos de pago.</p>
<p>Contacto: <a href='mailto:brigbrednich@gmail.com'>brigbrednich@gmail.com</a>.</p>
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


# --------------------------------------------------------------------------- #
# Billing (RevenueCat)
# --------------------------------------------------------------------------- #

@app.post("/billing/revenuecat/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_revenuecat_webhook_signature: Optional[str] = Header(
        default=None, alias="X-RevenueCat-Webhook-Signature"
    ),
    db: Session = Depends(get_db),
):
    """RevenueCat posts subscription lifecycle events here.

    We ignore the event's entitlement fields and re-fetch authoritative state
    from RevenueCat for every app_user_id the event mentions. Always answer 200
    on success — anything else makes RevenueCat retry (5x, backing off).
    """
    body = await request.body()
    verify_webhook(body, authorization, x_revenuecat_webhook_signature)
    payload = await request.json()
    return handle_webhook(db, payload)


@app.get("/billing/status")
async def billing_status(c: Caller = Depends(caller)):
    """What the server believes about the calling device. Used by the app after a
    purchase or restore, and by you for debugging a support ticket."""
    return {
        "app_user_id": c.app_user_id,
        "api_version": c.api_version,
        "gating_active": c.gated,
        "premium": c.premium,
    }


@app.post("/billing/refresh")
async def billing_refresh(c: Caller = Depends(caller), db: Session = Depends(get_db)):
    """Force a RevenueCat re-check for the calling device. The app calls this
    immediately after a successful purchase or restore so the server does not
    wait on the webhook."""
    if not c.app_user_id:
        raise HTTPException(status_code=400, detail="Missing X-Device-Id header")
    row = refresh_entitlement(db, c.app_user_id)
    return {
        "app_user_id": c.app_user_id,
        "premium": bool(row.is_active) if row else False,
        "expires_at": row.expires_at.isoformat() if row and row.expires_at else None,
    }
