import logging
from prefect import flow, task, serve
import httpx
import asyncio
from redis.asyncio import Redis
from core.service_mapping import ServiceConfig

logger = logging.getLogger(__name__)
config = ServiceConfig()

# ======================
# Task Definitions
# ======================

@task
async def produce_flags(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        logger.info(f"Producing flags from {config.service_urls['service-postgres']}")
        response = await client.get(f"{config.service_urls['service-postgres']}/flags")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to produce flags")
    return response.status_code == 200

@task
async def scrape_sources(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-scraper']}/create_scrape_jobs", timeout=700)
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to create scrape jobs")
    return response.status_code == 200

@task
async def store_raw_contents(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/store_raw_contents")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to store raw contents")
    return response.status_code == 200

@task
async def deduplicate_contents(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/deduplicate_contents")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to deduplicate contents")
    return response.status_code == 200

@task
async def create_embedding_jobs(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/create_embedding_jobs")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to create embedding jobs")
    return response.status_code == 200

@task
async def generate_embeddings(batch_size: int = 50, raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-embeddings']}/generate_embeddings",
            params={"batch_size": batch_size},
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to generate embeddings")
    return response.status_code == 200

@task
async def store_contents_with_embeddings(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/store_contents_with_embeddings")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to store contents with embeddings")
    return response.status_code == 200

@task
async def create_entity_extraction_jobs(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-postgres']}/create_entity_extraction_jobs",
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to create entity extraction jobs")
    return response.status_code == 200

@task
async def extract_entities(batch_size: int = 50, raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-entities']}/extract_entities",
            params={"batch_size": batch_size},
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to extract entities")
    return response.status_code == 200

@task
async def store_contents_with_entities(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/store_contents_with_entities")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to store contents with entities")
    return response.status_code == 200

@task
async def create_geocoding_jobs(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-postgres']}/create_geocoding_jobs",
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to create geocoding jobs")
    return response.status_code == 200

@task
async def geocode_contents(batch_size: int = 50, raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-geo']}/geocode_contents",
            params={"batch_size": batch_size},
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to geocode contents")
    return response.status_code == 200

@task
async def store_contents_with_geocoding(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/store_contents_with_geocoding")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to store contents with geocoding")
    return response.status_code == 200

@task
async def create_classification_jobs(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['service-postgres']}/create_classification_jobs",
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to create classification jobs")
    return response.status_code == 200

@task
async def classify_contents(batch_size: int = 50, raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(
            f"{config.service_urls['classification-service']}/classify_contents",
            params={"batch_size": batch_size},
            timeout=700
        )
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to classify contents")
    return response.status_code == 200

@task
async def store_contents_with_classification(raise_on_failure=True):
    async with httpx.AsyncClient(timeout=1000) as client:
        response = await client.post(f"{config.service_urls['service-postgres']}/store_contents_with_classification")
    if response.status_code != 200 and raise_on_failure:
        raise Exception("Failed to store contents with classification")
    return response.status_code == 200

# ======================
# Flow Definitions
# ======================

@flow(name="save-raw-contents-flow")
async def save_scraped_contents():
    try:
        await store_raw_contents()
    except Exception as e:
        logger.error(f"Error saving scraped contents: {e}")
        raise e

@flow(name="save-contents-with-embeddings-flow")
async def save_contents_with_embeddings_flow():
    try:
        await store_contents_with_embeddings()
    except Exception as e:
        logger.error(f"Error saving contents with embeddings: {e}")
        raise e

@flow(name="save-contents-with-entities-flow")
async def save_contents_with_entities_flow():
    try:
        await store_contents_with_entities()
    except Exception as e:
        logger.error(f"Error saving contents with entities: {e}")
        raise e

@flow(name="save-geocoded-contents-flow")
async def save_geocoded_contents_flow():
    try:
        await store_contents_with_geocoding()
    except Exception as e:
        logger.error(f"Error saving geocoded contents: {e}")
        raise e

@flow(name="save-contents-with-classification-flow")
async def save_contents_with_classification_flow():
    try:
        await store_contents_with_classification()
    except Exception as e:
        logger.error(f"Error saving contents with classification: {e}")
        raise e

@flow(name="create-jobs-flow")
async def create_jobs_flow():
    try:
        # Schedule all job creations
        await produce_flags()
        await create_embedding_jobs()
        await create_entity_extraction_jobs()
        await create_geocoding_jobs()
        await create_classification_jobs()
    except Exception as e:
        logger.error(f"Error in create_jobs_flow: {e}")
        raise e
    
@flow(name="save-all-flows")
async def save_all_flows():
    try:
        await save_scraped_contents()
        await save_contents_with_embeddings_flow()
        await save_contents_with_entities_flow()
        await save_geocoded_contents_flow()
        await save_contents_with_classification_flow()
    except Exception as e:
        logger.error(f"Error in save_all_flows: {e}")
        raise e

# ======================
# Deployment Definitions
# ======================

@flow(name="meta-flow")
async def meta_flow():
    await create_jobs_flow()
    await save_all_flows()
