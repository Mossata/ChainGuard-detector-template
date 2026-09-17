import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as wrapper
from examples.heuristic import detect as heuristic
from schema import AddressContext


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DETECTOR_API_KEY", raising=False)
    with TestClient(wrapper.app) as client:
        yield client


def test_standalone_stub_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    result = client.post("/detect", json={"address": "0x123", "chain": "ethereum"})
    assert result.status_code == 200
    assert result.json()["label"] == "insufficient_evidence"
    assert "explanation" not in result.json()
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {"/detect", "/health"}


@pytest.mark.parametrize("body", [{}, {"address": " "}, {"address": 123},
                                   {"address": "0x123", "tx_history": {}}])
def test_invalid_input(client, body):
    assert client.post("/detect", json=body).status_code == 422


def test_auth(client, monkeypatch):
    monkeypatch.setenv("DETECTOR_API_KEY", "test-secret")
    for headers in [{}, {"X-API-Key": "wrong"}]:
        assert client.post("/detect", json={"address": "0x123"}, headers=headers).status_code == 401
    assert client.post("/detect", json={"address": "0x123"},
                       headers={"X-API-Key": "test-secret"}).status_code == 200


@pytest.mark.parametrize("field,value", [("label", "CLEAN"), ("confidence", 2.0),
                                         ("confidence", float("nan")),
                                         ("evidence", [{"description": "reason", "weight": -1.0}])])
def test_invalid_output(client, monkeypatch, field, value):
    result = {"label": "not_scam", "risk_type": "unknown", "confidence": 0.5, "evidence": []}
    result[field] = value
    monkeypatch.setattr(wrapper, "detect", lambda context: result)
    assert client.post("/detect", json={"address": "0x123"}).status_code == 500


def test_failure_does_not_leak_details(client, monkeypatch):
    def fail(context):
        raise RuntimeError("private-detail")
    monkeypatch.setattr(wrapper, "detect", fail)
    response = client.post("/detect", json={"address": "0x123"})
    assert response.status_code == 500
    assert "private-detail" not in response.text


def test_example_through_api(client, monkeypatch):
    monkeypatch.setattr(wrapper, "detect", heuristic)
    context = json.loads((Path(__file__).parents[1] / "examples/context.json").read_text())
    response = client.post("/detect", json=context)
    assert response.status_code == 200
    assert response.json()["label"] == "scam"
    assert len(response.json()["evidence"]) == 2
    assert heuristic(AddressContext(address="0x123")).label == "insufficient_evidence"


def test_explanation(client, monkeypatch):
    monkeypatch.setattr(wrapper, "detect", lambda context: {
        "label": "insufficient_evidence", "risk_type": "unknown", "confidence": 0.0,
        "evidence": [], "explanation": "No usable observations supplied.",
    })
    assert client.post("/detect", json={"address": "0x123"}).json()["explanation"]
