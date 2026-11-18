# strategy-template

```
data/          research datasets — gitignored, local only
notebooks/     exploratory research, backtesting
interfaces/    the strategy contract (BaseStrategy, TargetPosition), vendored for research
deploy/        the complete, self-contained package that actually ships
```

`data/`, `notebooks/`, and `interfaces/` are for developing a strategy —
pull in data, prototype in a notebook, write logic against the vendored
`BaseStrategy`/`TargetPosition` contract with no heavy dependencies
(`uv sync` at the repo root only installs `pandas`/`jupyter`/`matplotlib`).

`deploy/` is the only thing that ships. It's fully self-contained: your
finished strategy code, any model weights or other assets it needs, its
own `pyproject.toml`/`uv.lock` (pinning the real `infrastructure` package),
its own copy of `interfaces/` (reference only — see below), and a
`Dockerfile`. Nothing outside `deploy/` is included in the image.

## Uploading a strategy: step by step

1. **Edit `deploy/strategies/strategy.py`** — that's the one that actually
   ships. Subclass `BaseStrategy`:

   ```python
   from decimal import Decimal
   from interfaces.strategy import BaseStrategy
   from interfaces.signals import TargetPosition

   class MyStrategy(BaseStrategy):
       topics = ["futures.BTCUSDT.bars.1m"]
       max_loss = Decimal("500")  # cosmetic default — real limit is set at deploy time

       def on_bar(self, bar):
           ...
           return TargetPosition(symbol="BTCUSDT", quantity=Decimal("0.001"))
   ```

   Drop any model weights or other assets it needs directly in `deploy/`
   too — everything there ships into the image.

   `deploy/strategies/` has no `__init__.py` — that's deliberate. The
   deployed worker discovers your class by scanning a package literally
   named `strategies` (`pkgutil.iter_modules`, hardcoded in
   `workers.strategy_worker`), and Python 3 namespace packages (no
   `__init__.py` needed) work fine for that. Don't rename this folder.

   `deploy/interfaces/` is the same `BaseStrategy`/`TargetPosition`
   contract, kept here purely so `deploy/` is self-contained to read and
   develop against. It's **not** shipped into the image — the Dockerfile
   excludes it via `.dockerignore`, since the real `interfaces` module
   comes from the installed `infrastructure` package. Don't import from it
   directly inside `strategy.py`; the `from interfaces.strategy import
   ...` in the example above already resolves to the real one once
   installed, whether locally (via `uv sync`) or in the built image.

   **Show what matters for your strategy on the site** by overriding
   `metrics()` — see [Strategy metrics](#strategy-metrics) below.


2. **Build the image from inside `deploy/`:**

   ```
   cd deploy
   docker buildx build \
     --platform linux/arm64 \
     --build-arg STRATEGY_NAME=MyStrategy \
     -t ghcr.io/eth-quant-research-group/<image-name>:latest \
     --push .
   ```

   The default target is `linux/arm64`. Always pass an explicit
   `--platform` rather than relying on plain `docker build`, which only
   targets the architecture you're building on (e.g. amd64 on an Intel/AMD
   machine) and would fail with "exec format error" on the arm64 deploy
   host. For a quick local-only test, swap `--push` for `--load`. If you
   ever need amd64 too, use `--platform linux/arm64,linux/amd64` — multi-
   platform builds require `--push` (they can't be `--load`-ed).

   This is a manual step — nothing here builds or pushes automatically on
   a git push.

3. **Deploy from the `/internal` Deploy page**, pointing it at the image
   you just pushed. It validates:
   - image ref starts with `ghcr.io/eth-quant-research-group/`
   - deploy name matches `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$`
   - injects `NATS_URL`, `BYBIT_API_KEY`, `BYBIT_API_SECRET`, `BYBIT_DEMO`,
     `TRADING_MODE`, `STRATEGY_ID` (auto, = your deploy name), and
     optionally `MAX_DRAWDOWN` — the risk limit that's actually enforced
     (see below).

## One thing worth knowing: risk limits aren't set by your code

`max_loss` on your class is a cosmetic default only. Real enforcement
lives centrally in the consolidator (`StrategyGuardRegistry`), which
tracks realized PnL per `STRATEGY_ID` from its own fills and drops signals
from any strategy that's breached the limit the admin set on the Deploy
page — regardless of what your container does. You don't need to
implement a guard yourself.

## Strategy metrics

Every strategy's page on the site shows the same core numbers: PnL,
drawdown, exposure, positions, fills. What else matters depends on the
strategy — a momentum strategy's signal strength and hit rate, a carry
trade's funding APR, a pairs trade's spread z-score, a stock strategy's
regime — so your strategy reports those itself by overriding `metrics()`:

```python
from interfaces.metrics import Metric

class MyStrategy(BaseStrategy):
    ...

    def metrics(self) -> list[Metric]:
        return [
            Metric("Signal", self._z, hint="z-score of the 20-bar return"),
            Metric("Hit rate", self._wins / max(self._trades, 1), fmt="percent"),
            Metric("Avg holding", self._avg_hold_seconds, fmt="duration"),
            Metric("Regime", "risk-on" if self._risk_on else "risk-off", fmt="text"),
        ]
```

They appear in a "Strategy Metrics" section on its page, in the order you
return them, and update live (the worker sends them every ~8 seconds with
the strategy's heartbeat). No change to the site is needed.

| `fmt` | pass | shown as |
| --- | --- | --- |
| `number` (default) | any number | `1.25` |
| `percent` | a fraction | `0.0523` → `5.23%` |
| `usd` | dollars | `-$1,234.50` |
| `bps` | basis points | `12.5 bps` |
| `duration` | seconds | `3h 20m` |
| `text` | a short string | `LONG` |

`value=None` shows "—" (e.g. before the first bar); `decimals=` fixes the
number of decimals; `hint=` adds a line of explanation under the value.

Keep it cheap: it's called every few seconds, so return values your
strategy already tracks — no heavy computation or network calls. If it
raises, the error is logged and that round's metrics are skipped; it never
stops your strategy. `deploy/strategies/strategy.py` has a working example.
