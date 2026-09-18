"""Tests for per-currency chart rendering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from forex_tracker.analysis import plot_all_currency_trends, plot_currency_trend
from forex_tracker.constants import TRACKED_CURRENCIES
from forex_tracker.db import session as db_session
from forex_tracker.db.models import ExchangeRate


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FOREX_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    db_session.get_engine.cache_clear()
    yield
    db_session.get_engine.cache_clear()


def _seed(currency: str, days_ago: int) -> None:
    with db_session.get_session() as session:
        session.add(
            ExchangeRate(
                currency=currency,
                buy_rate=Decimal("278.00"),
                sell_rate=Decimal("278.30"),
                source="forex.pk",
                scraped_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        session.commit()


def test_plot_currency_trend_writes_a_file(isolated_db, tmp_path) -> None:
    _seed("USD", days_ago=1)
    output = tmp_path / "usd_trend.png"

    plot_currency_trend("USD", output)

    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_currency_trend_raises_without_history(isolated_db, tmp_path) -> None:
    with pytest.raises(ValueError, match="No stored history"):
        plot_currency_trend("USD", tmp_path / "usd_trend.png")


def test_plot_all_currency_trends_skips_currencies_without_history(isolated_db, tmp_path) -> None:
    _seed("USD", days_ago=1)
    _seed("EUR", days_ago=1)

    written = plot_all_currency_trends(tmp_path)

    written_names = {path.name for path in written}
    assert written_names == {"usd_trend.png", "eur_trend.png"}
    for currency in TRACKED_CURRENCIES:
        if currency not in {"USD", "EUR"}:
            assert not (tmp_path / f"{currency.lower()}_trend.png").exists()
