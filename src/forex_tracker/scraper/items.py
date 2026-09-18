"""Data contract for a single scraped exchange rate record."""

from __future__ import annotations

import scrapy


class ExchangeRateItem(scrapy.Item):
    currency = scrapy.Field()
    rate = scrapy.Field()
    source = scrapy.Field()
    source_updated_at = scrapy.Field()
    scraped_at = scrapy.Field()
