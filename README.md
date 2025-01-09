![opol](.github/media/opol.png)

**Opol** is the beating heart of [*The Open Politics Project*](https://github.com/open-politics/open-politics) — a high-tech stack of efficiently operationalised and modular data methods. Integrated into a suite full of useful tools for data driven political analysis.


Our mission is to illuminate the dense web of politics, geopolitics, economics, and legislation through the systematic collection and analysis of open source intelligence. By building a foundation of modular, interconnected data operations, we're not just processing information — we're architecting the technological infrastructure for a more transparent, comprehensible, and genuinely democratic future.

We hope you can find some use in the tools we offer or are intruiged enough to look more closely at the code and maybe even contribute to it.

---
The Open Politics Project (and thus Opol) are built to enable. To see and measure more of what's happening right now in this maddening clusterfuck that politics is. Fully Open Source and as an asset to everyone. That is our commitment.


All of our methods and principles will be laid out in more detail on our [homepage](https://open-politics.org) and upcoming academic work. Especially all the patterns around classification schemes and reranking will need a comprehensive public discussion. Until we have set up such conversation framework please create a github issue or contact us via mail at engage@open-politics.org for any questions on this. 

## Table of Contents
- [Introduction](#introduction)
  - [What is O(P)SINT?](#what-is-opsint)
  - [Why Opol?](#why-opol)
- [Features](#features)
- [Data Coverage](#data-coverage)
- [Data Privacy & Security](#data-privacy--security)
- [This Repository](#this-repository)
  - [Python Client](#python-client)
  - [The Stack](#the-stack)
- [Quick Installation and Usage](#quick-installation-and-usage)
- [Example Usage](#example-usage)
- [Further Documentation](#further-documentation)
- [Contributing](#contributing)
- [License](#license)


## Introduction
### What is O(P)SINT?
Open Source Political Intelligence (O(P)SINT) is a specialized form of OSINT, tailored for political analysis. It integrates:

- **Data engineering** for large-scale data processing and management
- **Political science** for structuring, analyzing, and interpreting politically relevant data
- **Open-source principles** ensuring community-driven improvements, transparency, and extensibility

### Why Opol?
- **Better Data Access**: A robust platform that centralizes data from multiple sources (news, economic statistics, polls, legislation).
- **Scalable & Modular**: Microservice architecture, container-based deployment, and a flexible and highly ressource efficient pipeline orchestrated via Prefect.
- **Extendable**: Easily add your own sources, classification schemes, or transformations.
- **Transparency & Community**: This is a public intelligence operation—community contributions and reviews are welcomed.

## Features
Opol offers a comprehensive suite of tools and functionalities designed to streamline the entire data lifecycle for political intelligence:
- **Data Ingestion & Scraping**: Automate the collection of diverse data sources, including news, economic metrics, polls, and legislation across multiple regions.
- **Advanced Search & Semantic Capabilities**: Utilize a vectorized search interface powered by SearXng meta-search, supporting queries across platforms like Google, DuckDuckGo, Wikipedia, Arxiv, and YouTube.
- **Natural Language Processing**:
  - **LLM Classifications**: Leverage large language models to categorize documents with event types, topics, and relevance scores.
  - **Embeddings**: Generate vector embeddings for semantic search and advanced NLP tasks.
- **Reranking**: Enhance search result relevance through semantic similarity-based reranking.
- **Entity Recognition & Geocoding**: Identify key entities (people, locations, organizations) and convert geographical references into latitude-longitude coordinates for geospatial analysis.
- **Data Storage & Management**:
  - **Vector Database**: Implement pgvector for efficient text similarity queries.
  - **SQL Database**: Manage article metadata, including topics, entities, classification scores, and events.
- **Orchestration & Workflow Management**: Employ Prefect for scalable, isolated batch processing and live data operations, ensuring efficient handling of complex data pipelines.
- **Live Services & API Integration**: FastAPI-powered microservices offer real-time data access, embeddings generation, and contextual retrieval.
  - **Geospatial Utilities**: Tools for generating GeoJSON and integrating with SearXng for enhanced data enrichment.
- **Extensibility & Customization**: Easily add new data sources, classification schemes, or transformations to adapt to evolving analytical needs (e.g. new LLM models).

Many of these features are available as core processing element (like chunking & embedding all scraped content) and live inference (like embedding generation for queries or reranking). 

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

The webapp stores a local cookie for the user's session (json web token).
Additionally, the webapp [open-politics.org](https://open-politics.org) will **maybe** at some point use anonymized telemetry (according to open source best practices) to collect usage data on ui features and interactions for development. Maybe.

To sum up: We do not track any user data - and have no pixels or analytics.



## This Repository
This repo (named opol) contains two core components:

### Python Client
A user-friendly interface to interact with the Opol engine. You can install it from PyPI (`pip install opol`) and integrate it in your Python scripts or Jupyter notebooks.

### The Stack
A Docker + FastAPI microservice stack orchestrated by Prefect. It powers the ingestion, transformation, classification, geocoding, and search functionalities.

For advanced usage, environment configurations, and microservice definitions, see the opol/stack documentation.

## Quick Installation and Usage
Below is a minimal quickstart for local setup. For advanced usage, see the [Stack Documentation](opol/stack/README.md).

**Install the Python client:**
```bash
pip install opol
```

**Clone the Repository & Boot the Stack** to self-host: \
*(Needs ~32G of RAM)*
```bash
git clone https://github.com/open-politics/opol.git
cd opol/opol/stack
mv .env.example .env

# Boot with local Prefect server for orchestration
docker compose -f compose.local.yml up --build
```

**Use the Python client in your code**
Just switch mode="local" to connect to your local stack or use the default remote.

```python
from opol import OPOL

opol = OPOL(mode="local")
...
```

## Example Usage
Here are some quick code samples to showcase what Opol can do:

**Fetch articles:**

```python
from opol import OPOL

opol = OPOL(mode="local")
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

## Further Documentation

[**Opol Stack:**](opol/stack/README.md) For details on microservices, flows, environment variables, and more, head to the opol/stack directory.

[**Data Structure:**](opol/stack/core/models.py) Implementation references for news source content, [classification schemes](opol/stack/core/classification_models.py), entity extraction, etc.

[**Notebook Examples:**](opol/python-client/prototype.ipynb) Jupyter Notebook Prototype demonstrating typical usage scenarios.

## Contributing
We’re building Opol as a community-driven project. Whether you’re a developer, data scientist, political researcher, or simply interested in public intelligence operations, you’re welcome to contribute. Please open an Issue or Pull Request with your ideas and improvements.

How you can help:

- Add new scrapers for different news sites or legislative data
- Propose or refine classification prompts
- Improve data coverage for less represented countries
- Contribute to documentation, scripts, or code

## License
Opol is released under the MIT License. You’re free to use, modify, and distribute this software in any personal, academic, or commercial project, provided you include the license and its copyright notice.

