"""Smoke-test the deployed API, including the incident's failing order."""

import json
import os
from datetime import datetime, timedelta

import httpx


def main():
    with httpx.Client(base_url=os.getenv("APP_URL", "http://localhost:8000"), timeout=10) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert "Order Tracker" in client.get("/").text
        assert client.get("/api/orders/standard-1001").status_code == 200
        assert client.get("/api/orders/standard-1002").status_code == 404
        for _ in range(10):
            response = client.get("/api/orders/express-1002")
            assert response.status_code == 200, response.text
            order = response.json()
            expected = (datetime.fromisoformat(order["created_at"]) + timedelta(days=2)).date().isoformat()
            assert order["estimated_delivery"] == expected
        print(json.dumps({"health": "ok", "standard": 200, "missing": 404, "express": 200,
                          "express_checks": 10, "estimated_delivery": expected}, indent=2))


if __name__ == "__main__":
    main()
