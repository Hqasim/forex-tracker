"""SQLite engine/session management for the scraped rate history."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_PATH = Path("data/forex_tracker.db")


def _db_url() -> str:
    db_path = Path(os.environ.get("FOREX_TRACKER_DB_PATH", DEFAULT_DB_PATH))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(_db_url(), echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """Return a new session bound to the (lazily created) SQLite engine.

    Note: `get_engine` is memoized by `lru_cache`, so changing
    `FOREX_TRACKER_DB_PATH` mid-process (as tests do) requires calling
    `get_engine.cache_clear()` first.
    """
    return Session(get_engine())
