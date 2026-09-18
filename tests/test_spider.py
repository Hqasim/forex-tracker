"""Offline tests for the rates spider, using a saved HTML fixture.

No network calls are made: the fixture in tests/fixtures/ was captured once
from the live site so parsing logic can be tested deterministically.
"""

from __future__ import annotations

from pathlib import Path

from scrapy.http import HtmlResponse

from forex_tracker.scraper.spiders.rates import TRACKED_CURRENCIES, RatesSpider

FIXTURE = Path(__file__).parent / "fixtures" / "forex_pk_sample.html"


def _response(body: bytes | None = None) -> HtmlResponse:
    return HtmlResponse(
        url="https://www.forex.pk/foreign-exchange-rate.html",
        body=body if body is not None else FIXTURE.read_bytes(),
    )


def test_parse_yields_all_tracked_currencies() -> None:
    spider = RatesSpider()
    items = list(spider.parse(_response()))
    currencies = {item["currency"] for item in items}
    assert currencies == set(TRACKED_CURRENCIES)


def test_parse_extracts_expected_rate_and_source() -> None:
    spider = RatesSpider()
    items = {item["currency"]: item for item in spider.parse(_response())}
    assert items["EUR"]["rate"] == "0.8659"
    assert items["GBP"]["source"] == "forex.pk"


def test_parse_captures_source_timestamp() -> None:
    spider = RatesSpider()
    items = list(spider.parse(_response()))
    assert all(item["source_updated_at"] == "Thu, Jun 11 2026, 19:58 GMT" for item in items)


def test_parse_warns_and_skips_on_missing_currency_row(caplog) -> None:
    """A row disappearing from the page should be logged, not crash the spider."""
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<td align="center">EUR</td>', '<td align="center">XXX</td>'
    )
    spider = RatesSpider()
    with caplog.at_level("WARNING"):
        items = list(spider.parse(_response(html.encode("utf-8"))))

    assert "EUR" not in {item["currency"] for item in items}
    assert any("EUR" in message for message in caplog.messages)
