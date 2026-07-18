# Build from repo root: docker build -t continuum:local .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages/ packages/
COPY apps/ apps/

RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data

ENV CONTINUUM_DB_PATH=/app/data/continuum.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/v1/health || exit 1

CMD ["uvicorn", "continuum_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
