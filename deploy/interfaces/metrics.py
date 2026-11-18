# Vendored from Infrastructure's interfaces/metrics.py so strategy code in
# this repo can be written and tested against the real contract without
# installing the full infrastructure package (engine/execution/NATS/etc.)
# just to research and prototype. Zero runtime dependencies beyond stdlib
# by design — that's what makes vendoring safe here.
#
# Source of truth: ETH-Quant-Research-Group/Infrastructure, interfaces/metrics.py
# Keep this in sync manually if that file's contract changes. The deploy/
# image never uses this copy — it installs the real infrastructure package,
# so the deployed strategy always runs against the actual, current contract.
"""Metrics a strategy reports about itself, shown on its page on the site.

The site shows the same core numbers for every strategy (PnL, drawdown,
exposure, fills, ...). What matters beyond that depends on the strategy — a
momentum strategy's signal strength and hit rate, a carry trade's funding
APR and basis, a pairs trade's spread z-score — so each strategy reports
those itself, by overriding :meth:`BaseStrategy.metrics
<interfaces.strategy.BaseStrategy.metrics>`::

    def metrics(self) -> list[Metric]:
        return [
            Metric("Signal", self._z, hint="z-score of the 20-bar return"),
            Metric("Hit rate", self._wins / max(self._trades, 1), fmt="percent"),
            Metric("Avg holding", self._avg_hold_s, fmt="duration"),
        ]

The worker calls it every few seconds and sends the result with the
strategy's heartbeat; the site renders them in order, formatted by ``fmt``.
No site change is needed for a new kind of strategy.

Standard library only, so strategy repos can vendor this file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

#: How the site formats a metric's value:
#:
#: - ``number``    plain number, e.g. 1.234
#: - ``percent``   a fraction shown as a percentage: 0.0523 → 5.23%
#: - ``usd``       dollars: 1234.5 → $1,234.50
#: - ``bps``       basis points: 12.5 → 12.5 bps (pass the value in bps)
#: - ``duration``  seconds shown as e.g. 3h 20m
#: - ``text``      shown as given, e.g. "LONG", "risk-off"
MetricFormat = Literal["number", "percent", "usd", "bps", "duration", "text"]

FORMATS: frozenset[str] = frozenset(
    ("number", "percent", "usd", "bps", "duration", "text")
)

#: At most this many metrics are sent per strategy; the rest are dropped.
MAX_METRICS = 24


@dataclass(frozen=True, slots=True)
class Metric:
    """One number (or short text) a strategy wants shown on its page.

    ``value`` may be ``None`` while it isn't known yet (shown as "—").
    ``hint`` is a short explanation shown under the value. ``decimals``
    overrides how many decimals the site shows.
    """

    label: str
    value: float | int | Decimal | str | None
    fmt: MetricFormat = "number"
    hint: str = ""
    decimals: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "value": _json_value(self.value),
            "fmt": self.fmt,
            "hint": self.hint,
            "decimals": self.decimals,
        }


def _json_value(value: object) -> float | str | None:
    """A JSON-safe value: numbers as floats (NaN / infinity → None), text as
    is, anything else as its text."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int | float | Decimal):
        number = float(value)
        return number if math.isfinite(number) else None
    return str(value)


def metric_dicts(items: object) -> list[dict[str, Any]]:
    """What :meth:`BaseStrategy.metrics` returned, as JSON-safe dicts.

    Accepts :class:`Metric` objects, or plain dicts with the same keys (for
    strategies built against an older contract). Items without a label are
    skipped, an unknown ``fmt`` becomes ``number``, and at most
    :data:`MAX_METRICS` are kept.
    """
    if not isinstance(items, list | tuple):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Metric):
            d = item.to_dict()
        elif isinstance(item, dict) and item.get("label"):
            decimals = item.get("decimals")
            d = {
                "label": str(item["label"]),
                "value": _json_value(item.get("value")),
                "fmt": str(item.get("fmt", "number")),
                "hint": str(item.get("hint", "")),
                "decimals": decimals if isinstance(decimals, int) else None,
            }
        else:
            continue
        if d["fmt"] not in FORMATS:
            d["fmt"] = "number"
        out.append(d)
        if len(out) == MAX_METRICS:
            break
    return out
