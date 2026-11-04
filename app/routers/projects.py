"""
Projects router — mounted at /api/projects.

CRITICAL: LLM calls are NEVER made on GET endpoints or at module import time.
Only explicit POST requests to /generate-steps and /chat trigger Gemini.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.domain import Project, ProjectBOMItem, ProjectStep
from app.models.enums import ProjectStatusEnum
from app.models.schemas import (
    ErrorResponse,
    ProjectChatRequest,
    ProjectChatResponse,
    ProjectCreate,
    ProjectRead,
)
from app.services.gemini import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiService,
    GeminiServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Dependency: injectable Gemini service (override in tests via dependency_overrides)
# ---------------------------------------------------------------------------

_gemini_service = GeminiService()


def get_gemini_service() -> GeminiService:
    return _gemini_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_project_read(project: Project, session: Session) -> ProjectRead:
    """Load related steps and BOM items and return a ProjectRead DTO."""
    steps = session.exec(
        select(ProjectStep)
        .where(ProjectStep.project_id == project.id)
        .order_by(ProjectStep.step_order)
    ).all()

    bom_items = session.exec(
        select(ProjectBOMItem).where(ProjectBOMItem.project_id == project.id)
    ).all()

    return ProjectRead.model_validate(
        {
            **project.model_dump(),
            "steps": [s.model_dump() for s in steps],
            "bom_items": [b.model_dump() for b in bom_items],
        }
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
) -> ProjectRead:
    """Create a new project record. Does NOT call the LLM."""
    project = Project(
        student_id=payload.student_id,
        title=payload.title,
        description=payload.description,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return _load_project_read(project, session)


@router.get("", response_model=List[ProjectRead])
def list_projects(
    session: Session = Depends(get_session),
) -> List[ProjectRead]:
    """List all projects with their steps and BOM items. No LLM calls."""
    projects = session.exec(select(Project)).all()
    return [_load_project_read(p, session) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    session: Session = Depends(get_session),
) -> ProjectRead:
    """Return a single project with steps and BOM items, or 404."""
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _load_project_read(project, session)


@router.post("/{project_id}/generate-steps")
def generate_steps(
    project_id: int,
    session: Session = Depends(get_session),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """
    Explicit user-triggered endpoint: calls Gemini to generate fabrication steps.

    CRITICAL: This is only reachable via an explicit POST. No GET endpoint or
    page-load path ever invokes the LLM.
    """
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Call the LLM service
    try:
        plan = gemini.generate_project_plan(project.title, project.description)
    except GeminiConfigurationError as exc:
        logger.warning("Gemini not configured: %s", exc)
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="GEMINI_NOT_CONFIGURED",
                message="Google Gemini API key is not configured on this server.",
                retryable=False,
            ).model_dump(),
        )
    except GeminiNetworkError as exc:
        logger.warning("Gemini network timeout: %s", exc)
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error="GEMINI_NETWORK_TIMEOUT",
                message="Network timeout contacting Google Gemini API. Please retry.",
                retryable=True,
            ).model_dump(),
        )
    except GeminiServiceError as exc:
        logger.error("Gemini service error: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="GEMINI_UPSTREAM_ERROR",
                message=f"Upstream error from Google Gemini API: {exc}",
                retryable=False,
            ).model_dump(),
        )

    # Clear any previously generated draft steps and BOM items for this project
    old_steps = session.exec(
        select(ProjectStep).where(ProjectStep.project_id == project_id)
    ).all()
    for s in old_steps:
        session.delete(s)

    old_bom = session.exec(
        select(ProjectBOMItem).where(ProjectBOMItem.project_id == project_id)
    ).all()
    for b in old_bom:
        session.delete(b)

    # Persist new steps
    for step_data in plan.steps:
        step = ProjectStep(
            project_id=project_id,
            step_order=step_data.step_order,
            subsystem=step_data.subsystem,
            title=step_data.title,
            instructions=step_data.instructions,
            facility=step_data.facility,
            safety_level=step_data.safety_level,
            requires_steward_signoff=step_data.requires_steward_signoff,
            safety_notes=step_data.safety_notes,
        )
        session.add(step)

    # Persist BOM items
    for bom_data in plan.bom_items:
        bom = ProjectBOMItem(
            project_id=project_id,
            part_name=bom_data.part_name,
            quantity_needed=bom_data.quantity_needed,
            source_status=bom_data.source_status,
            external_purchase_note=bom_data.external_purchase_note,
        )
        session.add(bom)

    # Advance project status and commit so data survives restarts
    project.status = ProjectStatusEnum.IN_PROGRESS
    session.add(project)
    session.commit()
    session.refresh(project)

    return _load_project_read(project, session)


@router.post("/{project_id}/chat")
def project_chat(
    project_id: int,
    payload: ProjectChatRequest,
    session: Session = Depends(get_session),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """
    Explicit user-triggered chat endpoint. Passes project context + history to Gemini.

    CRITICAL: Only reachable via an explicit POST from the user pressing "Send".
    """
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    steps = session.exec(
        select(ProjectStep)
        .where(ProjectStep.project_id == project_id)
        .order_by(ProjectStep.step_order)
    ).all()

    try:
        reply = gemini.project_chat(
            title=project.title,
            description=project.description,
            steps=list(steps),
            history=payload.history,
            user_message=payload.message,
        )
    except GeminiConfigurationError as exc:
        logger.warning("Gemini not configured for chat: %s", exc)
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="GEMINI_NOT_CONFIGURED",
                message="Google Gemini API key is not configured on this server.",
                retryable=False,
            ).model_dump(),
        )
    except GeminiNetworkError as exc:
        logger.warning("Gemini network timeout on chat: %s", exc)
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error="GEMINI_NETWORK_TIMEOUT",
                message="Network timeout contacting Google Gemini API. Please retry.",
                retryable=True,
            ).model_dump(),
        )
    except GeminiServiceError as exc:
        logger.error("Gemini service error on chat: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="GEMINI_UPSTREAM_ERROR",
                message=f"Upstream error from Google Gemini API: {exc}",
                retryable=False,
            ).model_dump(),
        )

    return ProjectChatResponse(reply=reply)
