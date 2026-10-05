import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "orders.db")
    monkeypatch.setenv("TELEMETRY_EXPORTER", "none")
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "created_at,expected_delivery",
    [
        ("2026-09-30T18:00:00+00:00", "2026-10-02"),
        ("2026-01-30T18:00:00+00:00", "2026-02-01"),
        ("2026-12-31T18:00:00+00:00", "2027-01-02"),
        ("2026-02-28T18:00:00+00:00", "2026-03-02"),
        ("2024-02-28T18:00:00+00:00", "2024-03-01"),
        ("2024-02-27T18:00:00+00:00", "2024-02-29"),
        ("2026-10-05T18:00:00+00:00", "2026-10-07"),
    ],
)
def test_express_lookup_delivery_date(client, created_at, expected_delivery):
    with main.connect() as db:
        db.execute(
            "UPDATE orders SET created_at = ? WHERE id = ?",
            (created_at, "express-1002"),
        )

    response = client.get("/api/orders/express-1002")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "express-1002",
        "customer": "Sam",
        "item": "Headphones",
        "priority": "express",
        "status": "preparing",
        "created_at": created_at,
        "estimated_delivery": expected_delivery,
    }


def test_standard_lookup_has_no_delivery_estimate(client):
    response = client.get("/api/orders/standard-1001")

    assert response.status_code == 200
    assert "estimated_delivery" not in response.json()
