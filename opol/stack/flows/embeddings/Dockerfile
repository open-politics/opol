FROM python:3.11-slim AS base

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV PYTHONPATH=/app

# Install dependencies
RUN apt-get update && apt-get install -y curl git && \
    pip install uv

# Copy and install Python dependencies
COPY flows/embeddings/requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ../../core/ ./core

COPY flows/embeddings/ .