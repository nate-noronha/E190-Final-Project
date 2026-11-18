"""Tests for step completion (steward sign-off workflow removed)."""

from sqlmodel import Session

from app.models.domain import Project, ProjectStep, User
from app.models.enums import FacilityEnum, RoleEnum


def _make_step(session: Session):
    student = User(name="Student S", email="steps_student@hmc.edu", role=RoleEnum.STUDENT)
    session.add(student)
    session.commit()
    session.refresh(student)

    proj = Project(title="Drone Arms", description="Milling arms", student_id=student.id)
    session.add(proj)
    session.commit()
    session.refresh(proj)

    step = ProjectStep(
        project_id=proj.id,
        step_order=1,
        title="Mill Bracket",
        instructions="Run Haas CNC",
        facility=FacilityEnum.MACHINE_SHOP,
        requires_steward_signoff=True,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return student, step


def test_toggle_complete_and_back(client, session: Session):
    student, step = _make_step(session)

    res = client.post(
        f"/api/steps/{step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res.status_code == 200
    assert res.json()["is_completed"] is True

    res = client.post(
        f"/api/steps/{step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": False},
    )
    assert res.status_code == 200
    assert res.json()["is_completed"] is False


def test_toggle_complete_unknown_step(client, session: Session):
    student, _ = _make_step(session)
    res = client.post(
        "/api/steps/999999/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res.status_code == 404


def test_toggle_complete_unknown_user(client, session: Session):
    _, step = _make_step(session)
    res = client.post(
        f"/api/steps/{step.id}/toggle-complete",
        json={"student_id": 999999, "is_completed": True},
    )
    assert res.status_code == 404
