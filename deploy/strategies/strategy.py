from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

from interfaces.metrics import Metric
from interfaces.strategy import BaseStrategy

if TYPE_CHECKING:
    from data.types import AnyBar, FundingRate
    from interfaces.signals import TargetPosition

log = logging.getLogger(__name__)


class ExampleStrategy(BaseStrategy):
    """Alternates long/short 0.001 BTCUSDT each bar. Replace with real logic —
    this class only exists to prove the discovery/build/deploy path end to end.
    """

    topics: ClassVar[list[str]] = [
        "futures.BTCUSDT.bars.1m",
        "futures.BTCUSDT.funding_rate",
    ]

    # Cosmetic default only — real enforcement lives in the consolidator's
    # StrategyGuardRegistry (engine/order/guard_registry.py), keyed by
    # STRATEGY_ID and configured from the admin's "Max drawdown" field on the
    # /internal Deploy page. That registry tracks realized PnL from its OWN
    # fills (ground truth) and drops signals for any breached strategy_id
    # regardless of what this container does — this attribute is only used
    # as the reported default if the admin leaves that field blank.
    max_loss: ClassVar[Decimal] = Decimal("500")

    def __init__(self) -> None:
        self._long = True
        # Tracked only to report in metrics() below.
        self._bars = 0
        self._last_close: Decimal | None = None
        self._first_close: Decimal | None = None
        self._last_flip = self.now()
        self._funding_rate: Decimal | None = None

    def on_bar(self, bar: AnyBar) -> TargetPosition | None:
        from interfaces.signals import TargetPosition

        qty = Decimal("0.001") if self._long else Decimal("-0.001")
        self._long = not self._long
        self._bars += 1
        self._last_close = bar.close
        if self._first_close is None:
            self._first_close = bar.close
        self._last_flip = self.now()

        log.info(
            "[%s] BAR close=%-12s target_qty=%s",
            self.__class__.__name__,
            bar.close,
            qty,
        )
        return TargetPosition(symbol="BTCUSDT", quantity=qty, exchange="bybit_demo")

    def on_funding_rate(self, rate: FundingRate) -> TargetPosition | None:
        self._funding_rate = rate.funding_rate
        log.info(
            "[%s] FUNDING rate=%-10s next=%s",
            self.__class__.__name__,
            rate.funding_rate,
            rate.next_funding_time,
        )
        return None

    def metrics(self) -> list[Metric]:
        """What this strategy shows on its page on the site, next to the PnL,
        drawdown and exposure every strategy gets. Report whatever tells
        someone how *this* strategy is doing: its signal, its regime, hit
        rate, the thing it trades on. Called every few seconds — return
        values you already track, don't compute anything heavy here.

        ``fmt`` decides how the site shows the value: number, percent (pass a
        fraction), usd, bps, duration (seconds) or text. ``None`` shows "—".
        """
        move = (
            float(self._last_close / self._first_close - 1)
            if self._first_close and self._last_close
            else None
        )
        return [
            Metric("Next position", "LONG" if self._long else "SHORT", fmt="text"),
            Metric("Bars seen", self._bars, decimals=0),
            Metric("BTC move", move, fmt="percent", hint="since the first bar"),
            Metric(
                "Since last flip",
                (self.now() - self._last_flip).total_seconds(),
                fmt="duration",
            ),
            Metric(
                "Funding rate",
                self._funding_rate,
                fmt="percent",
                decimals=4,
                hint="per settlement",
            ),
        ]
