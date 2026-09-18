"""Chart generation from stored exchange rate history."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from sqlmodel import select

from forex_tracker.db.models import ExchangeRate
from forex_tracker.db.session import get_session


def plot_currency_trend(currency: str, output: Path, *, limit: int = 30) -> None:
    """Render a line chart of a currency's rate history and save it as a PNG."""
    with get_session() as session:
        rows = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency)
            .order_by(ExchangeRate.scraped_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    rows = list(reversed(rows))

    if not rows:
        raise ValueError(f"No stored history for currency {currency!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(
        [r.scraped_at for r in rows],  # type: ignore[arg-type]
        [float(r.rate) for r in rows],
        marker="o",
    )
    ax.set_title(f"{currency} — units per USD")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rate")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
