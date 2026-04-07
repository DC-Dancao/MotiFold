FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .python-version ./

# Install dependencies into the system environment
RUN uv pip install --system -r pyproject.toml

# Create a non-root user
RUN useradd -m appuser

# Copy the rest of the application
COPY --chown=appuser:appuser . .

USER appuser

# Default command (can be overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
