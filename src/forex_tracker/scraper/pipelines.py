"""Item pipelines: validate scraped rates, persist them, and prune history
outside the retention window.

Scrapy runs pipelines in ascending priority order (set in
`ITEM_PIPELINES`, `scraper/settings.py`): Validation (100) -> SQLModel
(300) -> Retention (400). That order is deliberate — a bad item must be
dropped *before* it's written, and pruning old rows only makes sense
*after* the new ones have landed.

Signature note: `open_spider`/`close_spider`/`process_item` below take no
`spider` argument. Scrapy tutorials predating ~2.19 show these methods as
`def process_item(self, item, spider)` — that form still runs, but now
raises a `ScrapyDeprecationWarning` on every call (Scrapy is phasing the
argument out in favour of `from_crawler()` for the rare pipeline that
actually needs the spider instance). None of these three do, so the
argument is dropped rather than kept-but-unused.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from sqlmodel import select

from forex_tracker.constants import RETENTION_DAYS, TRACKED_CURRENCIES
from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session


class ValidationPipeline:
    """Drops items that can't be trusted before they reach storage.

    Rejects an unknown currency code, a non-numeric or non-positive rate, or
    a selling rate below the buying rate (an impossible market spread) —
    any of which is far more likely to mean the page's structure shifted
    under us than that forex.pk is really quoting a currency we don't
    track or a negative price.
    """

    def process_item(self, item: Any) -> Any:
        adapter = ItemAdapter(item)
        currency = adapter.get("currency")

        if currency not in TRACKED_CURRENCIES:
            raise DropItem(f"Unexpected currency code: {currency!r}")

        try:
            buy_rate = Decimal(str(adapter.get("buy_rate")))
            sell_rate = Decimal(str(adapter.get("sell_rate")))
        except (InvalidOperation, TypeError):
            # `from None`: the DropItem message already states exactly what
            # was wrong, so re-raising with the original Decimal traceback
            # chained on would just be noise in the Scrapy log.
            raise DropItem(
                f"Non-numeric rate for {currency}: "
                f"buy={adapter.get('buy_rate')!r} sell={adapter.get('sell_rate')!r}"
            ) from None

        if buy_rate <= 0 or sell_rate <= 0:
            raise DropItem(f"Non-positive rate for {currency}: buy={buy_rate} sell={sell_rate}")
        if sell_rate < buy_rate:
            raise DropItem(
                f"Selling rate below buying rate for {currency}: buy={buy_rate} sell={sell_rate}"
            )

        return item


class SQLModelPipeline:
    """Persists validated items into the SQLite-backed rate history table.

    One `Session` is opened per crawl (`open_spider`) and reused for every
    item rather than opened-and-closed per row, which would otherwise mean
    one SQLite transaction per currency per run for no benefit — five
    currencies is nothing, but the pattern matters more once a source has
    dozens of rows per page.
    """

    def open_spider(self) -> None:
        self.session = get_session()

    def close_spider(self) -> None:
        self.session.close()

    def process_item(self, item: Any) -> Any:
        adapter = ItemAdapter(item)
        record = ExchangeRate(
            currency=adapter["currency"],
            buy_rate=Decimal(str(adapter["buy_rate"])),
            sell_rate=Decimal(str(adapter["sell_rate"])),
            source=adapter["source"],
            source_updated_at=adapter.get("source_updated_at"),
            scraped_at=datetime.fromisoformat(adapter["scraped_at"]),
        )
        self.session.add(record)
        self.session.commit()
        return item


class RetentionPipeline:
    """Prunes rate history older than RETENTION_DAYS once a run finishes.

    Keeps the store — and the SQLite file the scheduled workflow commits
    back to git — bounded to roughly three months of data instead of
    growing forever. Implemented as `close_spider` only (no `process_item`):
    pruning is a once-per-run bulk operation, not something to repeat for
    every one of the run's items.
    """

    def close_spider(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        with get_session() as session:
            # Load-then-delete rather than a single bulk DELETE statement:
            # at this data volume (a few hundred rows at most, per the
            # retention window) the difference is immaterial, and this way
            # stays ORM-level rather than mixing in raw SQL.
            stale = session.exec(select(ExchangeRate).where(ExchangeRate.scraped_at < cutoff)).all()
            for row in stale:
                session.delete(row)
            session.commit()
