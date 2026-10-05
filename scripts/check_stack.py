"""Verify a real lookup in all three Grafana data sources and save evidence."""

import json
import os
import time
from pathlib import Path

import httpx


def eventually(check, seconds=90):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return check()
        except (AssertionError, httpx.HTTPError, KeyError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("Telemetry did not become available") from exc
            time.sleep(2)


def main():
    app_url = os.getenv("APP_URL", "http://localhost:8000")
    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    with httpx.Client(timeout=10) as app, httpx.Client(
        base_url=grafana_url, auth=("admin", os.getenv("GRAFANA_PASSWORD", "admin")), timeout=10
    ) as grafana:
        for url in ["http://localhost:13133", "http://localhost:3200/ready"]:
            eventually(lambda: app.get(url).raise_for_status())
        response = app.get(f"{app_url}/api/orders/standard-1002")
        assert response.status_code == 404, response.text
        trace_id = response.headers["x-trace-id"]

        def query(uid, path, params=None):
            r = grafana.get(f"/api/datasources/proxy/uid/{uid}/{path}", params=params)
            r.raise_for_status()
            return r.json()

        def metric():
            result = query("prometheus", "api/v1/query", {"query": 'http_server_requests_total{http_response_status_code="404",service_name="order-tracker"}'})
            assert any(float(x["value"][1]) >= 1 for x in result["data"]["result"])
            return result

        def logs():
            result = query("loki", "loki/api/v1/query_range", {"query": '{service_name="order-tracker"} | trace_id="' + trace_id + '"', "limit": 20})
            assert result["data"]["result"]
            return result

        def trace():
            result = query("tempo", f"api/traces/{trace_id}")
            assert result.get("batches") or result.get("resourceSpans")
            return result

        evidence = {"lookup": {"status": response.status_code, "body": response.json(), "trace_id": trace_id},
                    "metric": eventually(metric), "logs": eventually(logs), "trace": eventually(trace)}
        target = Path(os.getenv("EVIDENCE_PATH", ".runtime/stack-check.json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"Grafana: status=404, metric present, correlated log and trace {trace_id} present")
        print(f"Evidence: {target}")


if __name__ == "__main__":
    main()
