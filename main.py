app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    ...
)@app.get("/")
async def root():
    return {
        "message": "Move Without Pain API is running 🧘",
        "endpoints": ["/today", "/history", "/stats", "/ai/coach"],
        "docs": "/docs"
    }
