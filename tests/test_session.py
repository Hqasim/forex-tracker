"""Tests for schema-drift recovery in the SQLite engine/session layer.

Reproduces the exact failure this project hit for real: a `.db` file
committed under an older model version (a single `rate` column, before
`buy_rate`/`sell_rate` existed) made the scheduled GitHub Actions workflow
fail with `OperationalError: no such column: exchangerate.buy_rate`,
because `SQLModel.metadata.create_all()` never alters an existing table.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlmodel import select

from forex_tracker.db import session as db_session
from forex_tracker.db.models import ExchangeRate


@pytest.fixture
def isolated_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FOREX_TRACKER_DB_PATH", str(db_path))
    db_session.get_engine.cache_clear()
    yield db_path
    db_session.get_engine.cache_clear()


def test_get_session_rebuilds_a_table_with_an_outdated_schema(isolated_db_path) -> None:
    # Simulate a database committed under the pre-buy/sell-rate schema,
    # entirely independent of SQLModel so this genuinely represents "an old
    # file on disk", not something the current model could produce itself.
    conn = sqlite3.connect(isolated_db_path)
    conn.execute("CREATE TABLE exchangerate (id INTEGER PRIMARY KEY, currency TEXT, rate TEXT)")
    conn.execute("INSERT INTO exchangerate (currency, rate) VALUES ('USD', '278')")
    conn.commit()
    conn.close()

    # Querying through the current model must not raise OperationalError.
    with db_session.get_session() as session:
        rows = session.exec(select(ExchangeRate)).all()

    # The stale row is gone (it belonged to a schema that no longer
    # exists), but the table now has the current, queryable schema.
    assert rows == []


def test_get_session_leaves_a_current_schema_table_untouched(isolated_db_path) -> None:
    with db_session.get_session() as session:
        session.add(
            ExchangeRate(
                currency="USD",
                buy_rate=Decimal("278"),
                sell_rate=Decimal("278.3"),
                source="forex.pk",
                scraped_at=datetime.now(UTC),
            )
        )
        session.commit()

    db_session.get_engine.cache_clear()

    with db_session.get_session() as session:
        rows = session.exec(select(ExchangeRate)).all()
    assert len(rows) == 1
    assert rows[0].currency == "USD"
