import httpx
import pytest
from fastapi.testclient import TestClient

import app
from examples import honeypot, rugcheck
from schema import AddressContext, DetectionResult

EVM = AddressContext(address="0x" + "1" * 40, chain="ethereum")
SOL = AddressContext(address="So11111111111111111111111111111111111111112", chain="solana")


@pytest.mark.parametrize("payload,label", [
    ({"honeypotResult": {"isHoneypot": True}}, "scam"),
    ({"honeypotResult": {"isHoneypot": False}}, "insufficient_evidence"),
    ({"simulationSuccess": False}, "insufficient_evidence"),
    ({"simulationSuccess": False, "honeypotResult": {"isHoneypot": True}}, "scam"),
])
def test_honeypot_mapping(payload, label):
    result = honeypot.map_result(payload)
    assert result.label == label
    assert result.confidence == 0.0


@pytest.mark.parametrize("risks,label", [
    ([], "insufficient_evidence"),
    ([{"name": "Authority enabled", "level": "warn"}], "insufficient_evidence"),
    ([{"name": "Concentration", "description": "One holder", "level": "danger"}], "scam"),
])
def test_rugcheck_mapping(risks, label):
    result = rugcheck.map_result({"risks": risks, "score": 50000})
    assert result.label == label
    assert result.confidence == 0.0
    assert result.evidence


@pytest.mark.parametrize("module,payload", [
    (honeypot, []), (honeypot, {"error": "failed"}),
    (honeypot, {"honeypotResult": {"isHoneypot": "false"}}),
    (rugcheck, {"risks": {}}), (rugcheck, {"risks": [None]}),
])
def test_malformed_response(module, payload):
    with pytest.raises(ValueError):
        module.map_result(payload)


@pytest.mark.parametrize("module,context,payload", [
    (honeypot, EVM, {"honeypotResult": {"isHoneypot": True}}),
    (rugcheck, SOL, {"risks": [{"name": "Risk", "level": "danger"}]}),
])
def test_detect_through_wrapper(monkeypatch, module, context, payload):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(module.httpx, "get", get)
    monkeypatch.setattr(app, "detect", module.detect)
    monkeypatch.delenv("DETECTOR_API_KEY", raising=False)
    with TestClient(app.app) as client:
        response = client.post("/detect", json=context.model_dump())
    assert response.status_code == 200
    assert DetectionResult.model_validate(response.json()).label == "scam"
    assert calls[0][1]["timeout"] == 30.0
    if module is honeypot:
        assert calls[0][1]["params"] == {"address": EVM.address, "chainID": 1}
    else:
        assert SOL.address in calls[0][0]


@pytest.mark.parametrize("module,context", [(honeypot, SOL), (rugcheck, EVM)])
def test_wrong_chain_never_calls_upstream(monkeypatch, module, context):
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected network call")
    monkeypatch.setattr(module.httpx, "get", unexpected)
    with pytest.raises(ValueError):
        module.detect(context)


@pytest.mark.parametrize("module,context", [(honeypot, EVM), (rugcheck, SOL)])
@pytest.mark.parametrize("failure", ["timeout", "http", "json"])
def test_upstream_failure_is_500(monkeypatch, module, context, failure):
    def get(url, **kwargs):
        if failure == "timeout":
            raise httpx.ReadTimeout("upstream secret")
        return httpx.Response(429 if failure == "http" else 200,
                              text="not json", request=httpx.Request("GET", url))
    monkeypatch.setattr(module.httpx, "get", get)
    monkeypatch.setattr(app, "detect", module.detect)
    monkeypatch.delenv("DETECTOR_API_KEY", raising=False)
    with TestClient(app.app) as client:
        response = client.post("/detect", json=context.model_dump())
    assert response.status_code == 500
    assert "upstream secret" not in response.text
