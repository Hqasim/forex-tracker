"""Command-line entry point: scrape, serve the API, or render a trend chart."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "forex_tracker.scraper.settings")

import typer
import uvicorn
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from forex_tracker.analysis import plot_currency_trend

app = typer.Typer(help="Forex Tracker: scrape, serve, and chart USD exchange rates.")


@app.command()
def scrape() -> None:
    """Run the rates spider once, writing results into the SQLite history."""
    process = CrawlerProcess(get_project_settings())
    process.crawl("rates")
    process.start()


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Serve the FastAPI app exposing scraped rate history."""
    uvicorn.run("forex_tracker.api.main:app", host=host, port=port, reload=reload)


@app.command()
def chart(
    currency: str,
    output: Path = Path("docs/screenshots/trend.png"),
    limit: int = 30,
) -> None:
    """Render a PNG trend chart for one currency from stored history."""
    plot_currency_trend(currency.upper(), output, limit=limit)
    typer.echo(f"Wrote {output}")


if __name__ == "__main__":
    app()
