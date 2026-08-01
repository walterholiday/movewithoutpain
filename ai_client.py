import os
from openai import AsyncOpenAI

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Don't crash the whole app at boot if the key is missing —
# /today, /history, /stats still work; /ai/coach returns 503.
deepseek = (
    AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    if DEEPSEEK_API_KEY
    else None
)

DEFAULT_MODEL = "deepseek-v4-pro"
