"""
Unit tests for app/services/gemini.py.

All tests use injected mock clients — NO real Gemini API calls are made.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.models.enums import (
    BOMSourceStatusEnum,
    FacilityEnum,
    SafetyLevelEnum,
    SubsystemEnum,
)
from app.services.gemini import (
    GeminiConfigurationError,
    GeminiNetworkError,
    GeminiProjectPlanOutput,
    GeminiService,
    GeminiServiceError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(plan: GeminiProjectPlanOutput) -> MagicMock:
    """Wrap a GeminiProjectPlanOutput as a mock Gemini SDK response object."""
    mock_resp = MagicMock()
    mock_resp.text = plan.model_dump_json()
    return mock_resp


def _minimal_plan() -> GeminiProjectPlanOutput:
    return GeminiProjectPlanOutput(
        summary="Build a simple lathe-turned aluminum shaft.",
        steps=[
            {
                "step_order": 1,
                "subsystem": SubsystemEnum.MECHANICAL,
                "title": "Turn shaft on lathe",
                "instructions": "Mount the aluminum bar stock in the lathe chuck. Turn to 12mm diameter.",
                "facility": FacilityEnum.MACHINE_SHOP,
                "safety_level": SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED,
                "requires_steward_signoff": True,
                "safety_notes": "Lathe operation requires steward sign-off.",
            },
            {
                "step_order": 2,
                "subsystem": SubsystemEnum.ASSEMBLY,
                "title": "Deburr and finish",
                "instructions": "File any sharp edges with a hand file. Sand with 220-grit.",
                "facility": FacilityEnum.MACHINE_SHOP,
                "safety_level": SafetyLevelEnum.NORMAL,
                "requires_steward_signoff": False,
                "safety_notes": None,
            },
        ],
        bom_items=[
            {
                "part_name": "6061 Aluminum Rod 1\" dia x 6\"",
                "quantity_needed": 1,
                "source_status": BOMSourceStatusEnum.EXTERNAL_PURCHASE_NEEDED,
                "facility": None,
                "external_purchase_note": "McMaster-Carr #8974K46",
            }
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_gemini_service_raises_when_no_api_key(monkeypatch):
    """Service must raise GeminiConfigurationError when GEMINI_API_KEY is absent."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    svc = GeminiService()  # no injected client → will try to read env var
    with pytest.raises(GeminiConfigurationError) as exc_info:
        svc.generate_project_plan("Test Project", "A simple test description.")

    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_gemini_service_raises_when_api_key_empty(monkeypatch):
    """Service must raise GeminiConfigurationError when GEMINI_API_KEY is empty string."""
    monkeypatch.setenv("GEMINI_API_KEY", "")

    svc = GeminiService()
    with pytest.raises(GeminiConfigurationError):
        svc.generate_project_plan("Test", "desc")


def test_gemini_service_parses_structured_plan_with_mock():
    """Service correctly parses a valid structured JSON response from a mock client."""
    plan = _minimal_plan()
    mock_response = _make_mock_response(plan)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    svc = GeminiService(client=mock_client)
    result = svc.generate_project_plan(
        title="Aluminum Shaft",
        description="Turn a 12mm shaft from 6061 bar stock.",
    )

    assert isinstance(result, GeminiProjectPlanOutput)
    assert result.summary == plan.summary
    assert len(result.steps) == 2
    assert result.steps[0].requires_steward_signoff is True
    assert result.steps[0].safety_level == SafetyLevelEnum.STEWARD_SIGN_OFF_REQUIRED
    assert result.steps[1].requires_steward_signoff is False
    assert result.steps[1].safety_level == SafetyLevelEnum.NORMAL
    assert len(result.bom_items) == 1
    assert result.bom_items[0].part_name == "6061 Aluminum Rod 1\" dia x 6\""

    # Verify the model was called exactly once with the right model ID
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs.kwargs.get("model") == GeminiService.MODEL or (
        len(call_kwargs.args) > 0 and call_kwargs.args[0] == GeminiService.MODEL
    )


def test_gemini_service_handles_network_timeout():
    """Service wraps a timeout exception from the SDK into GeminiNetworkError."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError(
        "Connection timed out after 30s"
    )

    svc = GeminiService(client=mock_client)
    with pytest.raises(GeminiNetworkError) as exc_info:
        svc.generate_project_plan("Timeout Test", "Intentionally triggers a timeout.")

    assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()


def test_gemini_service_handles_connection_error():
    """Service wraps a generic connection error into GeminiNetworkError."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ConnectionError(
        "Failed to establish a new connection"
    )

    svc = GeminiService(client=mock_client)
    with pytest.raises(GeminiNetworkError):
        svc.generate_project_plan("Conn Error Test", "desc")


def test_gemini_service_handles_rate_limit():
    """Service wraps a 429/quota error into GeminiRateLimitError."""
    from app.services.gemini import GeminiRateLimitError

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        "429 Resource exhausted: quota exceeded"
    )

    svc = GeminiService(client=mock_client)
    with pytest.raises(GeminiRateLimitError):
        svc.generate_project_plan("Rate Limit Test", "desc")


def test_gemini_service_raises_on_malformed_json():
    """Service raises GeminiServiceError when response is not valid JSON."""
    mock_response = MagicMock()
    mock_response.text = "not valid json {{{"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    svc = GeminiService(client=mock_client)
    with pytest.raises(GeminiServiceError):
        svc.generate_project_plan("Bad JSON Test", "desc")


def test_gemini_project_chat_with_mock():
    """project_chat passes history and returns the model's text response."""
    mock_response = MagicMock()
    mock_response.text = "You should use a 12mm end mill for that pocket."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    svc = GeminiService(client=mock_client)
    reply = svc.project_chat(
        title="Bracket",
        description="CNC milled aluminum bracket",
        steps=[],
        history=[
            {"role": "user", "content": "What tool should I use?"},
            {"role": "model", "content": "It depends on the feature size."},
        ],
        user_message="What about a 12mm pocket?",
    )

    assert reply == "You should use a 12mm end mill for that pocket."
    mock_client.models.generate_content.assert_called_once()


def test_gemini_service_no_import_side_effects(monkeypatch):
    """Importing GeminiService must not trigger any API calls or key validation."""
    # Unset the key — if the service tried to validate at import time, it would
    # already have raised before we even get here.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Re-import to simulate a fresh module load
    import importlib

    import app.services.gemini as gemini_module

    importlib.reload(gemini_module)
    # If we reach here without exception, the module is safe to import without a key.
    assert gemini_module.GeminiService is not None
