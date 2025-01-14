#! /usr/bin/env bash

# Let the DB start
python backend_pre_start.py

# Run migrations 
# alembic revision --autogenerate -m "V 0.4 Baseline Migration"

# # Migrate
alembic upgrade head