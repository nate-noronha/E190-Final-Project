"""
Unit and integration tests for the Shop Steward Safety Check-off Workflow (Slice 4).

Verifies role-enforcement, pending sign-off queue filtering, safety approval,
safety flagging, and step completion barriers.
"""

from datetime import datetime, timezone
import pytest
from sqlmodel import Session, select

from app.models.domain import Project, ProjectStep, User
from app.models.enums import FacilityEnum, ProjectStatusEnum, RoleEnum, SafetyLevelEnum, SubsystemEnum


def test_get_pending_signoffs(client, session: Session):
    student = User(name="Student A", email="student_a@hmc.edu", role=RoleEnum.STUDENT)
    session.add(student)
    session.commit()
    session.refresh(student)

    project = Project(
        title="Lathe Turning Project",
        description="Turning cylindrical stock",
        student_id=student.id,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    # Step 1: Normal step (no steward required)
    step1 = ProjectStep(
        project_id=project.id,
        step_order=1,
        title="Measure Stock",
        instructions="Use dial calipers",
        facility=FacilityEnum.MACHINE_SHOP,
        safety_level=SafetyLevelEnum.NORMAL,
        requires_steward_signoff=False,
    )
    # Step 2: Hazardous step (Machine shop lathe)
    step2 = ProjectStep(
        project_id=project.id,
        step_order=2,
        title="Turn on Lathe",
        instructions="High speed spindle turning",
        facility=FacilityEnum.MACHINE_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
    )
    # Step 3: Hazardous step (Wood shop table saw)
    step3 = ProjectStep(
        project_id=project.id,
        step_order=3,
        title="Rip Hardwood",
        instructions="Table saw rip cut",
        facility=FacilityEnum.WOOD_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
    )
    session.add_all([step1, step2, step3])
    session.commit()

    # Query all pending
    res = client.get("/api/steward/pending-signoffs")
    assert res.status_code == 200
    pending = res.json()
    assert len(pending) == 2
    step_titles = [p["title"] for p in pending]
    assert "Turn on Lathe" in step_titles
    assert "Rip Hardwood" in step_titles
    assert "Measure Stock" not in step_titles

    # Query filtered by facility=machine_shop
    res_mach = client.get("/api/steward/pending-signoffs?facility=machine_shop")
    assert res_mach.status_code == 200
    mach_pending = res_mach.json()
    assert len(mach_pending) == 1
    assert mach_pending[0]["title"] == "Turn on Lathe"
    assert mach_pending[0]["student_name"] == "Student A"
    assert mach_pending[0]["project_title"] == "Lathe Turning Project"


def test_approve_safety_success(client, session: Session):
    student = User(name="Student B", email="student_b@hmc.edu", role=RoleEnum.STUDENT)
    steward = User(name="Steward Sam", email="steward_sam@hmc.edu", role=RoleEnum.STEWARD)
    session.add_all([student, steward])
    session.commit()
    session.refresh(student)
    session.refresh(steward)

    proj = Project(title="Milling Part", description="CNC Mill", student_id=student.id)
    session.add(proj)
    session.commit()
    session.refresh(proj)

    step = ProjectStep(
        project_id=proj.id,
        step_order=1,
        title="CNC Mill",
        instructions="Cut aluminum bracket",
        facility=FacilityEnum.MACHINE_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
    )
    session.add(step)
    session.commit()
    session.refresh(step)

    # Approve safety as steward
    payload = {"steward_id": steward.id, "notes": "Clamping and spindle speed inspected."}
    res = client.post(f"/api/steps/{step.id}/approve-safety", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["safety_approved_by"] == steward.id
    assert data["safety_approved_at"] is not None
    assert "Clamping and spindle speed inspected." in data["safety_notes"]

    # Verify queue is now empty for this step
    q_res = client.get("/api/steward/pending-signoffs")
    assert not any(p["step_id"] == step.id for p in q_res.json())


def test_approve_safety_rejects_non_steward(client, session: Session):
    student1 = User(name="Student 1", email="s1@hmc.edu", role=RoleEnum.STUDENT)
    student2 = User(name="Student 2", email="s2@hmc.edu", role=RoleEnum.STUDENT)
    session.add_all([student1, student2])
    session.commit()
    session.refresh(student1)
    session.refresh(student2)

    proj = Project(title="Proj", description="Desc", student_id=student1.id)
    session.add(proj)
    session.commit()
    session.refresh(proj)

    step = ProjectStep(
        project_id=proj.id,
        step_order=1,
        title="High Voltage Wiring",
        instructions="Work on mains 120V",
        facility=FacilityEnum.EE_STOCKROOM,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
    )
    session.add(step)
    session.commit()
    session.refresh(step)

    # Student 2 attempts to sign off
    res = client.post(
        f"/api/steps/{step.id}/approve-safety",
        json={"steward_id": student2.id, "notes": "Self approved"},
    )
    assert res.status_code == 403
    assert "Only shop stewards" in res.json()["detail"]


def test_flag_safety_and_reset_approval(client, session: Session):
    student = User(name="Student C", email="sc@hmc.edu", role=RoleEnum.STUDENT)
    steward = User(name="Steward Jane", email="sj@hmc.edu", role=RoleEnum.STEWARD)
    session.add_all([student, steward])
    session.commit()
    session.refresh(student)
    session.refresh(steward)

    proj = Project(title="Proj C", description="Desc", student_id=student.id)
    session.add(proj)
    session.commit()
    session.refresh(proj)

    step = ProjectStep(
        project_id=proj.id,
        step_order=1,
        title="Router Table",
        instructions="Profile wood edges",
        facility=FacilityEnum.WOOD_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
        safety_approved_by=steward.id,
        safety_approved_at=datetime.now(timezone.utc),
        is_completed=True,
    )
    session.add(step)
    session.commit()
    session.refresh(step)

    # Flag safety hazard
    res = client.post(
        f"/api/steps/{step.id}/flag-safety",
        json={"steward_id": steward.id, "reason": "Featherboard missing, kickback risk"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["safety_approved_by"] is None
    assert data["safety_approved_at"] is None
    assert data["is_completed"] is False
    assert "SAFETY FLAG" in data["safety_notes"]


def test_toggle_complete_safety_barrier(client, session: Session):
    student = User(name="Student D", email="sd@hmc.edu", role=RoleEnum.STUDENT)
    steward = User(name="Steward Bob", email="sb@hmc.edu", role=RoleEnum.STEWARD)
    session.add_all([student, steward])
    session.commit()
    session.refresh(student)
    session.refresh(steward)

    proj = Project(title="Drone Arms", description="Milling arms", student_id=student.id)
    session.add(proj)
    session.commit()
    session.refresh(proj)

    # 1. Hazardous step requiring signoff
    haz_step = ProjectStep(
        project_id=proj.id,
        step_order=1,
        title="Mill Bracket",
        instructions="Run Haas CNC",
        facility=FacilityEnum.MACHINE_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
        is_completed=False,
    )
    # 2. Normal step
    norm_step = ProjectStep(
        project_id=proj.id,
        step_order=2,
        title="Sand 3D Part",
        instructions="Hand sand",
        facility=FacilityEnum.MAKERSPACE,
        safety_level=SafetyLevelEnum.NORMAL,
        requires_steward_signoff=False,
        is_completed=False,
    )
    session.add_all([haz_step, norm_step])
    session.commit()
    session.refresh(haz_step)
    session.refresh(norm_step)

    # Attempt to complete hazardous step WITHOUT approval -> MUST FAIL (400)
    res_fail = client.post(
        f"/api/steps/{haz_step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res_fail.status_code == 400
    assert "Cannot complete step before shop steward safety sign-off" in res_fail.json()["detail"]

    # Complete normal step -> SUCCEEDS (200)
    res_norm = client.post(
        f"/api/steps/{norm_step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res_norm.status_code == 200
    assert res_norm.json()["is_completed"] is True

    # Now steward approves hazardous step
    client.post(
        f"/api/steps/{haz_step.id}/approve-safety",
        json={"steward_id": steward.id, "notes": "Approved"},
    )

    # Attempt to complete hazardous step AFTER approval -> SUCCEEDS (200)
    res_ok = client.post(
        f"/api/steps/{haz_step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["is_completed"] is True

