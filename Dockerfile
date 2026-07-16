# syntax=docker/dockerfile:1
FROM node:20-alpine AS web
WORKDIR /build/webui
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/data/home \
    XDG_CACHE_HOME=/data/cache \
    WHALE_HOME=/data \
    WHALE_WORKSPACE=/workspace \
    WHALE_HOST=0.0.0.0 \
    WHALE_PORT=8765

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 whale \
    && mkdir -p /app /data /workspace \
    && chown -R whale:whale /app /data /workspace

ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY --chown=whale:whale pyproject.toml README.md ./
COPY --chown=whale:whale src/ ./src/
COPY --chown=whale:whale --from=web /build/webui/dist/ ./src/whale_cli/web/static/
COPY --chown=whale:whale docs/新手入门/ ./src/whale_cli/web/tutorials/
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_CACHE_DIR=/root/.cache/pip python -m pip install .

USER whale
VOLUME ["/data", "/workspace"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/ready', timeout=3)"
CMD ["whale-web"]
