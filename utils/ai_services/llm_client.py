# ABOUTME: Shared Gemini client wrapper for non-agentic AI surfaces that need guarded structured synthesis.
# ABOUTME: Keeps dashboard/runtime AI access centralized without pulling agentic or card-editor workflows into the same path.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from utils.ai_config import AI_DEFAULTS, GOOGLE_API_KEY

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeminiCallResult:
    """Structured result for shared Gemini calls so callers can observe failures."""

    ok: bool
    status: str
    model: str
    text: Optional[str] = None
    error_type: str = ""
    error_message: str = ""


def get_default_gemini_model() -> str:
    """Returns the default Gemini model configured for shared dashboard/runtime use."""
    return AI_DEFAULTS["gemini"]["model"]


def get_dashboard_brief_model_candidates() -> list[str]:
    """Returns the ordered Gemini model list for stable career dashboard brief synthesis."""
    return [
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite-preview",
    ]


def get_career_dashboard_model_candidates() -> list[str]:
    """Returns the ordered model list for the main career dashboard command-center synthesis."""
    candidates = [
        "gemini-3.1-pro-preview",
        AI_DEFAULTS["gemini"]["model"],
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite-preview",
    ]
    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def gemini_is_available() -> bool:
    """Returns whether the shared Gemini client can be constructed."""
    return bool(GOOGLE_API_KEY)


def get_gemini_client() -> Optional[Any]:
    """Builds a shared Gemini client when credentials are available."""
    if not GOOGLE_API_KEY:
        return None
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        return genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options=types.HttpOptions(api_version="v1beta"),
        )
    except Exception as exc:
        logger.debug("get_gemini_client error: %s", exc)
        return None


def generate_gemini_content(
    prompt: str,
    *,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    response_mime_type: Optional[str] = None,
) -> Optional[str]:
    """Runs a Gemini text request and returns plain response text on success."""
    result = generate_gemini_content_with_status(
        prompt,
        model_name=model_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type=response_mime_type,
    )
    return result.text if result.ok else None


def generate_gemini_content_with_status(
    prompt: str,
    *,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    response_mime_type: Optional[str] = None,
) -> GeminiCallResult:
    """Runs a Gemini text request and returns a structured status object."""
    resolved_model = model_name or get_default_gemini_model()
    client = get_gemini_client()
    if client is None:
        status = "missing_api_key" if not GOOGLE_API_KEY else "client_init_error"
        return GeminiCallResult(
            ok=False,
            status=status,
            model=resolved_model,
            error_type=status,
            error_message="Gemini client is not available.",
        )

    try:
        from google.genai import types as genai_types  # type: ignore

        config_kwargs = {
            "temperature": AI_DEFAULTS["gemini"]["temperature"] if temperature is None else temperature,
            "max_output_tokens": AI_DEFAULTS["gemini"]["max_output_tokens"] if max_output_tokens is None else max_output_tokens,
        }
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type

        response = client.models.generate_content(
            model=resolved_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
        text = getattr(response, "text", "") or ""
        normalized_text = text.strip() or None
        if not normalized_text:
            return GeminiCallResult(
                ok=False,
                status="empty_response",
                model=resolved_model,
                error_type="empty_response",
                error_message="Gemini returned an empty response body.",
            )
        return GeminiCallResult(
            ok=True,
            status="ok",
            model=resolved_model,
            text=normalized_text,
        )
    except Exception as exc:
        logger.debug("generate_gemini_content error: %s", exc)
        error_type = type(exc).__name__
        error_message = str(exc)
        status = "network_error"
        lowered = error_message.lower()
        if "api key" in lowered or "permission" in lowered or "unauthorized" in lowered:
            status = "auth_error"
        elif "429" in lowered or "resource_exhausted" in lowered:
            status = "quota_error"
        elif "400" in lowered or "invalid" in lowered:
            status = "request_error"
        return GeminiCallResult(
            ok=False,
            status=status,
            model=resolved_model,
            error_type=error_type,
            error_message=error_message,
        )
