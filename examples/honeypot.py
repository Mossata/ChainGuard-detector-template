"""Honeypot.is token API adapter. See README for mapping limitations."""
import re

import httpx
from schema import AddressContext, DetectionResult, EvidenceItem

HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"
# Deliberately limit this example to the project's concrete Ethereum support.
CHAIN_IDS = {"ethereum": 1}


def detect(context: AddressContext) -> DetectionResult:
    """Check an Ethereum token contract, not a wallet address."""
    if context.chain.lower() not in CHAIN_IDS:
        raise ValueError("This Honeypot example supports chain='ethereum' only")
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", context.address):
        raise ValueError("Expected an EVM token contract address")
    response = httpx.get(
        HONEYPOT_URL,
        params={"address": context.address, "chainID": CHAIN_IDS[context.chain.lower()]},
        timeout=30.0,
    )
    response.raise_for_status()
    return map_result(response.json())


def map_result(data: dict) -> DetectionResult:
    """Never interpret a risk score as a confidence probability."""
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Invalid Honeypot response")
    result = data.get("honeypotResult")
    if result is not None and not isinstance(result, dict):
        raise ValueError("Invalid honeypotResult")
    verdict = (result or {}).get("isHoneypot")
    if verdict is not None and type(verdict) is not bool:
        raise ValueError("isHoneypot must be a boolean")
    if verdict is True:
        description = "Honeypot.is reports this token is a honeypot."
        reason = result.get("honeypotReason")
        if isinstance(reason, str) and reason.strip():
            description += " " + reason
        label, risk_type = "scam", "honeypot"
    elif verdict is False:
        description = ("Honeypot.is reports this token is not a honeypot; "
                       "other scam types have not been ruled out.")
        label, risk_type = "insufficient_evidence", "unknown"
    else:
        description = "Honeypot.is did not supply a honeypot verdict."
        label, risk_type = "insufficient_evidence", "unknown"
    return DetectionResult(
        label=label, risk_type=risk_type, confidence=0.0,
        evidence=[EvidenceItem(description=description, weight=0.0)],
    )
