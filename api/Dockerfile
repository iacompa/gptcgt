FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the api requirements first (for better Docker layer caching)
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (api/ + shared src/)
COPY api/ /app/api/
COPY src/ /app/src/

ENV PYTHONPATH=/app
EXPOSE 8000

# Start FastAPI using uvicorn, but run migrations first
CMD ["sh", "-c", "python api/scripts/01_migration_teams_rbac.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
