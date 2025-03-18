FROM python:3.11-slim AS base

WORKDIR /app/

ENV UV_SYSTEM_PYTHON=1

# Install uv for faster dependency installation
RUN pip install --no-cache-dir uv

# Copy only requirements file first to leverage Docker cache
COPY services/service-postgres/requirements.txt /app/
RUN uv pip install --no-cache-dir -r /app/requirements.txt

FROM python:3.11-slim AS runtime

WORKDIR /app/

# Set PYTHONPATH
ENV PYTHONPATH=/.

# Copy installed packages from builder stage
COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/

# Install only runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends netcat-traditional && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY services/service-postgres .
COPY ../../core/ ./core

RUN chmod +x start-reload.sh

CMD ["./start-reload.sh"]