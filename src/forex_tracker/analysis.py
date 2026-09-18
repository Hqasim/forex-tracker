"""Chart generation from stored open-market rate history.

Each tracked currency gets its own figure rather than all five sharing one
plot. The currencies span roughly two orders of magnitude in PKR value
(INR ~2.6-3, USD ~278) — on a single shared y-axis, INR's trend would be
visually flattened to a near-flat line near zero while USD/EUR dominate
the scale, defeating the point of plotting it at all. A separate y-axis
per currency, auto-scaled to that currency's own range, is what actually
makes each trend "visible and noticeable" (the operative requirement this
module is built around).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import matplotlib

# Must be set before importing pyplot: "Agg" is a non-interactive backend
# that renders straight to a file. Without it, matplotlib would try (and,
# on a headless CI runner, fail) to open a GUI window.
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from sqlmodel import select

from forex_tracker.constants import RETENTION_DAYS, TRACKED_CURRENCIES
from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session


def plot_currency_trend(currency: str, output: Path, *, since_days: int = RETENTION_DAYS) -> None:
    """Render one chart of a single currency's PKR buying/selling history.

    Raises `ValueError` if there's no stored history for `currency` within
    the requested window — callers (the CLI, and `plot_all_currency_trends`
    below) decide whether that's fatal or just skip-and-continue.
    """
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    with get_session() as session:
        rows = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency, ExchangeRate.scraped_at >= cutoff)
            .order_by(ExchangeRate.scraped_at)  # type: ignore[arg-type]
        ).all()

    if not rows:
        raise ValueError(f"No stored history for {currency!r} in the last {since_days} days")

    timestamps = [row.scraped_at for row in rows]
    buy_values = [float(row.buy_rate) for row in rows]
    sell_values = [float(row.sell_rate) for row in rows]

    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))

    # Buying and selling are drawn as two distinct series (solid vs. dashed,
    # both with point markers) rather than, say, a shaded band between
    # them, so the dealer's spread and each side's own trend are both
    # individually readable at a glance.
    ax.plot(
        timestamps,  # type: ignore[arg-type]
        buy_values,
        marker="o",
        markersize=4,
        linewidth=1.8,
        label="Buying rate (PKR paid to you)",
    )
    ax.plot(
        timestamps,  # type: ignore[arg-type]
        sell_values,
        marker="o",
        markersize=4,
        linewidth=1.8,
        linestyle="--",
        label="Selling rate (PKR you pay)",
    )

    ax.set_title(
        f"{currency} / PKR — Pakistan Open Market rate (last {since_days} days)",
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xlabel("Date")
    ax.set_ylabel(f"PKR per 1 {currency}")
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.6)
    # loc="best" lets matplotlib pick whichever corner the data doesn't
    # occupy, rather than a hardcoded corner that could end up on top of
    # the trend line depending on which way rates moved.
    ax.legend(loc="best", fontsize=9, framealpha=0.9)

    # AutoDateLocator + ConciseDateFormatter is what makes the x-axis
    # "compress naturally": for a short span it labels individual days,
    # and as the span grows towards the 90-day retention window it steps
    # up to weekly/monthly ticks on its own — no manual tick-interval
    # tuning, and no becoming an unreadable wall of overlapping day labels.
    locator = mdates.AutoDateLocator()  # type: ignore[no-untyped-call]
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))  # type: ignore[no-untyped-call]

    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)  # release the figure; matplotlib doesn't GC these on its own


def plot_all_currency_trends(output_dir: Path, *, since_days: int = RETENTION_DAYS) -> list[Path]:
    """Render every tracked currency's chart into `output_dir`.

    Each file is named `<currency>_trend.png` (lowercase), e.g.
    `usd_trend.png`. A currency with no stored history yet is skipped
    rather than raising — expected on a fresh install before the first
    scrape has run for long enough to build up a trend. Returns the paths
    actually written, so a caller can report exactly what happened.
    """
    written: list[Path] = []
    for currency in TRACKED_CURRENCIES:
        output = output_dir / f"{currency.lower()}_trend.png"
        try:
            plot_currency_trend(currency, output, since_days=since_days)
        except ValueError:
            continue
        written.append(output)
    return written
