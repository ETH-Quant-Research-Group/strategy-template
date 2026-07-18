# syntax=docker/dockerfile:1
#
# Self-contained: everything the image needs (strategy code, model weights,
# any other assets) lives in this deploy/ folder. Build FROM INSIDE deploy/
# (context is deploy/ itself, not the repo root):
#
#   cd deploy
#   docker buildx build \
#     --platform linux/amd64,linux/arm64 \
#     --build-arg STRATEGY_NAME=ExampleStrategy \
#     -t ghcr.io/eth-quant-research-group/<image-name>:latest \
#     --push .
#
# Always use buildx with an explicit --platform, never plain `docker build`
# — a plain build only targets whatever architecture you're building ON,
# which silently produces an arm64-only image on Apple Silicon that then
# fails with "exec format error" on an amd64 deploy host. --push is
# required for multi-platform builds; they can't be --load-ed locally.
#
# This is a manual, deliberate action — nothing in this repo auto-builds
# or auto-pushes on a git push.

FROM python:3.11-slim

# git is required by `uv sync` to fetch the infrastructure and lighter-sdk
# dependencies, both pinned to git sources in pyproject.toml.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Everything else needed to run — strategy code, model weights, whatever
# else the strategy loads at runtime — lives in this folder and ships here.
COPY . .

ARG STRATEGY_NAME
ENV STRATEGY_NAME=${STRATEGY_NAME}
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "workers.strategy_worker"]
