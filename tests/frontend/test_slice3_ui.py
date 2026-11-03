"""
Tests for Slice 3 Frontend:
1. Honest error banner rendering on simulated 503/504 failure.
2. Zero LLM calls on page load (DOMContentLoaded / GET / /health / /api/users).
3. Zero <div> tags in template (index.html) and client-side JS markup generators.
4. Semantic structure of Project Co-Pilot: subsystem tabs, BOM table, chat thread, and progress bars.
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_engine, get_session
from app.main import app
from app.models.domain import Project, User
from app.models.enums import RoleEnum
from app.routers.projects import get_gemini_service
from app.services.gemini import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiService,
)

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "templates"
    / "index.html"
)
JS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "static"
    / "js"
    / "app.js"
)
CSS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "static"
    / "css"
    / "style.css"
)


class StrictTagCollector(HTMLParser):
    """HTML parser to audit all tags and detect any forbidden <div> tags."""

    def __init__(self):
        super().__init__()
        self.tags = set()
        self.div_tags = []
        self.element_ids = set()

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        self.tags.add(tag_lower)
        if tag_lower == "div":
            self.div_tags.append(tag)

        for attr, val in attrs:
            if attr == "id" and val:
                self.element_ids.add(val)


# ===========================================================================
# 1. ZERO <div> TAGS ASSERTIONS
# ===========================================================================


def test_zero_div_tags_in_template():
    """Assert absolutely zero <div> tags exist anywhere in app/templates/index.html."""
    assert TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}"
    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    collector = StrictTagCollector()
    collector.feed(content)
    assert collector.div_tags == [], (
        f"Found {len(collector.div_tags)} forbidden <div> tags in template!"
    )

    assert not re.search(r"<\s*div[\s>]", content, re.IGNORECASE), (
        "Regex detected opening <div> tag in index.html"
    )
    assert not re.search(r"<\s*/\s*div\s*>", content, re.IGNORECASE), (
        "Regex detected closing </div> tag in index.html"
    )


def test_zero_div_tags_in_javascript_markup():
    """Assert app/static/js/app.js does not generate any <div> elements dynamically."""
    assert JS_PATH.exists(), f"app.js not found at {JS_PATH}"
    js_content = JS_PATH.read_text(encoding="utf-8")

    # Check for document.createElement("div")
    assert not re.search(
        r'createElement\s*\(\s*["\']div["\']\s*\)', js_content, re.IGNORECASE
    ), "Detected document.createElement('div') in app.js!"

    # Strip JS comments before checking for HTML strings
    cleaned_js = re.sub(r"/\*.*?\*/", "", js_content, flags=re.DOTALL)
    cleaned_js = re.sub(r"//.*", "", cleaned_js)

    # Check for <div tags inside template literals or strings
    assert not re.search(r"<\s*div[\s>]", cleaned_js, re.IGNORECASE), (
        "Detected literal '<div' in executable JavaScript code in app.js!"
    )
    assert not re.search(r"<\s*/\s*div\s*>", cleaned_js, re.IGNORECASE), (
        "Detected literal '</div>' in executable JavaScript code in app.js!"
    )


# ===========================================================================
# 2. ZERO LLM CALLS ON PAGE LOAD
# ===========================================================================


def test_page_load_makes_zero_llm_calls_spy(client: TestClient, session: Session):
    """
    Assert page load (GET /, /health, /api/users, /api/projects) makes 0 calls to LLM.
    Verified with a spy on GeminiService.
    """
    call_log = []

    class SpyGeminiService(GeminiService):
        def generate_project_plan(self, title, description):  # type: ignore[override]
            call_log.append(("generate_project_plan", title))
            return super().generate_project_plan(title, description)

        def project_chat(self, title, description, steps, history, user_message):  # type: ignore[override]
            call_log.append(("project_chat", user_message))
            return super().project_chat(title, description, steps, history, user_message)

    spy_svc = SpyGeminiService(client=MagicMock())

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

    try:
        # 1. Fetch HTML shell (GET /)
        res_root = client.get("/")
        assert res_root.status_code == 200

        # 2. Fetch static assets
        res_css = client.get("/static/css/style.css")
        assert res_css.status_code == 200
        res_js = client.get("/static/js/app.js")
        assert res_js.status_code == 200

        # 3. Simulate DOMContentLoaded client-side calls
        res_health = client.get("/health")
        assert res_health.status_code == 200

        res_users = client.get("/api/users?role=student")
        assert res_users.status_code == 200

        res_projects = client.get("/api/projects")
        assert res_projects.status_code == 200

        # Spy log must be completely empty
        assert call_log == [], f"LLM was invoked during page load / read operations: {call_log}"
    finally:
        app.dependency_overrides.clear()


# ===========================================================================
# 3. HONEST FAILURE UI & SIMULATED 503 / 504 ERROR HANDLING
# ===========================================================================


def test_honest_error_banner_elements_in_template():
    """Assert honest error banners and retry buttons exist in index.html semantic markup."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = StrictTagCollector()
    collector.feed(content)

    # Generation alert banner
    assert "generation-alert" in collector.element_ids
    assert "generation-alert-title" in collector.element_ids
    assert "generation-alert-message" in collector.element_ids
    assert "btn-retry-generate" in collector.element_ids

    # Chat alert banner
    assert "chat-alert-box" in collector.element_ids
    assert "chat-alert-title" in collector.element_ids
    assert "chat-alert-message" in collector.element_ids
    assert "btn-retry-chat" in collector.element_ids

    # Accessibility attributes
    assert 'role="alert"' in content


def test_simulated_503_gemini_not_configured_returns_honest_error(session: Session):
    """
    When Gemini API key is missing, POST /generate-steps must return 503
    with explicit GEMINI_NOT_CONFIGURED error payload.
    """
    mock_svc = MagicMock(spec=GeminiService)
    mock_svc.generate_project_plan.side_effect = GeminiConfigurationError(
        "GEMINI_API_KEY is not set or empty."
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
    app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    try:
        with TestClient(app) as c:
            # Create user and project
            u_res = c.post(
                "/api/users",
                json={"name": "Alice Tester", "email": "alice@hmc.edu", "role": "student"},
            )
            assert u_res.status_code in (201, 409)
            user_id = u_res.json().get("id") if u_res.status_code == 201 else 1

            p_res = c.post(
                "/api/projects",
                json={"title": "Solar Tracker", "description": "Gimbal assembly", "student_id": user_id},
            )
            assert p_res.status_code == 201
            project_id = p_res.json()["id"]

            # Dispatch step generation (simulates user clicking DECOMPOSE)
            gen_res = c.post(f"/api/projects/{project_id}/generate-steps")
            assert gen_res.status_code == 503
            err_data = gen_res.json()
            assert err_data["error"] == "GEMINI_NOT_CONFIGURED"
            assert "Google Gemini API key is not configured" in err_data["message"]
            assert err_data["retryable"] is False
    finally:
        app.dependency_overrides.clear()


def test_simulated_504_gemini_network_timeout_returns_honest_error(session: Session):
    """
    When Gemini network call times out, POST /generate-steps must return 504
    with GEMINI_NETWORK_TIMEOUT and retryable=True.
    """
    mock_svc = MagicMock(spec=GeminiService)
    mock_svc.generate_project_plan.side_effect = GeminiNetworkError(
        "Gemini API connection timed out after 30s"
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
    app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    try:
        with TestClient(app) as c:
            u_res = c.post(
                "/api/users",
                json={"name": "Bob Tester", "email": "bob@hmc.edu", "role": "student"},
            )
            user_id = u_res.json().get("id") if u_res.status_code == 201 else 1

            p_res = c.post(
                "/api/projects",
                json={"title": "CNC Yoke", "description": "Machined yoke", "student_id": user_id},
            )
            project_id = p_res.json()["id"]

            gen_res = c.post(f"/api/projects/{project_id}/generate-steps")
            assert gen_res.status_code == 504
            err_data = gen_res.json()
            assert err_data["error"] == "GEMINI_NETWORK_TIMEOUT"
            assert "timeout" in err_data["message"].lower()
            assert err_data["retryable"] is True
    finally:
        app.dependency_overrides.clear()


def test_simulated_chat_503_honest_error(session: Session):
    """Chat endpoint must return 503 with honest error when unconfigured."""
    mock_svc = MagicMock(spec=GeminiService)
    mock_svc.project_chat.side_effect = GeminiConfigurationError(
        "GEMINI_API_KEY is not set or empty."
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
    app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    try:
        with TestClient(app) as c:
            u_res = c.post(
                "/api/users",
                json={"name": "Charlie Tester", "email": "charlie@hmc.edu", "role": "student"},
            )
            user_id = u_res.json().get("id") if u_res.status_code == 201 else 1

            p_res = c.post(
                "/api/projects",
                json={"title": "Chat Test", "description": "Chatting", "student_id": user_id},
            )
            project_id = p_res.json()["id"]

            chat_res = c.post(
                f"/api/projects/{project_id}/chat",
                json={"message": "What is the recommended spindle speed?", "history": []},
            )
            assert chat_res.status_code == 503
            err_data = chat_res.json()
            assert err_data["error"] == "GEMINI_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.clear()


# ===========================================================================
# 4. CHAT, BOM & SUBSYSTEM SEMANTIC UI LANDMARKS
# ===========================================================================


def test_chat_section_semantic_structure():
    """Assert project chat section contains semantic list <ul class='chat-thread'>."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = StrictTagCollector()
    collector.feed(content)

    assert "copilot-chat-section" in content
    assert "chat-thread-list" in collector.element_ids
    assert "chat-form" in collector.element_ids
    assert "chat-input" in collector.element_ids
    assert "btn-send-chat" in collector.element_ids
    assert "chat-thread" in content
    assert "chat-message" in content
    assert "chat-bubble" in content


def test_subsystem_tabs_semantic_structure():
    """Assert all 4 engineering subsystems + ALL filter buttons exist in markup."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'data-subsystem="all"' in content
    assert 'data-subsystem="mechanical"' in content
    assert 'data-subsystem="electrical"' in content
    assert 'data-subsystem="firmware"' in content
    assert 'data-subsystem="assembly"' in content
    assert "active-subsystem-badge" in content


def test_bom_table_semantic_structure():
    """Assert BOM table exists with semantic table landmarks and sourcing tags."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = StrictTagCollector()
    collector.feed(content)

    assert "bom-table-body" in collector.element_ids
    assert "bom-items-count-badge" in collector.element_ids
    assert "[IN_STOCK_ON_CAMPUS]" in content
    assert "[EXTERNAL_PURCHASE_NEEDED]" in content
    assert "th" in collector.tags
    assert "td" in collector.tags
    assert "thead" in collector.tags
    assert "tbody" in collector.tags


def test_high_contrast_progress_elements():
    """Assert high-contrast <progress> elements exist for generation and chat."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = StrictTagCollector()
    collector.feed(content)

    assert "progress" in collector.tags
    assert "generation-progress" in collector.element_ids
    assert "chat-progress" in collector.element_ids
