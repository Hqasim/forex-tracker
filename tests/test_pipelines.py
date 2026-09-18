"""Tests for the validation pipeline's drop conditions."""

from __future__ import annotations

import pytest
from scrapy.exceptions import DropItem

from forex_tracker.scraper.items import ExchangeRateItem
from forex_tracker.scraper.pipelines import ValidationPipeline


def _item(**overrides: str) -> ExchangeRateItem:
    base = {
        "currency": "EUR",
        "buy_rate": "318.94",
        "sell_rate": "323.95",
        "source": "forex.pk",
        "source_updated_at": "Fri, Sep 18 2026, 22:13 PST (GMT+5)",
        "scraped_at": "2026-09-18T22:13:00+00:00",
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
        pipeline.process_item(_item(buy_rate="not-a-number"))


def test_non_positive_rate_is_dropped() -> None:
    pipeline = ValidationPipeline()
    with pytest.raises(DropItem):
        pipeline.process_item(_item(buy_rate="0", sell_rate="0"))


def test_sell_below_buy_is_dropped() -> None:
    pipeline = ValidationPipeline()
    with pytest.raises(DropItem):
        pipeline.process_item(_item(buy_rate="320", sell_rate="310"))


def test_equal_buy_and_sell_is_allowed() -> None:
    """A zero spread is unusual but not invalid."""
    pipeline = ValidationPipeline()
    item = _item(buy_rate="278", sell_rate="278")
    assert pipeline.process_item(item) is item
