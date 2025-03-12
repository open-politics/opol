#!/bin/bash
set -e

# Start the server in the background
echo "Starting the server on port $GEO_SERVICE_PORT"
python run_with_logfire.py
