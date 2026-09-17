"""Standalone wire contract based on SPEC.md sections 5.3 and 5.6.
Coordinate contract changes with the consuming ChainGuard application.
"""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class FetcherProvenance(BaseModel):
    fields: list[str] = Field(default_factory=list)
    fetched_at: str | None = None
    status: str = "skip"
    error: str | None = None


class AddressContext(BaseModel):
    model_config = ConfigDict(strict=True)
    address: str = Field(min_length=1, pattern=r"\S")
    chain: str = Field(default="ethereum", min_length=1, pattern=r"\S")
    queried_at: str | None = None
    address_analysis: dict[str, Any] = Field(default_factory=dict)
    contract: dict[str, Any] = Field(default_factory=dict)
    tx_history: list[dict[str, Any]] = Field(default_factory=list)
    tokens: list[dict[str, Any]] = Field(default_factory=list)
    liquidity: list[dict[str, Any]] = Field(default_factory=list)
    fetcher_provenance: dict[str, FetcherProvenance] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")
    description: str = Field(min_length=1, pattern=r"\S")
    weight: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")
    label: Literal["scam", "not_scam", "insufficient_evidence"]
    risk_type: str = Field(min_length=1, pattern=r"\S")
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[EvidenceItem]
    explanation: str | None = None
