FROM python:3.11-slim AS base

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

# Install only necessary packages and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/service-embeddings/requirements.txt .
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/.

# Copy application code
COPY ../../core/ ./core
COPY services/service-embeddings/main.py .

# Use uvicorn to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "0420"]