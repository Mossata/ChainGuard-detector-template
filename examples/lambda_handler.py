"""Minimal API Gateway/Lambda endpoint for a user-owned LLM detector.

Replace invoke_user_llm() with the user's model call. The returned object must
match DetectionResult so the wrapper can validate it unchanged.
"""
import json
from typing import Any


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Accept an AddressContext JSON body and return a DetectionResult."""
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        return _response(400, {"error": "Request body must be a JSON object"})

    try:
        result = invoke_user_llm(body)
    except Exception:
        return _response(500, {"error": "LLM detector failed"})
    return _response(200, result)


def invoke_user_llm(context: dict[str, Any]) -> dict[str, Any]:
    """Call the user's LLM and map its output to the shared result contract."""
    raise NotImplementedError("Connect this function to your LLM")


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }