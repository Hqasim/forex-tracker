"""Tests for the validation pipeline's drop conditions."""

from __future__ import annotations

import pytest
from scrapy.exceptions import DropItem

from forex_tracker.scraper.items import ExchangeRateItem
from forex_tracker.scraper.pipelines import ValidationPipeline


def _item(**overrides: str) -> ExchangeRateItem:
    base = {
        "currency": "EUR",
        "rate": "0.8659",
        "source": "forex.pk",
        "source_updated_at": "Thu, Jun 11 2026, 19:58 GMT",
        "scraped_at": "2026-06-11T19:58:00+00:00",
    }
    base.update(overrides)
    return ExchangeRateItem(**base)


def test_valid_item_passes_through() -> None:
    pipeline = ValidationPipeline()
    item = _item()
    assert pipeline.process_item(item) is item


def test_unknown_currency_is_dropped() -> None:
    pipeline = ValidationPipeline()
    with pytest.raises(DropItem):
        pipeline.process_item(_item(currency="XXX"))


def test_non_numeric_rate_is_dropped() -> None:
    pipeline = ValidationPipeline()
    with pytest.raises(DropItem):
        pipeline.process_item(_item(rate="not-a-number"))


def test_non_positive_rate_is_dropped() -> None:
    pipeline = ValidationPipeline()
    with pytest.raises(DropItem):
        pipeline.process_item(_item(rate="0"))
