from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

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

    def on_bar(self, bar: AnyBar) -> TargetPosition | None:
        from interfaces.signals import TargetPosition

        qty = Decimal("0.001") if self._long else Decimal("-0.001")
        self._long = not self._long

        log.info(
            "[%s] BAR close=%-12s target_qty=%s",
            self.__class__.__name__,
            bar.close,
            qty,
        )
        return TargetPosition(symbol="BTCUSDT", quantity=qty, exchange="bybit_demo")

    def on_funding_rate(self, rate: FundingRate) -> TargetPosition | None:
        log.info(
            "[%s] FUNDING rate=%-10s next=%s",
            self.__class__.__name__,
            rate.funding_rate,
            rate.next_funding_time,
        )
        return None
