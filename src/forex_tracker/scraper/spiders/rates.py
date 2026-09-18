"""Spider that scrapes Pakistan's open-market currency rates from forex.pk.

Domain background, for readers unfamiliar with currency-exchange
terminology: a money changer quotes two prices per currency —
"buying" is the PKR rate at which *they* buy the foreign currency
from you (what you receive if you sell USD, EUR, etc.), and
"selling" is the rate at which *they* sell it to you (what you pay
to acquire it). Selling is always >= buying; that spread is the
money changer's margin, and `ValidationPipeline` treats an inverted
spread as a sign the page was misparsed rather than a real quote.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime

import scrapy
from scrapy.http import Response

from forex_tracker.constants import TRACKED_CURRENCIES
from forex_tracker.scraper.items import ExchangeRateItem


class RatesSpider(scrapy.Spider):
    """Scrapes forex.pk's "Pakistan Open Market Rates" table.

    Each tracked currency's buying/selling rate is quoted in PKR. Rows are
    located by the currency-code cell (e.g. the `<td>` containing "EUR")
    rather than an absolute table position, so the spider survives
    incidental layout changes such as an inserted column or a reordered
    row. The code cell's text is matched with `normalize-space(td[2])` —
    evaluated against the whole cell rather than a direct `text()` node —
    because this particular table wraps the code in a nested `<a>` element.
    """

    name = "rates"
    # Restricting the crawl to forex.pk means a bug that somehow yields an
    # off-site link (e.g. a rogue ad redirect) can never be followed.
    allowed_domains = ["forex.pk"]
    start_urls = ["https://www.forex.pk/open_market_rates.asp"]

    def parse(self, response: Response) -> Iterator[ExchangeRateItem]:
        """Extract one item per tracked currency from the rates table.

        Runs once per response (there is only one page, no pagination/
        follow-up requests), so this is a plain generator rather than
        something that also yields further `scrapy.Request` objects.
        """
        source_updated_at = self._parse_source_timestamp(response)
        # Stamped once per run (not per item) so every row from this scrape
        # shares an identical `scraped_at`, letting the API/chart group a
        # run's rows together without needing a separate "run id" table.
        scraped_at = datetime.now(UTC).isoformat()

        found: set[str] = set()
        for currency in TRACKED_CURRENCIES:
            row = response.xpath(f'//tr[normalize-space(td[2])="{currency}"]')
            buy_rate = row.xpath("./td[3]/text()").get()
            sell_rate = row.xpath("./td[4]/text()").get()
            if buy_rate is None or sell_rate is None:
                # Don't let one missing currency abort the whole run — log
                # it and keep going so the other four still get scraped.
                self.logger.warning("Could not find buy/sell rates for %s", currency)
                continue

            found.add(currency)
            yield ExchangeRateItem(
                currency=currency,
                buy_rate=buy_rate.strip(),
                sell_rate=sell_rate.strip(),
                source="forex.pk",
                source_updated_at=source_updated_at,
                scraped_at=scraped_at,
            )

        missing = set(TRACKED_CURRENCIES) - found
        if missing:
            # Distinct from the per-currency warning above: this fires once,
            # loudly, if the page structure has drifted enough that an
            # entire currency vanished — the signal an operator would
            # actually want surfaced (e.g. in CI/Actions logs).
            self.logger.error(
                "Page structure may have changed; missing currencies: %s", sorted(missing)
            )

    @staticmethod
    def _parse_source_timestamp(response: Response) -> str | None:
        """Extract forex.pk's own "as on <timestamp>" label, if present.

        This is metadata about *when the source claims the page was last
        updated*, kept alongside our own `scraped_at` (when we actually
        fetched it) — the two can legitimately differ if the site's cache
        lags behind a live market move.
        """
        raw = response.xpath(
            'string(//p[span[contains(@class, "bluetext") and contains(., "Open Market")]])'
        ).get()
        if raw is None:
            return None
        match = re.search(r"as on (.+?)(?:\n|$)", raw)
        return match.group(1).strip() if match else raw.strip()
