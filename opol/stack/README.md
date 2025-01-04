# Opol Stack

### Welcome to the Opol Stack documentation!

#### This guide provides an overview of the services, tasks, and flows used to orchestrate this data operation. Whether you're a developer looking to contribute or an enthusiast eager to understand the system, this documentation aims to help you navigate and comprehend the architecture effectively.
#### If something is unclear, missing documentation, or unnecessarily hard to get into, please let us know via a GitHub Issue.

--- 
| Note |  |
|------|-------------|
| This documentation concentrates on the **stack**. If you want to learn more about the python client used to interact with the stack please visit [this page](../python-client/README.md) |

## Table of Contents
- Overview
- Directory Structure
- Environment Configuration
- Service Orchestration
  - Docker Compose Files
  - Services
  - Flows
- Flow Orchestration
  - List of Flows & Pipelines
- Service Configuration
- Observability
- Setup and Deployment
- Contribution Guidelines
- Resources

## Overview
#### This `opol/opol/stack` directory is at the heart of the application, responsible for orchestrating various microservices and workflows essential for the system's functionality. It is as-is ready to use with docker compose on your local machine.
(*In it's advanced form it is deployed as a kubnetes cluster deployed with helm. For more information look into [here](../../.deployment)*)


## Directory Structure

| File/Directory          | Description                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| **README.md**           | You are here                                                                |
| **.store**             | Store for scraped data, geocoding data, and redis queue storage              |
| **compose.local.yml**   | Compose File using a local Prefect server                                    |
| **compose.yml**         | Development Compose File                                                    |
| **core**                | Service package, holding pydantic models, URL mappings, database connections |
| **flows**               | Batch processing flows: scraping, geocoding, entities, classification, embeddings |
| **services**            | Services, mostly used for live requests: scraping, geocoding, embeddings .. + a dashboard |
| **prefect.yaml**        | Prefect Flow File for local docker work pool                                |
| **prefect-k8s.yaml**   | Prefect Flow File for Kubernetes work pool                                       |
| **register-k8sflows.sh** | Script to register flows to Kubernetes work pool |
| **register-flows.sh**     | Script to register flows to local docker work pool | 


![Stack with Flows Architecture](../../.github/media/stackwithflowarchitecture.png)


## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/open-politics/opol.git
cd opol/opol/stack
```

### 2. Setup Environment

The `.env.example` file serves as a template, outlining the required variables without exposing sensitive information. Ensure you populate the `.env` file with the necessary configurations before deploying the stack. \
Run:
```bash
mv .env.example .env
```
#### Once this is done you have two options to boot up the stack:

##### 2.1 Full Stack (services + flows)
This is the stack we use. Apart from the env variables below you need to set up a Prefect account and add the API Key to the env file.
Furthermore you need to set up Google Generative AI (as long as Google is the only provider set up )
You need to set at least these env variables:
1. Prefect Account ID, Workspace ID and API Key (on non-local stack) 
   - This connects flow code, dependencies and infra (docker in this case)
2. Google Generative Studio API Key.
   - This is used for the classification service.

##### 2.2 Light Variant
No need to set any env variables. You can just use the services without flows. But there won't be any scraping happening.
So you can only use:
- SearXNG Engine Search (results = opol.search.engine(query)
- Embeddings (embeddings = opol.embeddings.get(text))
- Geocoding (geocode = opol.geo.code(address))

🚧 The full local stack setup needs some refactoring and testing:
The full local setup is still in works. Ollama is already set up to serve as a classifier instead of Google's LLMs.
Together with the local version this should be ready to work fully local.


### 3. Start the stack
Run:
```bash
docker compose up --build
```

### ✅ Done! Opol is ready to work
Now you can:   
- Visit the dashboard at `http://localhost:8089`
- Use it as local opol instance by setting the mode to local:
   ```python
   from opol import OPOL

   opol = OPOL(mode="local) # no api key needed
   ```

*Just give it some time to populate the data. For every 10 sources specified it should take about 20 Minutes to load everything into system (on a 32GB Ram Machine).*




## Service & Flow Orchestration
### Services
The opol-services (services, engines & databases) form the backbone of the application, handling functionalities like data scraping, engineering, batch processing and various utitlies centered around opol.

| All these services and packages build services with shared modules from `core`. \
| Here you can find the shared pydantic models, service-url-mappings, database connections and more.

| The scraped data/ database files are stored in stack/.store

Databases & Queues:
- PostgreSQL Database (`database-articles`)
- Redis Server (`redis`)
- Prefect Server (`prefect_server`)

Services:
- Opol Dashboard/ Core App (`app`)
- Scraping Service (`scraping_service`)
- Geocoding Service (`geocoding_service`)
- Embeddings Service (`embedding_service`)
- Entities Service (`entities_service`)
- Classification Service (`classification_service`) (deprecated in favor of direclty implementing classification capabilities in the opol package with instructor)

Utilities:
- Ollama Server (`ollama`) # For local LLMs
- Pelias Placeholder (`pelias_placeholder`) # For local geocoding
- SearXng # Self hostable search engine for many popular providers (Arxiv, DuckDuckGo)

### Flows
If you boot up the stack, the prefect worker will start up and create a workpool "docker-pool". \
Register the flows with the deploy-flows.sh:
```bash
bash deploy-flows.sh
```
This registers/ deploys the flows. Once they are registered the worker in the docker stack will look for jobs in that pool, like a pub/sub topic. When the worker recieves a new job, it will start a container with the image specified in the flow and execute the flow according the the entrypoint.
Except for the entities flow most flows share a lot of dependencies. That is why the base-worker image is used for most of the flows.

You can use your docker images or start building your own and adding your flow code definitions in the flows folder.
Invoke them in the prefect.yaml. 
Make sure that how the file is mounted in the docker container e.g. "flows/classification/classification_flow.py" is identical to from where locally the prefect.yaml is executed/ deployed from (run bash deploy-flows.sh from opol/stack).

#### Note on development
If you want to develop on flows you have to do a few things:
1. Set up your own prefect cloud account or spin up a local server
2. Build and push the images you need to use for the flows.
3. Start a work pool in prefect cloud or locally.
4. Register the flows with the register-flows.sh script. (Make sure that the first part of the entrypoint path exist relative from the prefect.yaml file - this means you flow code needs to be in this repo under flows/ somewhere.)


### Core Flows
#### Main Ingestion Flow

The primary ingestion flow follows this sequence:

0. **Orchestration Flow**

1. **Scraping** 
2. **Embeddings** 
3. **Entities** 
4. **Geocoding** 
5. **Classification** 

Each of these sequences is a single flow. 

#### Flow Mechanics

There are two mechanics:
1. The **Orchestration Flow** triggers these endpoints regularly:
- **Postgres Service:**
  1. **Create Jobs:** Push jobs to `unprocessed_**pipeline_name**` Redis queue.
  2. **Save Results:** Retrieve results from `processed_**pipeline_name**` Redis queue.

2. The **Processing Flows** are run on schedules, but can also manually be triggered with prefect commands:


#### Flow Execution

- Each flow is initiated within containers, launching a long-running Prefect `serve` deployment.
- Upon triggering (via HTTP API or Prefect command), the flow checks Redis for pending jobs and processes them accordingly.

#### Orchestration Flow

The orchestration flow is crucial for:


**Example Orchestration Sequence:**

1. **Trigger:** Orchestration Flow initiates.
2. **Job Creation:** Postgres Service creates embedding jobs for content lacking embeddings.
3. **Queue Management:** 
   - Redis Queue receives content without embeddings.
   - Embedding Flow processes and updates the queue with content containing embeddings.
4. **Result Saving:** Postgres Service saves the processed embeddings.



This orchestration flow acts as an overcomplicated cron job, But it allows the flexibility to dynamically add more comprehensive orchestration mechanisms through HTTP requests.


## Flow Orchestration
Flows are defined using Prefect, enabling asynchronous and structured workflow management.

Read more in the flows [README](flows/README.md)

## Observability
Prefect provides observability features, offering insights into task execution and resource orchestration.

## Setup and Deployment

### Prerequisites
- Docker: Ensure Docker is installed on your system.
- Docker Compose: Required for orchestrating services.

### Steps
1. Clone the Repository
2. Configure Environment Variables
   - Duplicate `.env.example` to `.env`
   - Populate the `.env` file with necessary values.
3. Build and Start Services
   - For local development: `docker compose -f compose.local.yml up --build`
   - For production: `docker compose -f compose.yml up --build`
4.
## Resources
- Prefect Documentation: [https://docs.prefect.io/](https://docs.prefect.io/)
- Docker Documentation: [https://docs.docker.com/](https://docs.docker.com/)
- SQLModel Documentation: [https://sqlmodel.tiangolo.com/](https://sqlmodel.tiangolo.com/)
- Open Politics Documentation: [https://docs.open-politics.org/](https://docs.open-politics.org/) (But this documentation in the repo here is always newer)

