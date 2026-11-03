import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.users import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup logic (DB init) only when DATABASE_URL is configured."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from app.database import init_db

            init_db()
            logger.info("Database tables initialized.")
        except Exception as exc:
            logger.error("Failed to initialize database: %s", exc)
            # Do not crash the process; /health will report 503
    else:
        logger.warning(
            "DATABASE_URL is not set — skipping DB init. "
            "Set DATABASE_URL before starting in production."
        )
    yield


app = FastAPI(
    title="E190 Hardware & Machining Prototyping Assistant",
    description=(
        "Backend API for HMC E190 — breaks down physical engineering projects into "
        "step-by-step instructions, integrates steward safety sign-offs, and tracks "
        "makerspace/stockroom inventory."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(users_router)
