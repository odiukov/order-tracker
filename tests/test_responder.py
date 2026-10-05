import importlib.util
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location("responder", Path(__file__).parents[1] / "incident-response/responder.py")
responder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = responder
spec.loader.exec_module(responder)


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(responder, "INCIDENTS", tmp_path)
    calls = []
    monkeypatch.setattr(responder, "collect_evidence", lambda path: responder.save(path / "logs.json", {"evidence": "test"}))

    def agent(path, test):
        calls.append((path, test))
        (path / "response.txt").write_text("Test notification received. No action needed.\n")

    monkeypatch.setattr(responder, "run_agent", agent)
    with TestClient(responder.app) as client:
        yield client, tmp_path, calls


def notification(status="firing", **labels):
    return {"alerts": [{"status": status, "labels": {"alertname": "Test", **labels},
                        "annotations": {"summary": "Test notification"}}]}


def terminal_state(path):
    for _ in range(200):
        state = json.loads((path / "status.json").read_text())
        if state["state"] not in {"running", "queued"}:
            return state
        time.sleep(.01)
    pytest.fail("Worker did not finish")


def test_webhook_persists_evidence_runs_agent_and_deduplicates(service):
    client, root, calls = service
    body = notification(test="true")
    first = client.post("/alerts", json=body)
    assert first.status_code == 202
    incident = first.json()["incidents"][0]
    directory = root / incident["id"]
    assert terminal_state(directory)["state"] == "completed"
    assert json.loads((directory / "alert.json").read_text())["alerts"][0]["annotations"]["summary"] == "Test notification"
    assert (directory / "logs.json").exists()
    assert (directory / "response.txt").read_text().endswith("No action needed.\n")
    assert client.post("/alerts", json=body).json()["incidents"][0]["state"] == "duplicate"
    assert len(calls) == 1 and calls[0][1] is True


def test_resolved_and_invalid_notifications_do_not_launch_agent(service):
    client, root, calls = service
    assert client.post("/alerts", json=notification("resolved")).json()["incidents"] == [{"state": "ignored"}]
    assert client.post("/alerts", json={"alerts": []}).status_code == 422
    assert client.post("/alerts", content="not json").status_code == 422
    assert client.post("/alerts", content="x" * 262145).status_code == 413
    assert not list(root.iterdir()) and not calls


def test_failed_agent_is_recorded_and_not_retried_on_duplicate(service, monkeypatch):
    client, root, _ = service
    def fail(*_):
        raise RuntimeError("Agent unavailable")
    monkeypatch.setattr(responder, "run_agent", fail)
    body = notification()
    key = client.post("/alerts", json=body).json()["incidents"][0]["id"]
    assert terminal_state(root / key) == {"state": "failed", "test": False, "error": "Agent unavailable"}
    assert client.post("/alerts", json=body).json()["incidents"][0]["state"] == "duplicate"


def test_new_alert_episode_runs_again_and_dedup_survives_restart(service):
    client, root, calls = service
    first = notification()
    first["alerts"][0]["startsAt"] = "2026-10-05T10:00:00Z"
    key = client.post("/alerts", json=first).json()["incidents"][0]["id"]
    terminal_state(root / key)
    restarted = responder.Responder(root)
    try:
        assert restarted.accept(responder.Alert(**first["alerts"][0]), first)["state"] == "duplicate"
    finally:
        restarted.executor.shutdown()
    first["alerts"][0]["startsAt"] = "2026-10-05T11:00:00Z"
    key2 = client.post("/alerts", json=first).json()["incidents"][0]["id"]
    terminal_state(root / key2)
    assert key2 != key and len(calls) == 2


def test_restart_marks_unfinished_incident_interrupted(tmp_path):
    incident = tmp_path / "unfinished"
    incident.mkdir()
    responder.save(incident / "status.json", {"state": "running"})
    worker = responder.Responder(tmp_path)
    worker.executor.shutdown()
    assert json.loads((incident / "status.json").read_text())["state"] == "interrupted"


def test_collection_keeps_backend_failures_and_fetches_correlated_trace(tmp_path, monkeypatch):
    trace_id = "a" * 32
    seen = []
    def handle(request):
        seen.append(str(request.url))
        if request.url.port == 9090:
            return httpx.Response(503)
        if request.url.port == 3100:
            return httpx.Response(200, json={"data": {"result": [{"stream": {"trace_id": trace_id, "http_response_status_code": "500"}}]}})
        return httpx.Response(200, json={"batches": [{"trace": "evidence"}]})
    original = httpx.Client
    monkeypatch.setattr(responder.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    responder.collect_evidence(tmp_path)
    assert "collection_error" in json.loads((tmp_path / "metrics.json").read_text())
    assert (tmp_path / f"trace-{trace_id}.json").exists()
    assert any(f"/api/traces/{trace_id}" in url for url in seen)
