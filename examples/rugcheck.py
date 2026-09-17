"""RugCheck token API adapter with an explicit demonstration label policy."""
import re

import httpx
from schema import AddressContext, DetectionResult, EvidenceItem

RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens/{}/report"


def detect(context: AddressContext) -> DetectionResult:
    """Check a Solana token mint; never send an Ethereum wallet to this API."""
    if context.chain.lower() != "solana":
        raise ValueError("This RugCheck example requires chain='solana'")
    if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", context.address):
        raise ValueError("Expected a Solana token mint address")
    response = httpx.get(RUGCHECK_URL.format(context.address), timeout=30.0)
    response.raise_for_status()
    return map_result(response.json())


def map_result(data: dict) -> DetectionResult:
    """Map danger-level findings using local policy, not a provider scam verdict.

    Scores/severity are not confidence probabilities. Numeric confidence and
    evidence weights stay at zero because the provider does not supply them.
    """
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Invalid RugCheck response")
    risks = data.get("risks")
    if risks is None:
        return DetectionResult(
            label="insufficient_evidence", risk_type="unknown", confidence=0.0,
            evidence=[EvidenceItem(description="RugCheck supplied no risk findings field.", weight=0.0)],
        )
    if not isinstance(risks, list):
        raise ValueError("RugCheck risks must be a list")
    evidence = []
    danger = False
    for risk in risks:
        if not isinstance(risk, dict):
            raise ValueError("Invalid RugCheck risk item")
        name = risk.get("name")
        description = risk.get("description")
        level = risk.get("level", "unknown")
        if not isinstance(level, str) or not any(
            isinstance(value, str) and value.strip() for value in (name, description)
        ):
            raise ValueError("RugCheck risk needs a textual name or description")
        text = ": ".join(value for value in (name, description)
                         if isinstance(value, str) and value.strip())
        evidence.append(EvidenceItem(description=f"RugCheck [{level}]: {text}", weight=0.0))
        danger |= level.lower() == "danger"
    if danger:
        evidence.append(EvidenceItem(
            description="Example adapter policy maps a danger-level finding to scam; this is not a confirmed rug pull.",
            weight=0.0,
        ))
    if not evidence:
        evidence.append(EvidenceItem(
            description="RugCheck returned no risk findings; this alone does not establish that the token is safe.",
            weight=0.0,
        ))
    return DetectionResult(
        label="scam" if danger else "insufficient_evidence",
        risk_type="token_risk" if risks else "unknown",
        confidence=0.0, evidence=evidence,
    )
