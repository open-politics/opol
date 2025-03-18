#!/usr/bin/env bash

sudo pip install prefect

unset PREFECT_API_URL

prefect config set PREFECT_API_URL="http://localhost:4200/api"

prefect --no-prompt deploy --all

prefect deployment run 'meta-flow/meta'

prefect deployment run 'scrape-newssites-flow/scraping'

prefect deployment run 'extract-entities-flow/entities'

