"""Choose and run the detector used by the ChainGuard detector service.

The HTTP service in ``app.py`` calls :func:`detect` for each ``POST /detect``
request. Most users only need to implement :func:`detect_custom`; use the
optional ``llm`` mode only when you want this service to forward requests to
your own API Gateway/Lambda endpoint.

Configure the mode and any LLM connection details as environment variables on
the machine running this service. See the comments on :func:`detect_llm` for
the supported variable names.
"""
import os

import httpx

from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:
    """Dispatch one validated address context to the selected detector.

    ``DETECTOR_MODE`` selects which implementation handles the request:

    * ``custom`` (the default) runs :func:`detect_custom`. Choose this for
      Python code, a local model, or another detector you integrate here.
    * ``llm`` runs :func:`detect_llm`, which makes an HTTP request to the
      endpoint configured by ``LLM_DETECTOR_ENDPOINT``.

    Set the environment variable before starting the service, for example
    ``DETECTOR_MODE=custom`` or ``DETECTOR_MODE=llm``. The value is stripped
    of surrounding whitespace and is case-insensitive. Any other value raises
    ``RuntimeError`` rather than silently choosing a different detector.

    Args:
        context: The address and available analysis data supplied by the
            ChainGuard caller. See ``schema.AddressContext`` for its fields.

    Returns:
        A ``DetectionResult`` containing the detector's label, risk type,
        confidence, evidence, and optional explanation. The service checks
        this result against the shared schema before returning its response.
    """
    # Default to the custom implementation so a new installation never makes
    # an unexpected network call to an LLM endpoint.
    mode = os.environ.get("DETECTOR_MODE", "custom").strip().lower()
    if mode == "custom":
        return detect_custom(context)
    if mode == "llm":
        return detect_llm(context)
    raise RuntimeError("DETECTOR_MODE must be either 'custom' or 'llm'")


def detect_custom(context: AddressContext) -> DetectionResult:
    """Run your own detector without requiring the optional LLM adapter.

    This is the normal place to add your implementation. You can write
    heuristics directly here, call a local model, or import and call a detector
    from another module or installed package. The complete input is available
    as ``context``; for example, read ``context.address`` and
    ``context.tx_history`` or ``context.liquidity`` as appropriate for your
    detector.

    Return a ``DetectionResult`` (or a value that can be validated as one).
    Its required fields are ``label`` (``scam``, ``not_scam``, or
    ``insufficient_evidence``), ``risk_type``, ``confidence`` (from 0.0 to
    1.0), and ``evidence``. Each evidence item needs a non-empty ``description``
    and a ``weight`` from 0.0 to 1.0. ``explanation`` is optional. These rules
    come from ``schema.py``; invalid results make the service return an error.

    The return value below is only a safe starter placeholder. Replace it with
    your detector's actual logic before relying on this service for decisions.
    """
    # TODO: Replace this conservative placeholder with your detector.
    return DetectionResult(
        label="insufficient_evidence",
        risk_type="unknown",
        confidence=0.0,
        evidence=[],
    )


def detect_llm(context: AddressContext) -> DetectionResult:
    """Forward the input to a user-managed API Gateway/Lambda detector.

    Enable this function by setting ``DETECTOR_MODE=llm`` in the environment
    before starting the service. Configure:

    * ``LLM_DETECTOR_ENDPOINT`` (required): full URL to the endpoint that
      accepts a JSON ``AddressContext`` and returns a JSON ``DetectionResult``.
    * ``LLM_DETECTOR_API_KEY`` (optional): sent as an ``X-API-Key`` header when
      set. Keep this secret in the service environment; do not hard-code it or
      put it in the address context.
    * ``LLM_DETECTOR_TIMEOUT`` (optional): request timeout in seconds. Defaults
      to ``30``; it must be parseable as a number.

    The configured endpoint must return the schema described in
    ``schema.DetectionResult``. HTTP failures, invalid JSON, and responses that
    do not satisfy that schema are raised to the service, which reports the
    detection as failed rather than treating it as a successful result.

    Args:
        context: The same validated address context received by ``detect``.

    Returns:
        The endpoint's response validated as a ``DetectionResult``.
    """
    # Do not fall back to custom detection when LLM mode is requested but
    # misconfigured: failing clearly avoids presenting a placeholder as a real
    # LLM-backed result.
    endpoint = os.environ.get("LLM_DETECTOR_ENDPOINT")
    if not endpoint:
        raise RuntimeError("LLM_DETECTOR_ENDPOINT is not configured")

    # The endpoint receives only this adapter's API key header when one is
    # configured; authentication for the service's own /detect route is separate.
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("LLM_DETECTOR_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    # Serialize the Pydantic input model to ordinary JSON-compatible values.
    # ``raise_for_status`` below makes non-2xx responses explicit failures.
    response = httpx.post(
        endpoint,
        json=context.model_dump(mode="json"),
        headers=headers,
        timeout=float(os.environ.get("LLM_DETECTOR_TIMEOUT", "30")),
    )
    response.raise_for_status()
    # Validate the remote response against the same contract used by custom
    # detectors, so both modes return a consistent result to the caller.
    return DetectionResult.model_validate(response.json())
