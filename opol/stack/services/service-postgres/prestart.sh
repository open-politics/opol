#! /usr/bin/env bash

# Let the DB start
python backend_pre_start.py

# Migrate
# alembic stamp head
# alembic revision --autogenerate -m "Baseline Migration"

# Migrate
alembic upgrade head