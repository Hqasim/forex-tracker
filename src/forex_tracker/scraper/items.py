"""Data contract for a single scraped open-market rate record."""

from __future__ import annotations

import scrapy


class ExchangeRateItem(scrapy.Item):
    """One currency's PKR quote from a single scrape run.

    `scrapy.Item` fields are declared this way (rather than as, say, a
    dataclass) because Scrapy's pipeline/exporter machinery — `ItemAdapter`,
    the JSON feed exporter used by `scrapy crawl rates -o rates.json`, etc.
    — is built around this API.
    """

    #: ISO 4217 code of the foreign currency, e.g. "USD" (always vs. PKR).
    currency = scrapy.Field()
    #: PKR the dealer pays *you* per unit of `currency` (dealer buys).
    buy_rate = scrapy.Field()
    #: PKR *you* pay the dealer per unit of `currency` (dealer sells).
    sell_rate = scrapy.Field()
    #: Constant "forex.pk" today; kept as a field (not hardcoded downstream)
    #: so a second spider/source could populate the same item shape later.
    source = scrapy.Field()
    #: The timestamp forex.pk itself displays for the quote, as free text.
    source_updated_at = scrapy.Field()
    #: When *we* fetched the page (UTC, ISO 8601) — see RatesSpider.parse.
    scraped_at = scrapy.Field()
