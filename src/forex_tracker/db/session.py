"""SQLite engine/session management for the scraped rate history.

Timezone note (worth knowing before touching any datetime query in this
codebase): SQLite has no native timezone-aware datetime type. SQLAlchemy's
default SQLite dialect silently stores a tz-aware `datetime` as a naive
one and returns it naive on read — verified empirically against this
project's own schema, not assumed. Every datetime this project ever writes
is UTC, so the naive value read back is still correct *as long as it's
never compared against another aware datetime in pure Python*. Comparisons
belong inside a SQLModel `.where(...)` clause (compiled to SQL, where this
doesn't bite) rather than as a Python `if row.scraped_at > some_aware_dt`
expression, which would raise `TypeError: can't compare offset-naive and
offset-aware datetimes`.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger(__name__)

#: Overridable via the FOREX_TRACKER_DB_PATH env var (tests do this to get
#: an isolated database per test rather than sharing the dev one).
DEFAULT_DB_PATH = Path("data/forex_tracker.db")


def _db_url() -> str:
    db_path = Path(os.environ.get("FOREX_TRACKER_DB_PATH", DEFAULT_DB_PATH))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def _rebuild_stale_tables(engine: Engine) -> None:
    """Drop and recreate any table whose on-disk columns don't match the model.

    This project has no migration tooling (Alembic et al. — see the
    README's Design decisions), because `SQLModel.metadata.create_all()`
    only creates *missing* tables; it never alters an existing one to
    match a changed model. That's exactly what broke the scheduled
    GitHub Actions run: `data/forex_tracker.db` had been committed under
    an older schema (a single `rate` column, before `buy_rate`/
    `sell_rate` existed), and every later query against the new model
    failed with `OperationalError: no such column: exchangerate.buy_rate`
    — the stale table just sat there, untouched by create_all(), forever.

    The fix here is deliberately blunt rather than a real migration: if a
    table's actual columns don't match what the current model expects,
    drop it and let `create_all()` rebuild it fresh, logging a warning so
    the data loss is visible rather than silent. That's an acceptable
    tradeoff *for this project specifically* — forex.pk is the real
    source of truth, every row is re-derivable by scraping it again, and
    a 90-day cache (see RETENTION_DAYS) was never meant to be a permanent
    record. It would be the wrong call for data that isn't recoverable
    from elsewhere.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in SQLModel.metadata.tables.values():
        if table.name not in existing_tables:
            continue  # doesn't exist yet; create_all() below will make it

        actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
        expected_columns = {col.name for col in table.columns}
        if actual_columns != expected_columns:
            logger.warning(
                "Table %r has an outdated schema (found columns %s, expected %s) — "
                "dropping and recreating it. Any rows it held are lost; forex.pk "
                "will be re-scraped to repopulate history going forward.",
                table.name,
                sorted(actual_columns),
                sorted(expected_columns),
            )
            table.drop(engine)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating tables on first use.

    Memoized because an `Engine` owns a connection pool — constructing one
    per call would open/close a fresh SQLite file handle on every query for
    no benefit, since a single engine is meant to be shared and is already
    thread-safe for this project's usage pattern (short-lived sessions).
    """
    engine = create_engine(_db_url(), echo=False)
    _rebuild_stale_tables(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """Return a new session bound to the (lazily created) SQLite engine.

    Note: `get_engine` is memoized by `lru_cache`, so changing
    `FOREX_TRACKER_DB_PATH` mid-process (as tests do) requires calling
    `get_engine.cache_clear()` first — otherwise you'd get a session bound
    to whichever database was created first in the process.
    """
    return Session(get_engine())
