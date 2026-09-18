"""Read-only API serving the scraped exchange rate history."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from sqlmodel import select

from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session

app = FastAPI(
    title="Forex Tracker API",
    description="Serves USD exchange rate history scraped from forex.pk.",
    version="0.2.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/rates/latest")
def latest_rates() -> list[ExchangeRate]:
    """The most recently scraped rate for every tracked currency."""
    with get_session() as session:
        rows = session.exec(select(ExchangeRate)).all()

    latest: dict[str, ExchangeRate] = {}
    for row in rows:
        current = latest.get(row.currency)
        if current is None or row.scraped_at > current.scraped_at:
            latest[row.currency] = row
    return sorted(latest.values(), key=lambda r: r.currency)


@app.get("/rates/history")
def rate_history(
    currency: str,
    limit: int = Query(default=30, ge=1, le=500),
) -> list[ExchangeRate]:
    """Chronological rate history for one currency, most recent `limit` points."""
    currency = currency.upper()
    with get_session() as session:
        rows = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency)
            .order_by(ExchangeRate.scraped_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for currency {currency!r}")
    return list(reversed(rows))
