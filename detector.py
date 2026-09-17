"""Implement your detector here; no ChainGuard installation is required."""
from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:
    """Call a package, CLI, or model and normalize its result here.

    Context can be partial. Missing data does not mean an address is safe.
    See examples/heuristic.py for a demonstration implementation.
    """
    return DetectionResult(
        label="insufficient_evidence", risk_type="unknown", confidence=0.0,
        evidence=[{"description": "No detector has been implemented.", "weight": 0.0}],
    )
