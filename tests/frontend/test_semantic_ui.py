"""
Frontend UI test suite for the Harvey Mudd E190 Prototyping Assistant.

Verifies:
1. Pure Semantic HTML5 with ZERO <div> tags (audit both template and GET / response).
2. Key semantic landmarks exist (<header>, <nav>, <main>, <section>, <article>, <dialog>, <footer>, <aside>, <figure>, <table>, <form>).
3. Viewport meta tag is configured mobile-first (width=device-width, initial-scale=1.0).
4. GET / returns 200 OK with Content-Type text/html.
5. Page load makes 0 calls to any LLM service.
6. Role switcher present with Student and Steward options.
7. Safety modal dialog (<dialog id="safety-modal">) with semantic form & checklist.
8. All 4 navigation tabs and 4 HMC facilities represented.
9. Static assets (/static/css/style.css, /static/js/app.js) mounted and reachable.
10. Stark Greek design system CSS rules (B&W palette, serif headings, >=44px touch targets).
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "templates"
    / "index.html"
)
CSS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "static"
    / "css"
    / "style.css"
)
JS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "static"
    / "js"
    / "app.js"
)


class SemanticTagCollector(HTMLParser):
    """HTML parser to audit all tags and detect any forbidden <div> tags."""

    def __init__(self):
        super().__init__()
        self.tags = set()
        self.tag_counts = {}
        self.div_tags = []
        self.element_ids = set()

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        self.tags.add(tag_lower)
        self.tag_counts[tag_lower] = self.tag_counts.get(tag_lower, 0) + 1

        if tag_lower == "div":
            self.div_tags.append(tag)

        for attr, val in attrs:
            if attr == "id" and val:
                self.element_ids.add(val)


def test_zero_div_tags_in_template():
    """Assert zero <div> tags exist anywhere in app/templates/index.html."""
    assert TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}"
    content = TEMPLATE_PATH.read_text(encoding="utf-8")

    # 1. Standard library HTMLParser audit
    collector = SemanticTagCollector()
    collector.feed(content)
    assert collector.div_tags == [], (
        f"Found {len(collector.div_tags)} forbidden <div> tags in template!"
    )

    # 2. Strict regex checks for opening and closing div tags
    assert not re.search(r"<\s*div[\s>]", content, re.IGNORECASE), (
        "Regex detected opening <div> tag in index.html"
    )
    assert not re.search(r"<\s*/\s*div\s*>", content, re.IGNORECASE), (
        "Regex detected closing </div> tag in index.html"
    )


def test_get_root_returns_200_html(client: TestClient):
    """Assert GET / returns HTTP 200 OK with text/html content type."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_get_root_serves_zero_div_tags(client: TestClient):
    """Assert HTTP response body from GET / has zero <div> tags."""
    response = client.get("/")
    assert response.status_code == 200
    html_body = response.text

    collector = SemanticTagCollector()
    collector.feed(html_body)
    assert collector.div_tags == [], (
        f"GET / response contains {len(collector.div_tags)} forbidden <div> tags!"
    )
    assert not re.search(r"<\s*div[\s>]", html_body, re.IGNORECASE)
    assert not re.search(r"<\s*/\s*div\s*>", html_body, re.IGNORECASE)


def test_key_semantic_landmarks_present():
    """Assert key semantic HTML5 landmarks are utilized in the markup."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = SemanticTagCollector()
    collector.feed(content)

    required_landmarks = [
        "header",
        "nav",
        "main",
        "section",
        "article",
        "dialog",
        "footer",
        "aside",
        "figure",
        "figcaption",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "form",
        "fieldset",
        "legend",
        "label",
        "input",
        "textarea",
        "button",
        "code",
        "kbd",
        "time",
    ]

    for landmark in required_landmarks:
        assert landmark in collector.tags, (
            f"Expected semantic landmark <{landmark}> was not found in template!"
        )


def test_mobile_first_viewport_meta():
    """Assert viewport meta tag is properly configured for mobile-first display."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    viewport_match = re.search(
        r'<meta\s+name=["\']viewport["\']\s+content=["\']([^"\']+)["\']',
        content,
        re.IGNORECASE,
    )
    assert viewport_match is not None, "Missing <meta name='viewport'> tag"
    viewport_content = viewport_match.group(1)
    assert "width=device-width" in viewport_content
    assert "initial-scale=1.0" in viewport_content


def test_page_load_makes_zero_llm_calls(client: TestClient, monkeypatch):
    """Assert page load (GET / and GET /health) makes 0 calls to any LLM service."""
    call_log = []

    def mock_llm_call(*args, **kwargs):
        call_log.append(("llm_called", args, kwargs))

    for mod_name in ("anthropic", "openai", "google.generativeai", "litellm"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            for attr in ("Anthropic", "OpenAI", "GenerativeModel", "completion"):
                if hasattr(mod, attr):
                    monkeypatch.setattr(mod, attr, mock_llm_call, raising=False)

    # 1. Load the page shell
    res_index = client.get("/")
    assert res_index.status_code == 200

    # 2. Simulate client-side DOMContentLoaded health check
    res_health = client.get("/health")
    assert res_health.status_code == 200

    assert call_log == [], f"LLM was invoked during page load: {call_log}"


def test_role_switcher_structure():
    """Assert stark role switcher (Student vs Steward) is present and accessible."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'value="student"' in content
    assert 'value="steward"' in content
    assert "role-switcher-fieldset" in content
    assert "[STUDENT]" in content
    assert "[STEWARD]" in content


def test_four_navigation_tabs_present():
    """Assert all 4 primary architectural navigation tabs are present in markup."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "tab-copilot" in content
    assert "tab-steward" in content
    assert "tab-stockroom" in content
    assert "tab-cad" in content
    assert "PROJECT CO-PILOT" in content
    assert "STEWARD QUEUE" in content
    assert "CAMPUS STOCKROOM" in content
    assert "3D CAD PREVIEW" in content


def test_four_hmc_facilities_represented():
    """Assert all four HMC prototyping facilities are represented."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    facilities = [
        "[MACHINE_SHOP]",
        "[WOOD_SHOP]",
        "[EE_STOCKROOM]",
        "[MAKERSPACE]",
    ]
    for fac in facilities:
        assert fac in content, f"Facility badge {fac} missing from template markup"


def test_safety_modal_dialog_semantic():
    """Assert <dialog id='safety-modal'> exists with semantic form controls."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    collector = SemanticTagCollector()
    collector.feed(content)

    assert "safety-modal" in collector.element_ids
    assert "dialog" in collector.tags
    assert 'method="dialog"' in content or 'id="dialog-signoff-form"' in content
    assert 'type="checkbox"' in content
    assert "chk-ppe" in collector.element_ids
    assert "chk-fixture" in collector.element_ids
    assert "chk-speeds" in collector.element_ids
    assert "chk-estop" in collector.element_ids


def test_static_assets_mounted_and_served(client: TestClient):
    """Assert static CSS and JS are mounted at /static and served with 200 OK."""
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == 200
    assert (
        "application/javascript" in js_res.headers.get("content-type", "")
        or "text/javascript" in js_res.headers.get("content-type", "")
    )


def test_stark_greek_design_css_rules():
    """Assert CSS adheres to Stark Greek aesthetic and mobile-first standards."""
    assert CSS_PATH.exists()
    css_content = CSS_PATH.read_text(encoding="utf-8")

    # Color palette
    assert "#000000" in css_content
    assert "#FFFFFF" in css_content

    # Typography
    assert "Cormorant Garamond" in css_content or "Playfair Display" in css_content or "Georgia" in css_content
    assert "JetBrains Mono" in css_content or "monospace" in css_content

    # Mobile-first touch targets
    assert "44px" in css_content

    # Mobile-first responsive media queries
    assert "@media" in css_content


def test_vanilla_js_zero_page_load_llm_queries():
    """Assert client-side JS does not contain page-load AI queries."""
    assert JS_PATH.exists()
    js_content = JS_PATH.read_text(encoding="utf-8")

    # Ensures health check is queried on load
    assert "DOMContentLoaded" in js_content
    assert "/health" in js_content

    # Ensures no automatic AI call
    assert "fetch('/api/generate" not in js_content
    assert "fetch('/api/llm" not in js_content
