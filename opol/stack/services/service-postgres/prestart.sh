#! /usr/bin/env bash

# Let the DB start
python backend_pre_start.py

# Migrate
# alembic stamp head
# alembic revision --autogenerate -m "Rename thematic_locations to top_locations in ContentEvaluation"

# Migrate
alembic upgrade head