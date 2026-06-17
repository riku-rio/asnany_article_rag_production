from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ai.endpoint import chat, admin
from database.admin_service import seed_owner
from database.tables.dashboard_users import create_dashboard_users_table
from database.db import get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_dashboard_users_table()
    seed_owner()
    yield


def _ensure_dashboard_users_table():
    try:
        conn = get_connection()
        try:
            create_dashboard_users_table(conn)
        finally:
            conn.close()
    except Exception as e:
        print(f"⚠️  Could not create dashboard_users table: {e}")


app = FastAPI(
    title="Asnany AI API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
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
    admin.auth_router,
    prefix="/api/admin",
    tags=["admin"],
)

app.include_router(
    admin.router,
    prefix="/api/admin",
    tags=["admin"],
)

app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "asnany-ai",
    }

@app.get("/")
def root():
    return {"message": "Asnany AI API is running"}