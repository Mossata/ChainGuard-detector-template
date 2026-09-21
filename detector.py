"""Detector entry point supporting custom detectors and optional user LLMs."""
import os

import httpx

from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:
    """Run the configured detector mode.

    Custom detectors are the default. Set DETECTOR_MODE=llm only when this
    service should call the configured API Gateway/Lambda LLM.
    """
    mode = os.environ.get("DETECTOR_MODE", "custom").strip().lower()
    if mode == "custom":
        return detect_custom(context)
    if mode == "llm":
        return detect_llm(context)
    raise RuntimeError("DETECTOR_MODE must be either 'custom' or 'llm'")


def detect_custom(context: AddressContext) -> DetectionResult:
    """Implement a non-LLM detector here, or import one from your package.

    Replace this function body with custom heuristics, a local model, a CLI,
    or an external API adapter. Its output must match DetectionResult.
    """
    return DetectionResult(
        label="insufficient_evidence",
        risk_type="unknown",
        confidence=0.0,
        evidence=[],
    )


def detect_llm(context: AddressContext) -> DetectionResult:
    """Send the full context to an API Gateway/Lambda-backed LLM."""
    endpoint = os.environ.get("LLM_DETECTOR_ENDPOINT")
    if not endpoint:
        raise RuntimeError("LLM_DETECTOR_ENDPOINT is not configured")

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("LLM_DETECTOR_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    response = httpx.post(
        endpoint,
        json=context.model_dump(mode="json"),
        headers=headers,
        timeout=float(os.environ.get("LLM_DETECTOR_TIMEOUT", "30")),
    )
    response.raise_for_status()
    return DetectionResult.model_validate(response.json())
