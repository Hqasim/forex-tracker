# Forex Tracker

[![CI](https://github.com/Hqasim/forex-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Hqasim/forex-tracker/actions/workflows/ci.yml)
[![Scheduled scrape](https://github.com/Hqasim/forex-tracker/actions/workflows/scrape.yml/badge.svg)](https://github.com/Hqasim/forex-tracker/actions/workflows/scrape.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A small, production-shaped data pipeline: a **Scrapy** spider scrapes daily USD
exchange rates, validates and persists them to **SQLite**, and a **FastAPI**
service and **matplotlib** chart command expose the resulting history. A
GitHub Actions workflow runs the scrape on a schedule so the dataset grows on
its own.

This started as a one-off scraping script; the current version rebuilds it
around resilient selectors, validation, persistence, tests, and CI — see
[Design decisions](#design-decisions) for the reasoning.

## Screenshots

| Trend chart (`forex-tracker chart EUR`) | API docs (`/docs`) |
| --- | --- |
| ![EUR trend chart](docs/screenshots/eur_trend.png) | _Add a screenshot of the Swagger UI at `http://127.0.0.1:8000/docs` here_ |

> The chart above is real output from this repo's own scrape — as the
> scheduled workflow accumulates more daily data points, it becomes an
> actual trend line rather than a single dot. Drop additional screenshots
> (CLI output, `/rates/latest` response, etc.) into `docs/screenshots/` and
> reference them here.

## Architecture

```
                 ┌────────────────────┐
 forex.pk  ───▶  │  RatesSpider        │
                 │  (scrapy)           │
                 └─────────┬───────────┘
                           │ ExchangeRateItem
                           ▼
                 ┌────────────────────┐
                 │ ValidationPipeline  │  drops malformed / out-of-range items
                 └─────────┬───────────┘
                           ▼
                 ┌────────────────────┐
                 │ SQLModelPipeline    │  persists to SQLite
                 └─────────┬───────────┘
                           ▼
                 ┌────────────────────┐        ┌───────────────────────┐
                 │ data/forex_tracker │ ◀────▶ │ FastAPI (/rates/*)     │
                 │        .db         │        └───────────────────────┘
                 └─────────┬───────────┘
                           ▼
                 ┌────────────────────┐
                 │ matplotlib chart    │
                 └────────────────────┘
```

## Requirements

- Python **3.12+** (developed and tested against **3.14.7**)
- No external services — SQLite is a plain file, no database server needed

## Setup

```bash
git clone https://github.com/Hqasim/forex-tracker.git
cd forex-tracker
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate on cmd/PowerShell
pip install -e ".[dev]"
```

## Usage

All commands go through the `forex-tracker` CLI (installed by the step above).

```bash
# Scrape the current rates and store them in data/forex_tracker.db
forex-tracker scrape

# Serve the API at http://127.0.0.1:8000 (interactive docs at /docs)
forex-tracker serve

# Render a trend chart for one currency
forex-tracker chart EUR --output docs/screenshots/eur_trend.png
```

The original `scrapy crawl rates -o rates.json` invocation still works too
(run from the repo root, where `scrapy.cfg` lives) if you just want a raw
JSON feed instead of the SQLite history.

### API

| Endpoint | Description |
| --- | --- |
| `GET /health` | Liveness check |
| `GET /rates/latest` | Latest stored rate for every tracked currency |
| `GET /rates/history?currency=EUR&limit=30` | Chronological history for one currency |

### Tracked currencies

`CNY`, `EUR`, `JPY`, `PKR`, `SAR`, `AED`, `GBP` (all quoted as units per USD).

## Development

```bash
ruff check .          # lint
ruff format .         # format
mypy src              # type-check (strict)
pytest --cov=forex_tracker   # tests, offline (no network calls)
pre-commit install    # run the above automatically on each commit
```

Spider tests run against a saved HTML fixture in `tests/fixtures/`, so the
suite never depends on forex.pk being reachable or unchanged mid-test-run.

## Automation

`.github/workflows/scrape.yml` runs `forex-tracker scrape` daily, regenerates
the sample chart, and commits both back to the repo — so the commit history
itself is a visible, running record of the pipeline working. `ci.yml` lints,
type-checks, and tests on every push across Python 3.12–3.14.

## Design decisions

- **Anchor-based selectors, not absolute XPath.** The original spider used
  paths like `/html/body/table/tr[1]/td[2]/table/...`, which break on any
  incidental layout change. The current spider locates each row by its
  currency-code cell (`//tr[td[2][text()="EUR"]]/td[3]`) instead, and logs a
  warning — rather than crashing or silently emitting `None` — if a currency
  disappears from the page.
- **`ROBOTSTXT_OBEY = True`, a real `USER_AGENT`, and `AUTOTHROTTLE`** are
  deliberate choices to scrape politely rather than as fast as possible.
- **Validation before persistence.** A dedicated pipeline stage rejects
  unknown currency codes and non-numeric/non-positive rates before anything
  reaches SQLite, so a partially-broken page can't corrupt the history.
- **SQLite over a hosted database.** For a single-writer, low-volume history
  like this, a file-based store keeps the project runnable with zero
  infrastructure. If this needed multiple writers or larger scale, the
  natural next step is Postgres + Alembic migrations (SQLModel already gives
  a straightforward migration path there).
- **`Decimal`, not `float`, for rates.** Exchange rates are financial data;
  storing them as `Decimal` avoids floating-point representation error
  creeping into stored history.

## Possible extensions

Ideas for taking this further, roughly in order of effort:

- Second spider for another FX source + a reconciliation step that flags
  disagreements between sources.
- Alerting (email/Slack webhook) when a rate crosses a configured threshold.
- Swap SQLite for Postgres with Alembic migrations if this needed concurrent
  writers.
- Dockerize and deploy the API somewhere publicly reachable (Fly.io, Railway,
  Render).

## License

[MIT](LICENSE)
