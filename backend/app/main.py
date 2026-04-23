"""Video-Use Platform — FastAPI Application Entry Point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.core.config import OUTPUT_DIR, UPLOAD_DIR

from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.ws import router as ws_router
from app.api.routes.templates import router as templates_router
from app.api.routes.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup: initialize database tables
    await init_db()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Video-Use Platform",
    description="Automated video editing with real-time progress monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(uploads_router)
app.include_router(jobs_router)
app.include_router(ws_router)
app.include_router(templates_router)
app.include_router(settings_router)

# ── Static file serving for outputs ─────────────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


# ── Health check ────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "video-use-platform",
        "version": "1.0.0",
    }
