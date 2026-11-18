"""
Project step router.

Handles toggling a manufacturing step's completion status.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models.domain import ProjectStep, User
from app.models.schemas import ProjectStepRead, StepCompleteToggle

router = APIRouter(tags=["steps"])


@router.post("/api/steps/{step_id}/toggle-complete", response_model=ProjectStepRead)
def toggle_step_complete(
    step_id: int,
    payload: StepCompleteToggle,
    session: Session = Depends(get_session),
):
    """Toggle step completion status."""
    step = session.get(ProjectStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    user = session.get(User, payload.student_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    step.is_completed = payload.is_completed
    session.add(step)
    session.commit()
    session.refresh(step)

    return ProjectStepRead.model_validate(step)
