FROM python:3.11-slim

RUN apt-get update && apt-get install -y git

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

RUN pip install uv

COPY requirements.txt .

RUN uv pip install -r requirements.txt

