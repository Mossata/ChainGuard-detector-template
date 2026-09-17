"""Demonstration only: this is not a validated scam detection model."""
from schema import AddressContext, DetectionResult, EvidenceItem


def detect(context: AddressContext) -> DetectionResult:
    unverified = (context.contract.get("is_contract") is True
                  and context.contract.get("verified_source") is False)
    empty_pool = any(
        pool.get("liquidity_usd") == 0
        and any(isinstance(event, dict) and event.get("type") == "remove"
                for event in pool.get("liquidity_events", []) or [])
        for pool in context.liquidity
    )
    if unverified and empty_pool:
        return DetectionResult(
            label="scam", risk_type="rug_pull", confidence=0.6,
            evidence=[
                EvidenceItem(description="Contract source is explicitly unverified", weight=0.4),
                EvidenceItem(description="A pool has zero liquidity and a recorded removal event", weight=0.7),
            ],
        )
    return DetectionResult(label="insufficient_evidence", risk_type="unknown",
                           confidence=0.0, evidence=[])
