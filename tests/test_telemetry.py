import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import main
from app.telemetry import ROUTE, Telemetry


@pytest.fixture
def observed(tmp_path, monkeypatch):
    reader = InMemoryMetricReader()
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()
    telemetry = Telemetry([reader], [SimpleSpanProcessor(spans)], [SimpleLogRecordProcessor(logs)])
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "orders.db")
    monkeypatch.setattr(main, "make_telemetry", lambda: telemetry)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client, reader, spans, logs


@pytest.mark.parametrize("order_id,status", [("standard-1001", 200), ("standard-1002", 404), ("broken", 500)])
def test_lookup_signals_correlate_and_record_actual_status(observed, monkeypatch, order_id, status):
    client, reader, spans, logs = observed
    if status == 500:
        def broken_detail(row):
            raise ValueError("deliberate test failure")

        monkeypatch.setattr(main, "order_detail", broken_detail)
        order_id = "standard-1001"
    response = client.get(f"/api/orders/{order_id}")
    assert response.status_code == status
    metrics = [m for rm in reader.get_metrics_data().resource_metrics for sm in rm.scope_metrics for m in sm.metrics]
    counter = next(m for m in metrics if m.name == "http.server.requests")
    points = [p for p in counter.data.data_points if p.value == 1]
    assert len(points) == 1
    assert points[0].attributes == Telemetry.attributes(status)
    span, = spans.get_finished_spans()
    log, = logs.get_finished_logs()
    assert span.name == f"GET {ROUTE}"
    assert span.attributes["http.response.status_code"] == status
    assert log.log_record.trace_id == span.context.trace_id
    assert log.log_record.span_id == span.context.span_id
    assert log.log_record.attributes["http.response.status_code"] == status
    if status == 500:
        assert span.status.is_ok is False
        assert log.log_record.attributes["exception.type"] == "ValueError"
    else:
        assert response.headers["x-trace-id"] == f"{span.context.trace_id:032x}"


def test_health_is_not_counted_and_remote_trace_is_preserved(observed):
    client, _, spans, _ = observed
    client.get("/healthz")
    assert not spans.get_finished_spans()
    trace_id = "0123456789abcdef0123456789abcdef"
    client.get("/api/orders/standard-1001", headers={"traceparent": f"00-{trace_id}-0123456789abcdef-01"})
    assert f"{spans.get_finished_spans()[0].context.trace_id:032x}" == trace_id
