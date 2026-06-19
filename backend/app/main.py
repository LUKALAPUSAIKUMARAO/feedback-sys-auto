from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.database import create_all_tables
from app.core.redis_client import get_redis, close_redis
from app.core.seed import seed_database
from app.api.v1 import auth, admin, feedback, analytics, admin_participants, webhook
from app.api.v1 import settings as settings_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.startup", name=settings.APP_NAME, version=settings.APP_VERSION)
    await create_all_tables()
    await seed_database()
    try:
        await get_redis()
    except Exception as e:
        log.warning("app.redis_init_failed", error=str(e))
    yield
    await close_redis()
    log.info("app.shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Training Intelligence Platform — Bilvantis Agentic AI Hackathon",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(admin_participants.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/api/v1/ping")
async def ping():
    return {"ping": "pong"}
