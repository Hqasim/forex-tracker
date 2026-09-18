"""Spider that scrapes daily USD exchange rates from forex.pk."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime

import scrapy
from scrapy.http import Response

from forex_tracker.scraper.items import ExchangeRateItem

TRACKED_CURRENCIES = ("CNY", "EUR", "JPY", "PKR", "SAR", "AED", "GBP")


class RatesSpider(scrapy.Spider):
    """Scrapes the forex.pk exchange rate table.

    Each row is located by anchoring on the currency code cell (e.g. the
    `<td>` containing exactly "EUR") rather than an absolute table position.
    That survives the kind of incidental layout changes (an inserted column,
    a re-ordered row) that broke the original spider's fixed XPath, while
    still failing loudly via a logged warning if a currency truly disappears
    from the page.
    """

    name = "rates"
    start_urls = ["https://www.forex.pk/foreign-exchange-rate.html"]

    def parse(self, response: Response) -> Iterator[ExchangeRateItem]:
        source_updated_at = self._parse_source_timestamp(response)
        scraped_at = datetime.now(UTC).isoformat()

        found: set[str] = set()
        for currency in TRACKED_CURRENCIES:
            rate = response.xpath(
                f'//tr[td[2][normalize-space(text())="{currency}"]]/td[3]/text()'
            ).get()
            if rate is None:
                self.logger.warning("Could not find a rate row for %s", currency)
                continue

            found.add(currency)
            yield ExchangeRateItem(
                currency=currency,
                rate=rate.strip(),
                source="forex.pk",
                source_updated_at=source_updated_at,
                scraped_at=scraped_at,
            )

        missing = set(TRACKED_CURRENCIES) - found
        if missing:
            self.logger.error(
                "Page structure may have changed; missing currencies: %s", sorted(missing)
            )

    @staticmethod
    def _parse_source_timestamp(response: Response) -> str | None:
        raw = response.css("span.blueboldtext::text").get()
        if raw is None:
            return None
        match = re.search(r"As on (.+)", raw)
        return match.group(1).strip() if match else raw.strip()
