import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers.health import router as health_router
from app.routers.integrations import router as integrations_router
from app.routers.inventory import router as inventory_router
from app.routers.projects import router as projects_router
from app.routers.steward import router as steward_router
from app.routers.users import router as users_router

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
INDEX_FILE = TEMPLATES_DIR / "index.html"


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

# Mount static directory for stylesheets, scripts, and static assets
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), html=True),
    name="static",
)

# Route index root GET / to pure semantic HTML5 shell
@app.get("/", response_class=FileResponse)
async def read_root():
    """Serve the stark Greek design system and mobile-first semantic HTML5 shell."""
    return FileResponse(str(INDEX_FILE), media_type="text/html")


app.include_router(health_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(steward_router)
app.include_router(inventory_router)
app.include_router(integrations_router)

