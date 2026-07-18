# Vendored from Infrastructure's interfaces/strategy.py so strategy code in
# this repo can be written and tested against the real contract without
# installing the full infrastructure package (engine/execution/NATS/etc.)
# just to research and prototype. Zero runtime dependencies beyond stdlib
# by design — that's what makes vendoring safe here.
#
# Source of truth: ETH-Quant-Research-Group/Infrastructure, interfaces/strategy.py
# Keep this in sync manually if that file's contract changes. The deploy/
# image never uses this copy — it installs the real infrastructure package,
# so the deployed strategy always runs against the actual, current contract.
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    # These resolve when the real `infrastructure` package is installed
    # (i.e. inside deploy/). In this repo's lightweight research
    # environment they're annotations only — harmless if unresolved.
    from data.types import AnyBar, FundingRate, Trade
    from execution.types import FillConfirmation
    from interfaces.signals import TargetPosition


class BaseStrategy(ABC):
    """Foundation class for all trading strategies.

    Subclass this and implement :meth:`on_bar` to react to incoming market
    data.  Override :meth:`on_start` and :meth:`on_stop` for setup and
    teardown logic.

    Class-level attributes to set on each subclass:

    ``topics``
        List of bus topic strings this strategy wants to receive.
        NATS subject strings, e.g. ``"futures.BTCUSDT.bars.1m"``.

    ``max_loss``
        A local default only. Real enforcement lives centrally in the
        consolidator's StrategyGuardRegistry, keyed by STRATEGY_ID and
        configured from the admin's "Max drawdown" field on the /internal
        Deploy page — this attribute is just what gets reported if that
        field is left blank. See deploy/README section on risk limits.

    Example::

        class MomentumStrategy(BaseStrategy):
            topics = [futures_bars_topic("BTCUSDT", KlineInterval.M1)]
            max_loss = Decimal("500")

            def on_bar(self, bar: AnyBar) -> TargetPosition | None:
                # your signal logic here
                ...
    """

    topics: ClassVar[list[str]] = []
    max_loss: ClassVar[Decimal] = Decimal("1000")

    def on_start(self) -> None:  # noqa: B027
        """Called once before the strategy begins receiving bars."""

    @abstractmethod
    def on_bar(self, bar: AnyBar) -> TargetPosition | None:
        """Called for each new bar, whether live or historical."""

    def on_trade(self, trade: Trade) -> TargetPosition | None:  # noqa: B027
        """Called for each individual trade tick (optional override)."""
        return None

    def on_funding_rate(self, rate: FundingRate) -> TargetPosition | None:  # noqa: B027
        """Called for each funding-rate update (optional override)."""
        return None

    def on_fill(self, fill: FillConfirmation) -> TargetPosition | None:  # noqa: B027
        """Called when the consolidator confirms a fill for this strategy (optional).

        Return a :class:`~interfaces.signals.TargetPosition` to immediately emit
        a follow-up signal — useful for placing a spot hedge after a perp fill.
        Return ``None`` for no further action.
        """
        return None

    def on_stop(self) -> None:  # noqa: B027
        """Called once after the strategy stops receiving bars."""
