FROM python:3.13-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .python-version ./

# Create a non-root user
RUN useradd -m appuser

# ================= PROD STAGE =================
FROM base AS prod

# Install dependencies into the system environment
RUN uv pip install --system -r pyproject.toml

# Copy the rest of the application
COPY --chown=appuser:appuser . .

USER appuser

# Default command (can be overridden by compose.yaml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ================= DEV STAGE =================
FROM base AS dev

# Install dependencies including dev dependencies
RUN uv pip install --system -r pyproject.toml --group dev

# Copy the rest of the application
COPY --chown=appuser:appuser . .

USER appuser

# Default command for dev mode
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

