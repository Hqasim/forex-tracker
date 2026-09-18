"""Item pipelines: validate scraped rates, then persist them to SQLite."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session

ALLOWED_CURRENCIES = {"CNY", "EUR", "JPY", "PKR", "SAR", "AED", "GBP"}


class ValidationPipeline:
    """Drops items with an unknown currency code or a non-positive/non-numeric rate.

    Runs before persistence so a malformed page never silently corrupts the
    stored history.
    """

    def process_item(self, item: Any) -> Any:
        adapter = ItemAdapter(item)
        currency = adapter.get("currency")

        if currency not in ALLOWED_CURRENCIES:
            raise DropItem(f"Unexpected currency code: {currency!r}")

        try:
            rate_value = Decimal(str(adapter.get("rate")))
        except (InvalidOperation, TypeError):
            raise DropItem(f"Non-numeric rate for {currency}: {adapter.get('rate')!r}") from None

        if rate_value <= 0:
            raise DropItem(f"Non-positive rate for {currency}: {rate_value}")

        return item


class SQLModelPipeline:
    """Persists validated items into the SQLite-backed rate history table."""

    def open_spider(self) -> None:
        self.session = get_session()

    def close_spider(self) -> None:
        self.session.close()

    def process_item(self, item: Any) -> Any:
        adapter = ItemAdapter(item)
        record = ExchangeRate(
            currency=adapter["currency"],
            rate=Decimal(str(adapter["rate"])),
            source=adapter["source"],
            source_updated_at=adapter.get("source_updated_at"),
            scraped_at=datetime.fromisoformat(adapter["scraped_at"]),
        )
        self.session.add(record)
        self.session.commit()
        return item
