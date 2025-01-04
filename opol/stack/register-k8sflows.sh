#! /bin/bash

echo "Registering flows with Prefect Cloud"
prefect --no-prompt deploy --prefect-file prefect-k8s.yaml --all