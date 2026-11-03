"""
Integration tests for the /api/projects router.

These tests run against a real PostgreSQL instance (see conftest.py).
Gemini calls are always mocked — no live LLM traffic.
"""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import get_engine, get_session, reset_engine
from app.main import app
from app.models.domain import Project, ProjectBOMItem, ProjectStep
from app.models.enums import (
    BOMSourceStatusEnum,
    FacilityEnum,
    ProjectStatusEnum,
    RoleEnum,
    SafetyLevelEnum,
    SubsystemEnum,
)
from app.routers.projects import get_gemini_service
from app.services.gemini import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiProjectPlanOutput,
    GeminiService,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_plan() -> GeminiProjectPlanOutput:
    """Return a minimal but valid GeminiProjectPlanOutput for mocking."""
    return GeminiProjectPlanOutput(
        summary="Machine a simple bracket.",
        steps=[
            {
                "step_order": 1,
                "subsystem": SubsystemEnum.MECHANICAL,
                "title": "Mill the profile",
                "instructions": "Clamp stock and mill the outer profile on the Bridgeport.",
                "facility": FacilityEnum.MACHINE_SHOP,
                "safety_level": SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
                "requires_steward_signoff": True,
                "safety_notes": "Mill operation — steward sign-off required.",
            },
            {
                "step_order": 2,
                "subsystem": SubsystemEnum.ASSEMBLY,
                "title": "Deburr edges",
                "instructions": "Use a hand file to remove all burrs.",
                "facility": FacilityEnum.MACHINE_SHOP,
                "safety_level": SafetyLevelEnum.NORMAL,
                "requires_steward_signoff": False,
                "safety_notes": None,
            },
        ],
        bom_items=[
            {
                "part_name": "6061 Aluminum Sheet 1/4\"",
                "quantity_needed": 1,
                "source_status": BOMSourceStatusEnum.EXTERNAL_PURCHASE_NEEDED,
                "facility": None,
                "external_purchase_note": "McMaster-Carr",
            }
        ],
    )


def _mock_gemini_service(plan: GeminiProjectPlanOutput | None = None) -> GeminiService:
    """Return a GeminiService whose generate_project_plan returns `plan`."""
    if plan is None:
        plan = _make_plan()
    mock_svc = MagicMock(spec=GeminiService)
    mock_svc.generate_project_plan.return_value = plan
    return mock_svc


def _create_test_user(session: Session) -> int:
    """Insert a student user and return its id."""
    from app.models.domain import User

    user = User(name="Test Student", email="student@test.hmc.edu", role=RoleEnum.STUDENT)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id


@pytest.fixture
def client_with_mock_gemini(session):
    """TestClient with the Gemini service replaced by a mock that returns _make_plan()."""
    mock_svc = _mock_gemini_service()

    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    with TestClient(app) as c:
        yield c, mock_svc

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: POST /api/projects
# ---------------------------------------------------------------------------


def test_post_projects_creates_and_commits_project(client, session):
    """POST /api/projects persists a project and returns 201 with the new record."""
    student_id = _create_test_user(session)

    resp = client.post(
        "/api/projects",
        json={
            "title": "CNC Bracket",
            "description": "Mill a bracket from 6061 aluminum.",
            "student_id": student_id,
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "CNC Bracket"
    assert data["student_id"] == student_id
    assert data["status"] == ProjectStatusEnum.DRAFT.value
    assert isinstance(data["id"], int)
    assert data["steps"] == []
    assert data["bom_items"] == []

    # Confirm the row actually landed in Postgres
    project = session.get(Project, data["id"])
    assert project is not None
    assert project.title == "CNC Bracket"


def test_post_projects_returns_422_without_required_fields(client):
    """POST /api/projects without required fields returns 422."""
    resp = client.post("/api/projects", json={"title": "Missing desc and student"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: GET /api/projects and GET /api/projects/{id}
# ---------------------------------------------------------------------------


def test_get_projects_returns_list(client, session):
    """GET /api/projects returns a list (empty or populated)."""
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_project_returns_404_for_missing_id(client):
    """GET /api/projects/99999 returns 404 when the project doesn't exist."""
    resp = client.get("/api/projects/99999")
    assert resp.status_code == 404


def test_get_project_returns_created_record(client, session):
    """GET /api/projects/{id} returns the project that was just created."""
    student_id = _create_test_user(session)
    create_resp = client.post(
        "/api/projects",
        json={"title": "Pulley", "description": "3D printed pulley.", "student_id": student_id},
    )
    project_id = create_resp.json()["id"]

    resp = client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id
    assert resp.json()["title"] == "Pulley"


# ---------------------------------------------------------------------------
# Tests: POST /api/projects/{id}/generate-steps
# ---------------------------------------------------------------------------


def test_generate_steps_persists_to_postgres_across_engine_reset(session):
    """
    Steps generated by LLM must survive a simulated container restart.

    Flow:
      1. Create user + project via HTTP
      2. Call generate-steps with a mocked Gemini service
      3. Dispose the engine (simulates restart)
      4. Re-read from a brand-new session
      5. Assert steps and BOM items are intact
    """
    # Need a separate client setup to control mock at this level
    plan = _make_plan()
    mock_svc = _mock_gemini_service(plan)

    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    student_id = _create_test_user(session)

    with TestClient(app) as c:
        create_resp = c.post(
            "/api/projects",
            json={
                "title": "Persistence Test Bracket",
                "description": "Check that steps survive restart.",
                "student_id": student_id,
            },
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        gen_resp = c.post(f"/api/projects/{project_id}/generate-steps")
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert len(gen_data["steps"]) == 2
        assert gen_data["status"] == ProjectStatusEnum.IN_PROGRESS.value

    app.dependency_overrides.clear()

    # Simulate container restart by disposing the engine
    reset_engine()

    # Re-read from a completely fresh engine/session
    fresh_engine = get_engine()
    with Session(fresh_engine) as fresh_session:
        project = fresh_session.get(Project, project_id)
        assert project is not None
        assert project.status == ProjectStatusEnum.IN_PROGRESS

        steps = fresh_session.exec(
            select(ProjectStep).where(ProjectStep.project_id == project_id)
        ).all()
        assert len(steps) == 2
        assert steps[0].requires_steward_signoff is True

        bom = fresh_session.exec(
            select(ProjectBOMItem).where(ProjectBOMItem.project_id == project_id)
        ).all()
        assert len(bom) == 1
        assert bom[0].part_name == "6061 Aluminum Sheet 1/4\""


def test_generate_steps_returns_503_when_no_api_key(session):
    """POST /api/projects/{id}/generate-steps returns 503 when Gemini key is missing."""
    unconfigured_svc = MagicMock(spec=GeminiService)
    unconfigured_svc.generate_project_plan.side_effect = GeminiConfigurationError(
        "GEMINI_API_KEY not set"
    )

    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: unconfigured_svc

    student_id = _create_test_user(session)

    with TestClient(app) as c:
        create_resp = c.post(
            "/api/projects",
            json={"title": "503 Test", "description": "Triggers missing key.", "student_id": student_id},
        )
        project_id = create_resp.json()["id"]

        resp = c.post(f"/api/projects/{project_id}/generate-steps")

    app.dependency_overrides.clear()

    assert resp.status_code == 503
    body = resp.json()
    assert body["error"] == "GEMINI_NOT_CONFIGURED"
    assert body["retryable"] is False


def test_generate_steps_returns_honest_failure_on_timeout(session):
    """POST /api/projects/{id}/generate-steps returns 504 on network timeout."""
    timeout_svc = MagicMock(spec=GeminiService)
    timeout_svc.generate_project_plan.side_effect = GeminiNetworkError(
        "Connection timed out"
    )

    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: timeout_svc

    student_id = _create_test_user(session)

    with TestClient(app) as c:
        create_resp = c.post(
            "/api/projects",
            json={"title": "Timeout Test", "description": "Triggers timeout.", "student_id": student_id},
        )
        project_id = create_resp.json()["id"]

        resp = c.post(f"/api/projects/{project_id}/generate-steps")

    app.dependency_overrides.clear()

    assert resp.status_code == 504
    body = resp.json()
    assert body["error"] == "GEMINI_NETWORK_TIMEOUT"
    assert body["retryable"] is True


# ---------------------------------------------------------------------------
# Tests: zero LLM calls on GET endpoints
# ---------------------------------------------------------------------------


def test_zero_llm_calls_on_get_endpoints(session):
    """
    GET /api/projects, GET /health, and GET / must never call the Gemini service.

    A spy on GeminiService.generate_project_plan and project_chat confirms
    exactly 0 calls across all read-only / page-load paths.
    """
    call_log: list = []

    class SpyGeminiService(GeminiService):
        def generate_project_plan(self, title, description):  # type: ignore[override]
            call_log.append(("generate_project_plan", title))
            return super().generate_project_plan(title, description)

        def project_chat(self, title, description, steps, history, user_message):  # type: ignore[override]
            call_log.append(("project_chat", user_message))
            return super().project_chat(title, description, steps, history, user_message)

    spy_svc = SpyGeminiService(client=MagicMock())  # mock client so no real key needed

    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: spy_svc

    student_id = _create_test_user(session)

    with TestClient(app) as c:
        # Create a project so GET /api/projects isn't empty
        create_resp = c.post(
            "/api/projects",
            json={"title": "Spy Test", "description": "Testing spy.", "student_id": student_id},
        )
        project_id = create_resp.json()["id"]

        # Fire every non-mutating / page-load path
        c.get("/")
        c.get("/health")
        c.get("/api/projects")
        c.get(f"/api/projects/{project_id}")

    app.dependency_overrides.clear()

    # No LLM calls must have occurred
    assert call_log == [], (
        f"Expected 0 LLM calls on GET endpoints, but got: {call_log}"
    )
