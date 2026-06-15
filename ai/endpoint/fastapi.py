from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.endpoint import chat, admin

app = FastAPI(
    title="Asnany AI API",
    version="0.1.0",
)

# CORS (مهم جدًا)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"],
)

app.include_router(
    admin.router,
    prefix="/api/admin",
    tags=["admin"],
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "asnany-ai",
    }

@app.get("/")
def root():
    return {"message": "Asnany AI API is running"}