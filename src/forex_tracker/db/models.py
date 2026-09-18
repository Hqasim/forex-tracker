"""Persistence model for scraped open-market rate history.

`SQLModel` is used (rather than plain SQLAlchemy + a separate Pydantic
schema) because this one class serves double duty: it's both the ORM
model `SQLModelPipeline` writes rows with, and — since it's also a
Pydantic model — the schema FastAPI serializes straight out of `api/main.py`
without a hand-written response DTO to keep in sync.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel


class ExchangeRate(SQLModel, table=True):
    """A foreign currency's PKR buy/sell rate, as recorded during one scrape run."""

    id: int | None = Field(default=None, primary_key=True)
    #: ISO 4217 code of the foreign currency, e.g. "USD". Indexed since
    #: every read query (API, chart) filters or groups by this column.
    currency: str = Field(index=True)
    #: PKR paid to you per unit of `currency` (see ExchangeRateItem for the
    #: full buying/selling explanation). `Decimal`, not `float`: this is
    #: financial data, and binary floating point can't represent most
    #: decimal fractions exactly — `float("278.3")` is already a tiny bit
    #: off internally, and that error compounds if ever aggregated.
    buy_rate: Decimal = Field(max_digits=18, decimal_places=6)
    #: PKR you pay per unit of `currency`. Always >= buy_rate; enforced by
    #: ValidationPipeline before a row ever reaches this table.
    sell_rate: Decimal = Field(max_digits=18, decimal_places=6)
    source: str
    source_updated_at: str | None = None
    #: When the scrape that produced this row ran (UTC). Indexed: both the
    #: API's history endpoint and RetentionPipeline's prune query filter on
    #: it, and the chart module orders by it.
    scraped_at: datetime = Field(index=True)
    #: When this specific row was written to the database — distinct from
    #: `scraped_at` in principle (a retried write could lag the scrape),
    #: identical in practice today since SQLModelPipeline commits inline.
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
