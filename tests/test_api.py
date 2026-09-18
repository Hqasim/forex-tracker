"""API tests against an isolated, per-test SQLite file."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from forex_tracker.db import session as db_session
from forex_tracker.db.models import ExchangeRate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FOREX_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    db_session.get_engine.cache_clear()

    with db_session.get_session() as session:
        session.add(
            ExchangeRate(
                currency="EUR",
                rate=Decimal("0.8659"),
                source="forex.pk",
                source_updated_at="Thu, Jun 11 2026, 19:58 GMT",
                scraped_at=datetime(2026, 6, 11, tzinfo=UTC),
            )
        )
        session.commit()

    from forex_tracker.api.main import app

    yield TestClient(app)
    db_session.get_engine.cache_clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_latest_rates(client: TestClient) -> None:
    response = client.get("/rates/latest")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["currency"] == "EUR"
    assert body[0]["rate"] == "0.865900"


def test_history_returns_stored_point(client: TestClient) -> None:
    response = client.get("/rates/history", params={"currency": "eur"})
    assert response.status_code == 200
    assert response.json()[0]["currency"] == "EUR"


def test_history_unknown_currency_returns_404(client: TestClient) -> None:
    response = client.get("/rates/history", params={"currency": "ZZZ"})
    assert response.status_code == 404
