"""Constants shared across the scraper, pipelines, API, and chart command."""

from __future__ import annotations

#: Foreign currencies tracked against PKR (the open market's quote currency).
TRACKED_CURRENCIES: tuple[str, ...] = ("USD", "EUR", "CNY", "SAR", "INR")

#: How much rate history to retain and display — the "last three months" window.
RETENTION_DAYS: int = 90
