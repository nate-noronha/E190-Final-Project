"""
Automated Compliance Directive Suite (Slice 6).

Asserts the 6 non-negotiable architectural invariants:
1. Zero <div> soup in HTML templates and dynamic frontend JavaScript.
2. Zero LLM calls on page load or any GET endpoint.
3. Strict Steward Safety Gate invariant (hazardous steps cannot be completed without steward sign-off).
4. Relational durability across engine resets (reset_engine()).
5. Zero secrets tracked in git or hardcoded in source files.
6. Honest error envelopes (503 on missing key, retryable diagnostics).
"""

from pathlib import Path
import re
from unittest.mock import MagicMock
import pytest
from sqlmodel import Session, select

from app.database import get_engine, reset_engine
from app.models.domain import InventoryItem, Project, ProjectStep, User
from app.models.enums import FacilityEnum, RoleEnum, SafetyLevelEnum
from app.routers.projects import get_gemini_service
from app.services.gemini import GeminiConfigurationError, GeminiService


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# DIRECTIVE 1: ZERO-DIV SOUP
# ---------------------------------------------------------------------------


def test_directive_1_zero_div_soup_in_templates():
    """Ensure zero <div> tags exist anywhere in HTML templates."""
    templates_dir = REPO_ROOT / "app" / "templates"
    html_files = list(templates_dir.rglob("*.html"))
    assert len(html_files) > 0, "No HTML template files found to inspect"

    div_regex = re.compile(r"<\s*/?\s*div(\s+|>)", re.IGNORECASE)

    for html_path in html_files:
        content = html_path.read_text(encoding="utf-8")
        matches = div_regex.findall(content)
        assert len(matches) == 0, (
            f"VIOLATION: Found {len(matches)} <div> tags in {html_path.name}. "
            "CLAUDE.md strictly prohibits <div> soup — use semantic HTML5 elements."
        )


def test_directive_1_zero_div_soup_in_javascript():
    """Ensure zero <div> tags are generated dynamically in frontend JavaScript."""
    static_js_dir = REPO_ROOT / "app" / "static" / "js"
    js_files = list(static_js_dir.rglob("*.js"))
    assert len(js_files) > 0, "No JavaScript files found to inspect"

    div_html_regex = re.compile(r"<\s*/?\s*div(\s+|>)", re.IGNORECASE)
    div_create_regex = re.compile(r"createElement\s*\(\s*['\"]div['\"]\s*\)", re.IGNORECASE)

    for js_path in js_files:
        content = js_path.read_text(encoding="utf-8")
        html_matches = div_html_regex.findall(content)
        create_matches = div_create_regex.findall(content)
        assert len(html_matches) == 0, (
            f"VIOLATION: Found {len(html_matches)} <div> string literals in {js_path.name}."
        )
        assert len(create_matches) == 0, (
            f"VIOLATION: Found {len(create_matches)} document.createElement('div') in {js_path.name}."
        )


# ---------------------------------------------------------------------------
# DIRECTIVE 2: ZERO PAGE-LOAD LLM CALLS
# ---------------------------------------------------------------------------


def test_directive_2_zero_page_load_llm(client, monkeypatch):
    """Ensure that all GET endpoints and initial page load execute ZERO calls to Gemini."""
    spy_service = GeminiService()
    spy_service.generate_project_plan = MagicMock()
    spy_service.project_chat = MagicMock()

    from app.main import app
    app.dependency_overrides[get_gemini_service] = lambda: spy_service

    try:
        # 1. Page load
        r_root = client.get("/")
        assert r_root.status_code == 200

        # 2. Health check
        r_health = client.get("/health")
        assert r_health.status_code == 200

        # 3. Read projects
        r_proj = client.get("/api/projects")
        assert r_proj.status_code == 200

        # 4. Read steward queue
        r_steward = client.get("/api/steward/pending-signoffs")
        assert r_steward.status_code == 200

        # 5. Read inventory
        r_inv = client.get("/api/inventory")
        assert r_inv.status_code == 200

        # 6. Read CAD status
        r_cad = client.get("/api/integrations/cad/status")
        assert r_cad.status_code == 200

        # ASSERT: Zero LLM invocations across all GET routes!
        assert spy_service.generate_project_plan.call_count == 0, (
            f"VIOLATION: generate_project_plan called {spy_service.generate_project_plan.call_count} times on GET!"
        )
        assert spy_service.project_chat.call_count == 0, (
            f"VIOLATION: project_chat called {spy_service.project_chat.call_count} times on GET!"
        )
    finally:
        app.dependency_overrides.pop(get_gemini_service, None)


# ---------------------------------------------------------------------------
# DIRECTIVE 3: STRICT STEWARD SAFETY GATE INVARIANT
# ---------------------------------------------------------------------------


def test_directive_3_steward_safety_invariant(client, session: Session):
    """Enforce that hazardous steps cannot be completed without shop steward sign-off."""
    student = User(name="Student Safety Check", email="safety_student@hmc.edu", role=RoleEnum.STUDENT)
    session.add(student)
    session.commit()
    session.refresh(student)

    project = Project(title="Bridgeport Milling", description="Milling steel", student_id=student.id)
    session.add(project)
    session.commit()
    session.refresh(project)

    haz_step = ProjectStep(
        project_id=project.id,
        step_order=1,
        title="Operate Bridgeport Mill",
        instructions="High torque milling",
        facility=FacilityEnum.MACHINE_SHOP,
        safety_level=SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
        requires_steward_signoff=True,
    )
    session.add(haz_step)
    session.commit()
    session.refresh(haz_step)

    # Invariant A: Student cannot mark completed without sign-off
    res = client.post(
        f"/api/steps/{haz_step.id}/toggle-complete",
        json={"student_id": student.id, "is_completed": True},
    )
    assert res.status_code == 400
    assert "Cannot complete step before shop steward safety sign-off" in res.json()["detail"]

    # Invariant B: Student cannot sign off on safety
    res_bad_signoff = client.post(
        f"/api/steps/{haz_step.id}/approve-safety",
        json={"steward_id": student.id, "notes": "I approve myself"},
    )
    assert res_bad_signoff.status_code == 403


# ---------------------------------------------------------------------------
# DIRECTIVE 4: DURABILITY ACROSS ENGINE RESETS
# ---------------------------------------------------------------------------


def test_directive_4_durability_across_engine_resets(session: Session):
    """Verify that committed records survive database engine teardown/reset."""
    student = User(name="Persistent Student", email="persistent@hmc.edu", role=RoleEnum.STUDENT)
    session.add(student)
    session.commit()
    session.refresh(student)
    saved_user_id = student.id

    inv = InventoryItem(
        sku="DURABLE-STOCK-01",
        name="Brass Stock 1.0 OD",
        category="Metals",
        facility=FacilityEnum.MACHINE_SHOP,
        location="Rack 1",
        quantity=25,
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    saved_inv_id = inv.id

    # Reset engine (simulates container restart or connection recycling)
    reset_engine()

    # Open fresh session from the newly created engine
    with Session(get_engine()) as fresh_session:
        loaded_student = fresh_session.get(User, saved_user_id)
        assert loaded_student is not None
        assert loaded_student.email == "persistent@hmc.edu"

        loaded_inv = fresh_session.get(InventoryItem, saved_inv_id)
        assert loaded_inv is not None
        assert loaded_inv.sku == "DURABLE-STOCK-01"
        assert loaded_inv.quantity == 25


# ---------------------------------------------------------------------------
# DIRECTIVE 5: SECRET HYGIENE
# ---------------------------------------------------------------------------


def test_directive_5_secret_hygiene():
    """Verify that no real API secrets or credentials exist in tracked source files."""
    code_extensions = [".py", ".html", ".js", ".css", ".toml", ".yml", ".yaml"]
    ignored_dirs = [".git", ".venv", "__pycache__", ".pytest_cache", ".worktrees"]

    # Pattern for typical real Google AI Studio keys
    key_pattern = re.compile(r"AIzaSy[A-Za-z0-9_-]{33}")

    for root, dirs, files in os_walk_filtered(REPO_ROOT, ignored_dirs):
        for f in files:
            p = Path(root) / f
            if p.suffix in code_extensions and p.name != ".env":
                content = p.read_text(encoding="utf-8", errors="ignore")
                matches = key_pattern.findall(content)
                assert len(matches) == 0, (
                    f"CRITICAL VIOLATION: Hardcoded API key detected in {p.relative_to(REPO_ROOT)}!"
                )


def os_walk_filtered(base_path: Path, ignored_names: list[str]):
    for root, dirs, files in base_path.walk():
        dirs[:] = [d for d in dirs if d not in ignored_names]
        yield root, dirs, files


# ---------------------------------------------------------------------------
# DIRECTIVE 6: HONEST ERROR ENVELOPES
# ---------------------------------------------------------------------------


def test_directive_6_honest_error_envelopes(session: Session):
    """Verify that failure states return 503 with honest, structured retryable errors."""
    student = User(name="Test Student", email="test_student_err@hmc.edu", role=RoleEnum.STUDENT)
    session.add(student)
    session.commit()
    session.refresh(student)

    project = Project(title="Drone Project", description="Drone motor mounts", student_id=student.id)
    session.add(project)
    session.commit()
    session.refresh(project)

    mock_bad_service = MagicMock(spec=GeminiService)
    mock_bad_service.generate_project_plan.side_effect = GeminiConfigurationError("GEMINI_API_KEY is not set.")

    from app.main import app
    from fastapi.testclient import TestClient
    from app.database import get_engine, get_session

    def override_get_session():
        with Session(get_engine()) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_gemini_service] = lambda: mock_bad_service

    try:
        with TestClient(app) as c:
            res = c.post(f"/api/projects/{project.id}/generate-steps")
        assert res.status_code == 503
        data = res.json()
        assert data["error"] == "GEMINI_NOT_CONFIGURED"
        assert data["retryable"] is False
        assert "Google Gemini API key" in data["message"]
    finally:
        app.dependency_overrides.clear()
