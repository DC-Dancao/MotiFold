# syntax=docker/dockerfile:1
# ================= BASE STAGE =================
# Common system setup shared by every downstream stage.
FROM python:3.13-slim AS base

# curl is needed at runtime for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Create a non-root user used by all runtime stages.
RUN useradd -m appuser

# ================= DEPS STAGE =================
# Install runtime Python dependencies once. Shared by prod / migration / dev.
# The uv cache mount makes incremental rebuilds nearly instant.
FROM base AS deps

COPY pyproject.toml .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

# ================= APP STAGE =================
# Copy application source once on top of deps. Reused by prod/migration.
FROM deps AS app

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs
USER appuser

# ================= PROD STAGE =================
FROM app AS prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ================= MIGRATION STAGE =================
# Same layers as prod, only the default CMD differs. BuildKit reuses everything.
FROM app AS migration
CMD ["alembic", "upgrade", "head"]

# ================= DEV STAGE =================
# Adds dev-only dependencies (pytest, watchfiles, httpx, ...) on top of deps.
FROM deps AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml --group dev

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Intentionally NOT switching to `appuser` here.
# The dev compose bind-mounts ./backend over /app, exposing host UID/GID to
# the container. Running dev as root sidesteps the UID-coordination dance
# entirely; files created from inside the container (rare in normal edit-on-
# host workflows) will be root-owned on the host. Production inherits from
# the `app` stage which DOES drop to appuser.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
