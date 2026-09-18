"""Command-line entry point: scrape, serve the API, or render trend charts.

Registered as the `forex-tracker` console script in `pyproject.toml`
(`[project.scripts]`), so after `pip install -e .` these subcommands are
also reachable as `forex-tracker scrape` / `serve` / `chart` directly.
"""

from __future__ import annotations

import os
from pathlib import Path

# Scrapy normally discovers its settings module by walking up from the
# current working directory looking for `scrapy.cfg`. Setting the env var
# explicitly instead means `forex-tracker scrape` works from *any* working
# directory, not only when invoked from the repo root — important once
# this is an installed console script rather than something always run via
# `cd repo && scrapy crawl rates`. Must happen before `scrapy.utils.project`
# is imported below, since it reads the env var at import/call time.
os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "forex_tracker.scraper.settings")

import typer
import uvicorn
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from forex_tracker.analysis import plot_all_currency_trends, plot_currency_trend
from forex_tracker.constants import RETENTION_DAYS, TRACKED_CURRENCIES

app = typer.Typer(help="Forex Tracker: scrape, serve, and chart PKR open-market rates.")


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
    currency: str | None = typer.Argument(
        None,
        help=f"Currency to chart, one of {', '.join(TRACKED_CURRENCIES)}. "
        "Omit to render every tracked currency.",
    ),
    output_dir: Path = Path("docs/screenshots"),
    since_days: int = RETENTION_DAYS,
) -> None:
    """Render PKR buy/sell trend chart(s) — one PNG per currency.

    `forex-tracker chart` writes one file per tracked currency into
    `output_dir` (e.g. `docs/screenshots/usd_trend.png`).
    `forex-tracker chart USD` writes just that currency's chart instead.
    """
    if currency is not None:
        currency = currency.upper()
        output = output_dir / f"{currency.lower()}_trend.png"
        plot_currency_trend(currency, output, since_days=since_days)
        typer.echo(f"Wrote {output}")
        return

    written = plot_all_currency_trends(output_dir, since_days=since_days)
    if not written:
        typer.echo("No stored history yet — run `forex-tracker scrape` first.")
        raise typer.Exit(code=1)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    app()
