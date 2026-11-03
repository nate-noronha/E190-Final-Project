"""
Gemini LLM service for the E190 Prototyping Assistant.

CRITICAL: This module never instantiates a live client or validates API keys at
import time. All network activity is deferred to explicit method calls.

Usage:
    svc = GeminiService()                 # lazy — no network, no key check
    plan = svc.generate_project_plan(title, description)

    # For tests, inject a mock client:
    svc = GeminiService(client=mock_client)
"""

import os
from typing import Optional

from pydantic import BaseModel

from app.models.enums import (
    BOMSourceStatusEnum,
    FacilityEnum,
    SafetyLevelEnum,
    SubsystemEnum,
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class GeminiServiceError(Exception):
    """Base class for all Gemini service errors."""


class GeminiConfigurationError(GeminiServiceError):
    """Raised when GEMINI_API_KEY is not set or is empty."""


class GeminiNetworkError(GeminiServiceError):
    """Raised on timeout or connectivity failure contacting the Gemini API."""


class GeminiRateLimitError(GeminiServiceError):
    """Raised when the Gemini API returns a quota / 429 rate-limit response."""


# ---------------------------------------------------------------------------
# Structured output models (Pydantic, NOT SQLModel table models)
# ---------------------------------------------------------------------------


class GeminiStepOutput(BaseModel):
    step_order: int
    subsystem: SubsystemEnum
    title: str
    instructions: str
    facility: Optional[FacilityEnum] = None
    safety_level: SafetyLevelEnum
    requires_steward_signoff: bool
    safety_notes: Optional[str] = None


class GeminiBOMOutput(BaseModel):
    part_name: str
    quantity_needed: int
    source_status: BOMSourceStatusEnum
    facility: Optional[FacilityEnum] = None
    external_purchase_note: Optional[str] = None


class GeminiProjectPlanOutput(BaseModel):
    summary: str
    steps: list[GeminiStepOutput]
    bom_items: list[GeminiBOMOutput]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert machining and fabrication assistant for Harvey Mudd College's E190
Multidisciplinary Prototyping course. You help students break down physical engineering
projects into clear, safe, step-by-step fabrication plans.

## HMC Fabrication Ecosystem
You are aware of the following four facilities on campus:
- **Machine Shop** (machine_shop): lathes, mills, drill presses, grinders.
- **Wood Shop** (wood_shop): table saw, band saw, planer, router table, sanders.
- **EE Stockroom** (ee_stockroom): electronic components, benchtop PSUs, soldering stations, oscilloscopes.
- **Makerspace** (makerspace): 3D printers, laser cutters, vinyl cutter, hand tools, heat guns.

## Subsystems
Classify every step as one of: mechanical, electrical, firmware, aesthetic, assembly.

## Safety Rules — STRICTLY ENFORCED
The following operations ALWAYS require steward sign-off
(`requires_steward_signoff: true`, `safety_level: steward_sign_off_required`):
- Any operation on a lathe or milling machine
- Table saw or band saw operation
- High-voltage work (>50 V or mains/AC power)
- Chemical etching (PCB fabrication, anodizing, acid)
- Angle grinder, plasma cutter, or welding

The following operations do NOT require steward sign-off
(`requires_steward_signoff: false`, `safety_level: normal`):
- 5 V breadboard prototyping or low-voltage (<50 V DC) wiring
- 3D print post-processing (sanding, support removal)
- Hand sanding or filing
- Soldering through-hole or SMD components at a bench station
- Programming / firmware flashing

When in doubt about a tool, default to `requires_steward_signoff: true`.

## Output Requirements
- Number steps starting at 1.
- Keep `instructions` concise and actionable (2–5 sentences).
- In the BOM, list only physical parts/materials; omit software or firmware.
- Set `source_status` to `in_stock_on_campus` only when you are confident the part
  is commonly stocked at HMC (e.g., standard resistors, M3 hardware, PLA filament).
  Otherwise use `external_purchase_needed`.
- If a BOM item is associated with a specific campus facility, set `facility` accordingly.
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GeminiService:
    """Wrapper around the Google Gemini API with explicit-trigger semantics.

    The client is never created at module import time.  Pass `client=` in the
    constructor to inject a mock for unit tests without touching the network.
    """

    MODEL = "gemini-2.0-flash"

    def __init__(self, client=None):
        # A pre-built client (real or mock) can be injected for testing.
        # None means "create lazily on first call".
        self._client = client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return the underlying Gemini client, creating it lazily if needed."""
        if self._client is not None:
            return self._client

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigurationError(
                "GEMINI_API_KEY is not set or empty. "
                "Configure this environment variable to enable LLM features."
            )

        # Import deferred so that missing google-genai at import time does not
        # crash the process; the dependency is optional until this code path is hit.
        from google import genai  # type: ignore[import]

        return genai.Client(api_key=api_key)

    @staticmethod
    def _wrap_sdk_error(exc: Exception) -> GeminiServiceError:
        """Convert a raw SDK / network exception into our typed hierarchy."""
        msg = str(exc)
        low = msg.lower()

        # 429 / quota exhausted
        if "429" in msg or "quota" in low or "rate" in low or "exhausted" in low:
            return GeminiRateLimitError(f"Gemini API rate limit exceeded: {exc}")

        # Connectivity / timeout
        if (
            "timeout" in low
            or "timed out" in low
            or "connection" in low
            or "network" in low
            or "deadline" in low
            or "unavailable" in low
        ):
            return GeminiNetworkError(f"Gemini API network error: {exc}")

        return GeminiServiceError(f"Unexpected Gemini API error: {exc}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_project_plan(
        self, title: str, description: str
    ) -> GeminiProjectPlanOutput:
        """Generate a structured fabrication plan for a student project.

        Raises:
            GeminiConfigurationError: API key missing.
            GeminiNetworkError: Connectivity or timeout failure.
            GeminiRateLimitError: Quota / 429 from Google.
            GeminiServiceError: Any other upstream error.
        """
        from google.genai import types  # type: ignore[import]

        client = self._get_client()

        prompt = (
            f"Project title: {title}\n\n"
            f"Project description:\n{description}\n\n"
            "Generate a complete fabrication plan following the system instructions. "
            "Return a structured JSON object matching the required schema exactly."
        )

        try:
            response = client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=GeminiProjectPlanOutput,
                ),
            )
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise self._wrap_sdk_error(exc) from exc

        try:
            return GeminiProjectPlanOutput.model_validate_json(response.text)
        except Exception as exc:
            raise GeminiServiceError(
                f"Failed to parse Gemini structured output: {exc}"
            ) from exc

    def project_chat(
        self,
        title: str,
        description: str,
        steps: list,
        history: list[dict],
        user_message: str,
    ) -> str:
        """Answer a follow-up question about a student's fabrication project.

        Args:
            title: Project title.
            description: Project description.
            steps: List of ProjectStep domain objects (used for context).
            history: Prior conversation turns as list of {"role": ..., "content": ...}
                     dicts (OpenAI-compatible format).
            user_message: The student's latest question.

        Returns:
            Plain-text reply from Gemini.

        Raises:
            GeminiConfigurationError / GeminiNetworkError / GeminiRateLimitError /
            GeminiServiceError: same contract as generate_project_plan.
        """
        from google.genai import types  # type: ignore[import]

        client = self._get_client()

        # Build a concise project context preamble
        steps_text = ""
        if steps:
            lines = []
            for s in steps:
                signoff = " [STEWARD SIGN-OFF REQUIRED]" if s.requires_steward_signoff else ""
                lines.append(
                    f"  Step {s.step_order}: {s.title} ({s.subsystem}){signoff}\n"
                    f"    {s.instructions[:200]}"
                )
            steps_text = "\n".join(lines)

        system_with_context = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"## Current Project Context\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Steps:\n{steps_text or '(no steps generated yet)'}\n"
        )

        # Convert history dicts → google-genai Content objects
        contents: list = []
        for turn in history:
            role = turn.get("role", "user")
            content_text = turn.get("content", "")
            if role in ("user", "model"):
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=content_text)],
                    )
                )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            )
        )

        try:
            response = client.models.generate_content(
                model=self.MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_with_context,
                ),
            )
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise self._wrap_sdk_error(exc) from exc

        return response.text
