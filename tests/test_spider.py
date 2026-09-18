"""Offline tests for the rates spider, using a saved HTML fixture.

No network calls are made: the fixture in tests/fixtures/ was captured once
from the live site so parsing logic can be tested deterministically.
"""

from __future__ import annotations

from pathlib import Path

from scrapy.http import HtmlResponse

from forex_tracker.constants import TRACKED_CURRENCIES
from forex_tracker.scraper.spiders.rates import RatesSpider

FIXTURE = Path(__file__).parent / "fixtures" / "forex_pk_open_market_sample.html"


def _response(body: bytes | None = None) -> HtmlResponse:
    return HtmlResponse(
        url="https://www.forex.pk/open_market_rates.asp",
        body=body if body is not None else FIXTURE.read_bytes(),
    )


def test_parse_yields_all_tracked_currencies() -> None:
    spider = RatesSpider()
    items = list(spider.parse(_response()))
    currencies = {item["currency"] for item in items}
    assert currencies == set(TRACKED_CURRENCIES)


def test_parse_extracts_expected_buy_and_sell_rates() -> None:
    spider = RatesSpider()
    items = {item["currency"]: item for item in spider.parse(_response())}
    assert items["USD"]["buy_rate"] == "278"
    assert items["USD"]["sell_rate"] == "278.3"
    assert items["EUR"]["buy_rate"] == "318.94"
    assert items["EUR"]["sell_rate"] == "323.95"
    assert items["INR"]["source"] == "forex.pk"


def test_parse_ignores_remittance_only_rows() -> None:
    """USD-DD / USD-TT rows (a different table) must not be picked up as USD."""
    spider = RatesSpider()
    items = {item["currency"] for item in spider.parse(_response())}
    assert "USD-DD" not in items
    assert "USD-TT" not in items


def test_parse_captures_source_timestamp() -> None:
    spider = RatesSpider()
    items = list(spider.parse(_response()))
    assert all(item["source_updated_at"] == "Fri, Sep 18 2026, 22:13 PST (GMT+5)" for item in items)


def test_parse_warns_and_skips_on_missing_currency_row(caplog) -> None:
    """A row disappearing from the page should be logged, not crash the spider."""
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<img src="flags/EUR.gif" alt="EUR" class="box" />&nbsp;&nbsp; Euro</td>\n'
        '                      <td align="center"><a href="https://www.forex.pk/'
        'currency-eur-to-pkr-to-euro.php">EUR</a></td>',
        '<img src="flags/EUR.gif" alt="EUR" class="box" />&nbsp;&nbsp; Euro</td>\n'
        '                      <td align="center"><a href="https://www.forex.pk/'
        'currency-eur-to-pkr-to-euro.php">XXX</a></td>',
    )
    spider = RatesSpider()
    with caplog.at_level("WARNING"):
        items = list(spider.parse(_response(html.encode("utf-8"))))

    assert "EUR" not in {item["currency"] for item in items}
    assert any("EUR" in message for message in caplog.messages)
