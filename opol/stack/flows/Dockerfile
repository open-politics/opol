FROM python:3.11-slim

RUN apt-get update && apt-get install -y git

WORKDIR /app

ENV PYTHONPATH="${PYTHONPATH}:/app"

ENV UV_SYSTEM_PYTHON=1

COPY ./core ./core

RUN pip install uv

COPY ./flows/requirements.txt .

RUN uv pip install -r requirements.txt

COPY ./flows ./flows

COPY ./services/service-scraper/tasks /app/tasks/

COPY ./services/service-scraper/news_sites /app/news_sites/


