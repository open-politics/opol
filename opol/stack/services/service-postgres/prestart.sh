#! /usr/bin/env bash

# Let the DB start
python backend_pre_start.py

# Run migrations 
# alembic revision --autogenerate -m "Set default UUID for id column"

# # Migrate
alembic upgrade head