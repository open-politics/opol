#! /usr/bin/env bash

# Let the DB start
python backend_pre_start.py

# Migrate
alembic stamp head
alembic revision --autogenerate -m "Initial migration"

# Migrate
alembic upgrade head