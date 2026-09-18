"""Persistence model for scraped exchange rate history."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel


class ExchangeRate(SQLModel, table=True):
    """One currency's rate as recorded during a single scrape run."""

    id: int | None = Field(default=None, primary_key=True)
    currency: str = Field(index=True)
    rate: Decimal = Field(max_digits=18, decimal_places=6)
    source: str
    source_updated_at: str | None = None
    scraped_at: datetime = Field(index=True)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
