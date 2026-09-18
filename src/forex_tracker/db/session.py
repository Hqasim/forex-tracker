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

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

#: Overridable via the FOREX_TRACKER_DB_PATH env var (tests do this to get
#: an isolated database per test rather than sharing the dev one).
DEFAULT_DB_PATH = Path("data/forex_tracker.db")


def _db_url() -> str:
    db_path = Path(os.environ.get("FOREX_TRACKER_DB_PATH", DEFAULT_DB_PATH))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating tables on first use.

    Memoized because an `Engine` owns a connection pool — constructing one
    per call would open/close a fresh SQLite file handle on every query for
    no benefit, since a single engine is meant to be shared and is already
    thread-safe for this project's usage pattern (short-lived sessions).
    """
    engine = create_engine(_db_url(), echo=False)
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
