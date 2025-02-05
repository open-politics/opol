#!/usr/bin/env bash

# Run the tests
pytest tests/api.py

# # Wait until the postgres service is ready
# while ! nc -z postgres 5432; do
#   echo "Waiting for postgres..."
#   sleep 1
# done





# curl -X POST --max-time 600 --connect-timeout 300 "http://localhost:5434/standardize_sources"
# # Define the sources
# sources=("CNN" "DW" "BBC News")

# # Base URL for the update
# base_url="http://localhost:5434/update_articles"

# # Iterate over each source
# for source in "${sources[@]}"; do
#     # Convert source to lowercase and replace spaces with underscores for the URL
#     formatted_source=$(echo "$source" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
    
#     # Construct the URL
#     url="${base_url}?source=${formatted_source}&limit=1000000"
    
#     # Make the HTTP POST request with long timeouts
#     curl -X POST --max-time 600 --connect-timeout 300 "$url"
    
#     echo "Updated articles for source: $source"
# done


uvicorn main:app --host 0.0.0.0 --port 8089 --reload