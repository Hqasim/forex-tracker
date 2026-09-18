"""API tests against an isolated, per-test SQLite file."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from forex_tracker.db import session as db_session
from forex_tracker.db.models import ExchangeRate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FOREX_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    db_session.get_engine.cache_clear()

    now = datetime.now(UTC)
    with db_session.get_session() as session:
        session.add(
            ExchangeRate(
                currency="EUR",
                buy_rate=Decimal("318.94"),
                sell_rate=Decimal("323.95"),
                source="forex.pk",
                source_updated_at="Fri, Sep 18 2026, 22:13 PST (GMT+5)",
                scraped_at=now,
            )
        )
        session.add(
            ExchangeRate(
                currency="EUR",
                buy_rate=Decimal("310.00"),
                sell_rate=Decimal("315.00"),
                source="forex.pk",
                source_updated_at="stale",
                scraped_at=now - timedelta(days=120),
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
    assert body[0]["buy_rate"] == "318.940000"
    assert body[0]["sell_rate"] == "323.950000"


def test_history_returns_recent_point_only(client: TestClient) -> None:
    response = client.get("/rates/history", params={"currency": "eur"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source_updated_at"] != "stale"


def test_history_unknown_currency_returns_404(client: TestClient) -> None:
    response = client.get("/rates/history", params={"currency": "ZZZ"})
    assert response.status_code == 404
