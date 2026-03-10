FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from the canonical project metadata.
# Hub proof execution requires the dev toolchain in this image.
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN pip install --no-cache-dir ".[dev]"

# Copy application code (api/)
COPY api/ /app/api/

ENV PYTHONPATH=/app
EXPOSE 8000

# Start FastAPI using uvicorn, but run migrations first
CMD ["sh", "-c", "python api/migrations/run_migration.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
