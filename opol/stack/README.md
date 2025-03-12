# Opol Stack

Welcome to the Opol Stack documentation! This guide provides an overview of the architecture, services, and workflows that power the Open Politics data platform.

> This documentation focuses on the **stack**. For information about the Python client, please visit [the Python client documentation](../python-client/README.md).

## Overview

The Opol Stack is a microservices architecture designed to collect, process, and analyze political data at scale. It combines real-time services with batch processing workflows to efficiently handle both immediate requests and large-scale data operations.

![Stack with Flows Architecture](../../.github/media/stackwithflowarchitecture.png)

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/open-politics/opol.git
cd opol/opol/stack
docker compose -f compose.local.yml up --build -d
```

### 2. Start the stack
```bash
bash boot-local.sh
```
This script installs dependencies, configures Prefect, deploys data pipelines, and triggers initial flows.

### 3. Access & Use Opol
- **Dashboard**: `http://localhost:8089/dashboard`
- **Python Client**:
  ```python
  from opol import OPOL
  opol = OPOL(mode="local")  # or "container"
  ```

*Note: Initial data population takes time. For every 10 sources, expect about 20 minutes to load everything (on a 32GB RAM machine).*

## Architecture

Opol uses a dual architecture pattern to efficiently handle both batch processing and live usage:

### Services Architecture

The stack is organized into five main categories:

1. **App Layer**
   - `app-opol-core`: Dashboard and API interface

2. **Services Layer**
   - `service-scraper`: Collects data from sources
   - `service-embeddings`: Generates vector embeddings
   - `service-entities`: Extracts named entities
   - `service-geo`: Provides geocoding functionality
   - `service-postgres`: Manages database operations

3. **Engines Layer**
   - `engine-ollama`: Local LLM provider
   - `engine-pelias-placeholder`: Local geocoding
   - `engine-prefect-server`: Workflow orchestration
   - `engine-redis`: Queue and cache service
   - `engine-searxng`: Self-hosted search engine

4. **Data Layer**
   - `database-articles`: Main PostgreSQL database with pgvector
   - `database-prefect`: Workflow metadata database

5. **Worker Layer**
   - `worker-prefect`: Executes workflow tasks
   - Various runner images for specific flows

### Workflow Architecture

![Prefect Dashboard](../../.github/media/prefect_dashboard.png)

Opol uses Prefect for workflow orchestration, following this sequence:

1. **Orchestration Flow** coordinates the entire pipeline
2. **Scraping Flow** collects data from sources
3. **Embeddings Flow** generates vector embeddings
4. **Entities Flow** extracts named entities
5. **Geocoding Flow** adds geographic information
6. **Classification Flow** categorizes content

This approach:
- Isolates operations in separate containers
- Schedules regular data jobs
- Monitors health and performance
- Handles retries and failures
- Scales batch processing horizontally

## Setup Options

### Full Stack
The complete stack with all features is automatically set up by the `boot-local.sh` script.

### Light Variant
If you only need core services without flows:
```bash
docker compose -f compose.local.yml up -d
```

This provides:
- SearXNG Engine Search
- Embeddings
- Geocoding

## Directory Structure

| File/Directory          | Description                                                |
|-------------------------|------------------------------------------------------------|
| **README.md**           | This documentation                                         |
| **.env.local**          | Local environment configuration                            |
| **.store**              | Data storage for scraped data, geocoding, Redis queues     |
| **boot-local.sh**       | Quick start script                                         |
| **compose.local.yml**   | Docker Compose file with local Prefect server              |
| **compose.yml**         | Development Compose file                                   |
| **core**                | Shared models, URL mappings, database connections          |
| **flows**               | Batch processing workflows                                 |
| **services**            | Microservices for live requests                            |
| **prefect.yaml**        | Prefect configuration for local Docker                     |
| **prefect-k8s.yaml**    | Prefect configuration for Kubernetes                       |
| **register-flows.sh**   | Script to register flows to local Docker work pool         |
| **register-k8sflows.sh**| Script to register flows to Kubernetes work pool           |

## Development Notes

### Working with Flows

To develop flows:
1. Set up a Prefect account or local server
2. Build and push required images
3. Start a Prefect work pool
4. Register flows with the `register-flows.sh` script

### Flow Execution

- Flows run in containers using Prefect's `serve` deployment
- The worker polls for jobs in the work pool
- When a job is received, the worker starts a container with the specified image

## Resources
- [Prefect Documentation](https://docs.prefect.io/)
- [Docker Documentation](https://docs.docker.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Open Politics Documentation](https://docs.open-politics.org/)

If something is unclear or missing, please let us know via a GitHub Issue!

