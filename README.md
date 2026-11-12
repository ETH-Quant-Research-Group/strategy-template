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
