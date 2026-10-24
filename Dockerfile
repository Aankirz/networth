# Networth server for Maritime: one container, $PORT, GET /health, state in /data.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY networth ./networth
RUN uv sync --frozen --no-dev

ENV DATA_DIR=/data \
    PORT=8080
EXPOSE 8080

CMD ["/app/.venv/bin/python", "-m", "networth.app"]
