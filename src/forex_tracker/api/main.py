"""Read-only API serving the scraped open-market rate history.

Run locally with `forex-tracker serve` (see `cli.py`), then visit
http://127.0.0.1:8000/docs for FastAPI's interactive Swagger UI — every
`summary`/`description`/`Query(description=...)` below feeds directly
into that page, so the docs a consumer sees are generated from this file
rather than maintained separately.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from sqlmodel import select

from forex_tracker.constants import RETENTION_DAYS, TRACKED_CURRENCIES
from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session

app = FastAPI(
    title="Forex Tracker API",
    description=(
        "Read-only history of Pakistan's open-market currency rates "
        f"({', '.join(TRACKED_CURRENCIES)} against PKR), scraped from "
        "forex.pk. Every rate carries both a buying and a selling quote — "
        "see /rates/latest and /rates/history below."
    ),
    version="0.3.0",
)


@app.get("/health", summary="Liveness check", tags=["meta"])
def health() -> dict[str, str]:
    """Returns 200 with a static body if the process is up.

    Deliberately does *not* touch the database — a slow/locked SQLite file
    should fail `/rates/*` requests, not this one, so a monitor can tell
    "the process is dead" apart from "the process is up but the DB is
    unhappy".
    """
    return {"status": "ok"}


@app.get(
    "/rates/latest",
    summary="Latest buy/sell rate per currency",
    tags=["rates"],
)
def latest_rates() -> list[ExchangeRate]:
    """The single most recent scraped row for every tracked currency.

    Example:
        GET /rates/latest ->
        [
          {"currency": "CNY", "buy_rate": "38.250000", "sell_rate": "38.970000", ...},
          {"currency": "EUR", "buy_rate": "318.940000", "sell_rate": "323.950000", ...},
          ...
        ]

    Implementation note: this reduces in Python rather than a `GROUP BY`
    in SQL. At five currencies and a 90-day/daily-cadence retention window,
    the whole table is at most a few hundred rows — reading all of it and
    picking the max `scraped_at` per currency in Python is simpler than a
    correlated subquery or window function, and the cost difference is not
    measurable at this scale. A `SELECT ... GROUP BY currency` with a
    window function would be the right call if this table's row count
    were ever orders of magnitude larger.
    """
    with get_session() as session:
        rows = session.exec(select(ExchangeRate)).all()

    latest: dict[str, ExchangeRate] = {}
    for row in rows:
        current = latest.get(row.currency)
        if current is None or row.scraped_at > current.scraped_at:
            latest[row.currency] = row
    return sorted(latest.values(), key=lambda r: r.currency)


@app.get(
    "/rates/history",
    summary="Chronological buy/sell history for one currency",
    tags=["rates"],
)
def rate_history(
    currency: str = Query(
        ...,
        description=f"Currency code, one of: {', '.join(TRACKED_CURRENCIES)} (case-insensitive).",
        examples=["USD"],
    ),
    days: int = Query(
        default=RETENTION_DAYS,
        ge=1,
        le=RETENTION_DAYS,
        description=(
            "How many days of history to return, oldest-first. Capped at "
            f"{RETENTION_DAYS} since RetentionPipeline never keeps rows "
            "older than that — see the README's Data Retention section."
        ),
    ),
) -> list[ExchangeRate]:
    """Every stored row for `currency` from the last `days` days, oldest first.

    Example:
        GET /rates/history?currency=USD&days=30

    Returns 404 (not an empty list) when `currency` is valid but has no
    rows in the requested window — that distinction matters to a caller:
    "nothing happened to scrape yet" is a different situation from
    "you asked for a currency this API doesn't track".
    """
    currency = currency.upper()
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with get_session() as session:
        rows = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency, ExchangeRate.scraped_at >= cutoff)
            .order_by(ExchangeRate.scraped_at)  # type: ignore[arg-type]
        ).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for currency {currency!r}")
    return list(rows)
