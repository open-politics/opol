FROM python:3.11

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

# Install cron
# Install only necessary packages and clean up
RUN apt-get update && apt-get install -y curl git cron && \
    pip install uv

# Copy requirements file
COPY services/app/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY services/app/ .
COPY ../../core/ core
COPY flows/orchestration/ ./flows

# Copy the start script and make it executable
COPY services/app/start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]