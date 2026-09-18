"""Tests for pruning rate history outside the retention window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel import select

from forex_tracker.constants import RETENTION_DAYS
from forex_tracker.db import session as db_session
from forex_tracker.db.models import ExchangeRate
from forex_tracker.scraper.pipelines import RetentionPipeline


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FOREX_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    db_session.get_engine.cache_clear()
    yield
    db_session.get_engine.cache_clear()


def _add(*, currency: str, scraped_at: datetime) -> None:
    with db_session.get_session() as session:
        session.add(
            ExchangeRate(
                currency=currency,
                buy_rate=Decimal("278"),
                sell_rate=Decimal("278.3"),
                source="forex.pk",
                scraped_at=scraped_at,
            )
        )
        session.commit()


def test_prunes_rows_older_than_retention_window(isolated_db) -> None:
    now = datetime.now(UTC)
    _add(currency="USD", scraped_at=now - timedelta(days=RETENTION_DAYS + 1))
    _add(currency="USD", scraped_at=now - timedelta(days=1))

    RetentionPipeline().close_spider()

    with db_session.get_session() as session:
        remaining = session.exec(select(ExchangeRate)).all()
    assert len(remaining) == 1
    # SQLite round-trips datetimes as naive (UTC-valued) rather than aware.
    cutoff_naive = (now - timedelta(days=RETENTION_DAYS)).replace(tzinfo=None)
    assert remaining[0].scraped_at > cutoff_naive


def test_keeps_rows_within_retention_window(isolated_db) -> None:
    now = datetime.now(UTC)
    _add(currency="USD", scraped_at=now - timedelta(days=RETENTION_DAYS - 1))

    RetentionPipeline().close_spider()

    with db_session.get_session() as session:
        remaining = session.exec(select(ExchangeRate)).all()
    assert len(remaining) == 1
