#!/usr/bin/env bash

# check that HUGGINGFACE_TOKEN in .env.local is set
HUGGINGFACE_TOKEN=$(grep -oP 'HUGGINGFACE_TOKEN=\K[^ ]+' .env.local)
if [ -z "$HUGGINGFACE_TOKEN" ]; then
  echo "HUGGINGFACE_TOKEN is not set. It's needed for the embedding model, we will fade requiring any additional api keys out of the stack."
  exit 1
fi

# needed when publishing, currently using
# docker compose -f compose.local.yml up -d

pip install -q prefect

unset PREFECT_API_URL

docker compose -f compose.flows.yml up -d

prefect config set PREFECT_API_URL="http://localhost:4200/api"

prefect --no-prompt deploy --all

prefect deployment run 'meta-flow/meta'

prefect deployment run 'scrape-newssites-flow/scraping'

prefect deployment run 'extract-entities-flow/entities'

