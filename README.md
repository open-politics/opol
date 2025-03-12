![opol](.github/media/opol.png)

**Opol** is the beating heart of [*The Open Politics Project*](https://github.com/open-politics/open-politics) — a high-tech stack of efficiently operationalized and modular data methods integrated into a suite of tools for data-driven political analysis.

Our mission is to illuminate the dense web of politics, geopolitics, economics, and legislation through the systematic collection and analysis of open source intelligence. By building a foundation of modular, interconnected data operations, we're not just processing information — we're aiming to help architect the technological infrastructure of a more transparent, comprehensible, and genuinely more democratic future.

All of our methods and principles are laid out in more detail on our [homepage](https://open-politics.org) and upcoming academic work. Especially all the patterns around classification schemes and reranking will need a comprehensive public discussion. Until we have set up such conversation framework please create a GitHub issue or contact us via mail at engage@open-politics.org for any questions.

![OPP Webapp with Opol data](.github/media/opol-data-on-globe.png)
Opol serves the data for the interactive globe visualization in the [Open Politics web application](https://github.com/open-politics/open-politics) displaying news articles processed through LLM classification, entity extraction, and geocoding for spatial representation

## Table of Contents
- [Introduction](#introduction)
- [Repository Overview](#repository-overview)
- [Features](#features)
- [Quickstart](#quickstart)
- [Example Usage](#example-usage)
- [Data Coverage](#data-coverage)
- [Data Privacy & Security](#data-privacy--security)
- [Further Documentation](#further-documentation)
- [Contributing](#contributing)
- [License](#license)

## Repository Overview
This repository (named opol) contains two core components:

### Python Client
A user-friendly interface to interact with the Opol engine. You can install it from PyPI (`pip install opol`) and integrate it in your Python scripts or Jupyter notebooks.

### The Stack
A Docker + FastAPI microservice stack orchestrated by Prefect. It powers the ingestion, transformation, classification, geocoding, and search functionalities.

For advanced usage, environment configurations, and microservice definitions, see the [opol/stack documentation.](/opol/stack/README.md)

## Features
opol serves as a toolkit to streamline the full lifecycle of the most common data needs of open source (political) intelligence operations.

- **Data Ingestion & Scraping**: Automate the collection of diverse data sources, including news, economic metrics, polls, and legislation across multiple regions.

- **Search Capabilities**: 
  - **Semantic Search**: Vector-based similarity search using document embeddings stored in pgvector
  - **Structured Retrieval**: via SQL like over Entities, Locations, Core Classifications
  - **Meta-Search Integration**: Access to multiple search engines (Google, DuckDuckGo, Wikipedia, etc.) through SearXng

- **Natural Language Processing**:
  - **LLM Classifications**: Leverage large language models to categorize, annotate and classify documents with various types like topics, quotes and relevance scores
  - **Embeddings**: Generate vector embeddings for semantic search and advanced NLP tasks
  - **Reranking**: Enhance search result relevance through semantic similarity scoring

- **Entity Recognition & Geocoding**: 
  - Identify key entities (people, locations, organizations)
  - Convert geographical references into latitude-longitude coordinates for geospatial analysis

- **Data Storage & Management**:
  - **Vector Database**: pgvector implementation for efficient text similarity queries
  - **SQL Database**: Manage article metadata, including topics, entities, classification scores, and events

- **Orchestration & Workflow Management**: 
  - Prefect for scalable, isolated batch processing
    - Prefect excels at the handling of complex data pipelines with monitoring and retry capabilities

- **Live Services & API Integration**: 
  - FastAPI python microservices
  - Geospatial utilities for generating GeoJSON 
  - Local LLMs via Ollama

- **Extensibility & Customization**: Easily add new data sources, classification schemes, or transformation methods
(This is a lie, it's super hardcoded)

> We are aiming to build in OWLER from the [OWS project](https://dashboard.ows.eu/) It should help facilitate easier configuration of large-scale scrape jobs

## Quickstart
There are two main ways to get started with Opol:

### 1. Use the Python Client Only

Install the client library to interact with our hosted services:

```bash
pip install opol
```

### 2. Run the Full Stack Locally

Clone and boot the entire Opol infrastructure locally:

```bash
git clone https://github.com/open-politics/opol.git

cd opol/opol/stack

cp .env.local .env

docker compose -f compose.local.yml up --build -d

bash boot-local.sh
```

This will give you access to:
- Dashboard at http://localhost:8089/dashboard
- Full infrastructure including Ollama, Geocoder, Scraping & Entity Extraction Pipelines

**Note:** Running the full stack locally requires approximately 32GB of RAM.

## Example Usage
Here are some quick code samples to showcase what Opol can do:

**Fetch articles:**

```python
from opol import OPOL

opol = OPOL(mode="local") # Use "local" to connect to your local stack, or default to remote
articles = opol.articles.get_articles(query="apple")
for article in articles:
    print(article) # or print(article['title])
```

**Render events as GeoJSON for a specified event type:**

```python
geojson = opol.geo.json_by_event("War", limit=5)
print(geojson)
# Returns a FeatureCollection with geometry & properties
```

**Geocode a location:**

```python
location = "Berlin"
coordinates = opol.geo.code(location)["coordinates"]
# [13.407032, 52.524932]
print(coordinates)
```

**Fetch Economic Data (OECD):**

```python
econ_data = opol.scraping.economic("Italy", indicators=["GDP"])
print(econ_data)
```

**Get Summarized Poll Data:**

```python
polls = opol.scraping.polls("Germany", summarised=True)
for poll in polls:
    print(f"Party: {poll['party']}, Percentage: {poll['percentage']}")
```

## Data Coverage
Because global coverage is huge, we focus on building reliable, modular methods that can be extended to new geographies and data sets. Current efforts are aimed at:

- **Germany and the European Union (EU)**:
  - Legislative data (Bundestag, EU Parliament)
  - Economic and polls
- **International**:
  - Focus on the Middle East, Eastern Europe, Africa, and Asia for major geopolitical news
  - OECD-based economic data ingestion (e.g., GDP and GDP Growth)

We encourage public contributions to add new sources, modules, or classification schemes—ensuring transparency and accountability in how and what we collect.

## Data Privacy & Security
This is a short note since in no part of our architecture we have embedded tracking or analytics of any sorts (which we invite you to proof-read in our codebase).

## Further Documentation

[**Opol Stack:**](opol/stack/README.md) For details on microservices, flows, environment variables, and more, head to the opol/stack directory.

[**Data Structure:**](opol/stack/core/models.py) Implementation references for news source content, [classification schemes](opol/stack/core/classification_models.py), entity extraction, etc.

[**Notebook Examples:**](opol/python-client/prototype.ipynb) Jupyter Notebook Prototype demonstrating typical usage scenarios.

## Contributing
We're building Opol as a community-driven project. Whether you're a developer, data scientist, political researcher, or simply interested in public intelligence operations, you're welcome to contribute. Please open an Issue or Pull Request with your ideas and improvements.

How you can help:

- Add new scrapers for different news sites or legislative data
- Propose or refine classification prompts
- Improve data coverage for less represented countries
- Contribute to documentation, scripts, or code

## License
Opol is released under the MIT License. You're free to use, modify, and distribute this software in any personal, academic, or commercial project, provided you include the license and its copyright notice.