import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app.database import get_engine

router = APIRouter()


@router.get("/health")
def health_check():
    """Check application and database health.

    Returns 200 with {"status": "ok", "database": "connected"} when the DB is reachable.
    Returns 503 with an honest error payload (no credentials leaked) otherwise.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": "DATABASE_URL environment variable is not configured",
            },
        )

    try:
        engine = get_engine()
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except OperationalError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": "Database connection failed",
            },
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": str(exc),
            },
        )
