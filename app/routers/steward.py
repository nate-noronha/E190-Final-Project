"""
Steward safety sign-off router.

Handles shop steward sign-offs, safety hazard flags, pending approval queue,
and step completion barriers for safety-critical operations.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.domain import Project, ProjectStep, User
from app.models.enums import FacilityEnum, RoleEnum
from app.models.schemas import (
    PendingSignoffRead,
    ProjectStepRead,
    StepCompleteToggle,
    StewardFlagRequest,
    StewardSignoffRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["steward"])


@router.get("/api/steward/pending-signoffs", response_model=List[PendingSignoffRead])
def get_pending_signoffs(
    facility: Optional[FacilityEnum] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Retrieve all project steps requiring steward safety sign-off that are not yet approved."""
    query = (
        select(ProjectStep, Project, User)
        .join(Project, ProjectStep.project_id == Project.id)
        .join(User, Project.student_id == User.id)
        .where(ProjectStep.requires_steward_signoff == True)  # noqa: E712
        .where(ProjectStep.safety_approved_at == None)  # noqa: E711
    )

    if facility:
        query = query.where(ProjectStep.facility == facility)

    query = query.order_by(ProjectStep.id)
    results = session.exec(query).all()

    pending = []
    for step, project, student in results:
        pending.append(
            PendingSignoffRead(
                step_id=step.id,
                project_id=project.id,
                project_title=project.title,
                student_id=student.id,
                student_name=student.name,
                step_order=step.step_order,
                subsystem=step.subsystem,
                facility=step.facility,
                title=step.title,
                instructions=step.instructions,
                safety_notes=step.safety_notes,
                safety_level=step.safety_level,
            )
        )
    return pending


@router.post("/api/steps/{step_id}/approve-safety", response_model=ProjectStepRead)
def approve_step_safety(
    step_id: int,
    payload: StewardSignoffRequest,
    session: Session = Depends(get_session),
):
    """Steward approval of a safety barrier.

    Verifies the user has the STEWARD role, records attribution and timestamp,
    and commits to Postgres.
    """
    step = session.get(ProjectStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    steward = session.get(User, payload.steward_id)
    if not steward:
        raise HTTPException(status_code=404, detail="Steward user not found")

    if steward.role != RoleEnum.STEWARD:
        raise HTTPException(
            status_code=403,
            detail="Only shop stewards can sign off on safety barriers",
        )

    now = datetime.now(timezone.utc)
    step.safety_approved_by = steward.id
    step.safety_approved_at = now

    if payload.notes:
        existing_notes = f"{step.safety_notes} | " if step.safety_notes else ""
        step.safety_notes = f"{existing_notes}Approved by {steward.name}: {payload.notes}".strip()

    session.add(step)
    session.commit()
    session.refresh(step)

    logger.info(
        "Step %d safety approved by steward %s (%d) at %s",
        step.id,
        steward.name,
        steward.id,
        now.isoformat(),
    )
    return ProjectStepRead.model_validate(step)


@router.post("/api/steps/{step_id}/flag-safety", response_model=ProjectStepRead)
def flag_step_safety(
    step_id: int,
    payload: StewardFlagRequest,
    session: Session = Depends(get_session),
):
    """Steward flags a safety hazard or revokes sign-off.

    Requires STEWARD role, resets approval timestamps, and appends flag notes.
    """
    step = session.get(ProjectStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    steward = session.get(User, payload.steward_id)
    if not steward:
        raise HTTPException(status_code=404, detail="Steward user not found")

    if steward.role != RoleEnum.STEWARD:
        raise HTTPException(
            status_code=403,
            detail="Only shop stewards can flag safety concerns",
        )

    # Revoke approval and record safety flag
    step.safety_approved_by = None
    step.safety_approved_at = None
    step.is_completed = False

    flag_text = f"[SAFETY FLAG from {steward.name}]: {payload.reason}"
    step.safety_notes = (
        f"{step.safety_notes} | {flag_text}" if step.safety_notes else flag_text
    )

    session.add(step)
    session.commit()
    session.refresh(step)

    logger.warning("Step %d flagged by steward %s: %s", step.id, steward.name, payload.reason)
    return ProjectStepRead.model_validate(step)


@router.post("/api/steps/{step_id}/toggle-complete", response_model=ProjectStepRead)
def toggle_step_complete(
    step_id: int,
    payload: StepCompleteToggle,
    session: Session = Depends(get_session),
):
    """Toggle step completion status.

    ENFORCEMENT: A step marked requires_steward_signoff CANNOT be completed
    unless safety_approved_at is set.
    """
    step = session.get(ProjectStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    user = session.get(User, payload.student_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.is_completed and step.requires_steward_signoff and not step.safety_approved_at:
        raise HTTPException(
            status_code=400,
            detail="Cannot complete step before shop steward safety sign-off",
        )

    step.is_completed = payload.is_completed
    session.add(step)
    session.commit()
    session.refresh(step)

    return ProjectStepRead.model_validate(step)

