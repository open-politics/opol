# Standard library imports
import os
import asyncio
import subprocess
from enum import Enum
from typing import Optional, Dict, Any

# Third-party imports
import httpx
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    BackgroundTasks,
    APIRouter,
    Path,
    Query,
    Depends,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from pydantic import BaseModel
from fastapi.logger import logger
import logging

from jinja2 import Environment, FileSystemLoader

# Local imports
from core.service_mapping import ServiceConfig
from core.utils import get_redis_url

from flows.orchestration import (
    produce_flags,
    create_embedding_jobs,
    create_entity_extraction_jobs,
    create_geocoding_jobs,
    create_classification_jobs,
    store_raw_contents,
    store_contents_with_embeddings,
    store_contents_with_entities,
    store_contents_with_geocoding,
    store_contents_with_classification,
    geocode_contents,
)

# Initialize templates
templates = Jinja2Templates(directory="templates")
config = ServiceConfig()

# FastAPI Setup
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
router = APIRouter()
app.include_router(router)
status_message = "Ready to start scraping."

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.access")
logger.setLevel(logging.WARNING)

# Global variable to store the current pool type
current_pool_type = "docker"

class PipelineManager:
    def __init__(self, config: ServiceConfig, redis_conn: Redis):
        self.config = config
        self.redis_conn = redis_conn
        self.pipelines = {
            "scraping": {
                "title": "Scraping Pipeline",
                "input": "Flags",
                "output": "Raw Contents",
                "steps": [
                    {"name": "produce_flags", "label": "1. Produce Flags"},
                    {"name": "scrape_sources", "label": "2. Scrape"},
                    {"name": "store_raw_contents", "label": "3. Store Raw Contents"},
                ],
                "channels": ["scrape_sources", "raw_contents_queue"],
            },
            "embedding": {
                "title": "Embedding Pipeline",
                "input": "Raw Contents",
                "output": "Embedded Contents",
                "steps": [
                    {"name": "create_embedding_jobs", "label": "1. Create Jobs"},
                    {"name": "generate_embeddings", "label": "2. Generate", "batch": True},
                    {"name": "store_contents_with_embeddings", "label": "3. Store"},
                ],
                "channels": ["contents_without_embedding_queue", "contents_with_embeddings"],
            },
            "entity_extraction": {
                "title": "Entity Extraction Pipeline",
                "input": "Raw Contents",
                "output": "Contents with Entities",
                "steps": [
                    {"name": "create_entity_extraction_jobs", "label": "1. Create Jobs"},
                    {"name": "extract_entities", "label": "2. Extract", "batch": True},
                    {"name": "store_contents_with_entities", "label": "3. Store"},
                ],
                "channels": [
                    "contents_without_entities_queue",
                    "contents_with_entities_queue",
                ],
            },
            "geocoding": {
                "title": "Geocoding Pipeline",
                "input": "Contents with Entities",
                "output": "Geocoded Contents",
                "steps": [
                    {"name": "create_geocoding_jobs", "label": "1. Create Jobs"},
                    {"name": "geocode_contents", "label": "2. Geocode", "batch": True},
                    {"name": "store_contents_with_geocoding", "label": "3. Store"},
                ],
                "channels": [
                    "contents_without_geocoding_queue",
                    "contents_with_geocoding_queue",
                ],
            },
            "classification": {
                "title": "Classification Pipeline",
                "input": "Processed Contents",
                "output": "Classified Contents",
                "steps": [
                    {"name": "create_classification_jobs", "label": "1. Create Jobs"},
                    {"name": "classify_contents", "label": "2. Process", "batch": True},
                    {"name": "store_contents_with_classification", "label": "3. Store"},
                ],
                "channels": [
                    "contents_without_classification_queue",
                    "contents_with_classification_queue",
                ],
            },
        }

    async def trigger_step(
        self,
        step_name: str,
        pipeline_name: str,
        batch_size: int = 50,
        pool_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        global current_pool_type
        pool_type = pool_type or current_pool_type
        logger.info(
            f"Triggering step: {step_name} in pipeline: {pipeline_name} with pool type: {pool_type}"
        )

        saving_steps = {
            "store_raw_contents": store_raw_contents,
            "store_contents_with_embeddings": store_contents_with_embeddings,
            "store_contents_with_entities": store_contents_with_entities,
            "store_contents_with_geocoding": store_contents_with_geocoding,
            "store_contents_with_classification": store_contents_with_classification,
        }

        job_creation_steps = {
            "produce_flags": produce_flags,
            "create_embedding_jobs": create_embedding_jobs,
            "create_entity_extraction_jobs": create_entity_extraction_jobs,
            "create_geocoding_jobs": create_geocoding_jobs,
            "create_classification_jobs": create_classification_jobs,
        }

        process_steps = {
            "scrape_sources": "scrape-newssites-flow/scraping",
            "generate_embeddings": "generate-embeddings-flow/embeddings",
            "extract_entities": "extract-entities-flow/entities",
            "classify_contents": "classify-contents-flow/classification",
            "geocode_contents": "geocode-locations-flow/geocoding",
        }

        if pool_type == "k8s":
            process_steps = {k: v + "-k8s" for k, v in process_steps.items()}

        try:
            if step_name in job_creation_steps:
                await job_creation_steps[step_name]()
                response_message = f"Function '{job_creation_steps[step_name].__name__}' executed successfully."
                deployment_id = None
            elif step_name in saving_steps:
                saving_function = saving_steps[step_name]
                await saving_function()  # Ensure the function is awaitable if it's async
                response_message = f"Function '{saving_function.__name__}' executed successfully."
                deployment_id = None
            elif step_name in process_steps:
                deployment_name = process_steps[step_name]
                subprocess.run(
                    ["prefect", "deployment", "run", deployment_name], check=True
                )
                response_message = f"Prefect deployment '{deployment_name}' triggered successfully."
                deployment_id = None
            else:
                raise HTTPException(
                    status_code=404, detail=f"Invalid step name: {step_name}"
                )

            return {
                "message": response_message,
                "deployment_id": deployment_id,  # Update based on actual Prefect response
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Prefect command failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to trigger Prefect deployment: {e}"
            )
        except Exception as e:
            logger.error(f"Error in trigger_step: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def flush_channels(self, pipeline_name: str) -> Dict[str, Any]:
        if pipeline_name not in self.pipelines:
            raise HTTPException(
                status_code=404, detail=f"Invalid pipeline name: {pipeline_name}"
            )

        flow_channels = self.pipelines[pipeline_name].get("channels", [])

        flushed_channels = []
        for channel_name in flow_channels:
            queue_info = self.config.redis_queues.get(channel_name)
            if queue_info:
                await self.redis_conn.select(queue_info["db"])
                await self.redis_conn.delete(queue_info["key"])
                flushed_channels.append(channel_name)

        return {
            "message": f"Flushed Redis channels for {pipeline_name}",
            "flushed_channels": flushed_channels,
        }

    async def get_channels_status(self, pipeline_name: Optional[str] = None) -> Dict[str, Any]:
        channels_status = {}
        if pipeline_name:
            if pipeline_name not in self.pipelines:
                raise HTTPException(status_code=404, detail=f"Invalid pipeline name: {pipeline_name}")
            flow_channels = self.pipelines[pipeline_name].get('channels', [])
            channels_status[pipeline_name] = {}
            for channel in flow_channels:
                queue_info = self.config.redis_queues.get(channel)
                if queue_info:
                    async with self.redis_conn.client() as redis:
                        await redis.select(queue_info["db"])
                        queue_length = await redis.llen(queue_info["key"])
                        channels_status[pipeline_name][channel] = queue_length
                else:
                    channels_status[pipeline_name][channel] = None
        else:
            # Return status for all pipelines
            for pname, pipeline in self.pipelines.items():
                flow_channels = pipeline.get('channels', [])
                channels_status[pname] = {}
                for channel in flow_channels:
                    queue_info = self.config.redis_queues.get(channel)
                    if queue_info:
                        async with self.redis_conn.client() as redis:
                            await redis.select(queue_info["db"])
                            queue_length = await redis.llen(queue_info["key"])
                            channels_status[pname][channel] = queue_length
                    else:
                        channels_status[pname][channel] = None
        return channels_status

async def get_pipeline_manager() -> PipelineManager:
    redis_conn = Redis.from_url(get_redis_url(), decode_responses=True)
    return PipelineManager(config, redis_conn)

@app.get("/pipeline/{pipeline_name}", response_class=HTMLResponse)
async def get_pipeline(
    pipeline_name: str,
    request: Request,
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    if pipeline_name not in manager.pipelines:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_name}' not found.")

    pipeline = manager.pipelines[pipeline_name]
    # Fetch current channel statuses
    channel_status = await manager.get_channels_status(pipeline_name)

    await manager.redis_conn.aclose()

    return templates.TemplateResponse(
        "partials/pipeline.html",
        {
            "request": request,
            "pipeline": pipeline,
            "pipeline_name": pipeline_name,
            "channel_status": channel_status.get(pipeline_name, {}),
            "current_pool_type": current_pool_type,
        }
    )

@app.post("/trigger_step/{pipeline_name}/{step_name}")
async def trigger_step(
    pipeline_name: str,
    step_name: str,
    batch_size: int = Query(50, ge=1, le=100),
    pool_type: Optional[str] = Query(None),
    manager: PipelineManager = Depends(get_pipeline_manager),
):
    result = await manager.trigger_step(step_name, pipeline_name, batch_size, pool_type)
    await manager.redis_conn.aclose()
    return result

@app.post("/flush_redis_channels/{pipeline_name}")
async def flush_redis_channels(
    pipeline_name: str, manager: PipelineManager = Depends(get_pipeline_manager)
):
    result = await manager.flush_channels(pipeline_name)
    await manager.redis_conn.aclose()
    return result

@app.post("/toggle_pool")
async def toggle_pool(manager: PipelineManager = Depends(get_pipeline_manager)):
    global current_pool_type
    current_pool_type = "docker" if current_pool_type == "k8s" else "k8s"
    result = {
        "message": f"Pool type switched to {current_pool_type}",
        "current_pool_type": current_pool_type,
    }
    await manager.redis_conn.aclose()
    return result

# Updated Endpoints to Handle Channel Status Checks with HTML Responses

@app.get("/check_channels/{pipeline_name}", response_class=HTMLResponse)
async def check_channels(
    pipeline_name: str, 
    request: Request, 
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    """
    Get the status of Redis queues for a specific pipeline.
    """
    try:
        status = await manager.get_channels_status(pipeline_name)
        return templates.TemplateResponse(
            "partials/channel_status.html",
            {"request": request, "channel_status": status.get(pipeline_name, {})}
        )
    except HTTPException as e:
        raise e
    finally:
        await manager.redis_conn.aclose()

@app.get("/check_channels/status", response_class=HTMLResponse)
async def check_channels_status(
    request: Request,
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    """
    Get the status of Redis queues for all pipelines and render HTML.
    """
    try:
        status = await manager.get_channels_status()
        # Flatten the status dictionary
        flattened_status = {k: v for p in status.values() for k, v in p.items()}
        return templates.TemplateResponse(
            "partials/channels_status.html",
            {"request": request, "channel_status": flattened_status}
        )
    except HTTPException as e:
        raise e
    finally:
        await manager.redis_conn.aclose()

@app.get("/check_channels/scrapers_running", response_class=HTMLResponse)
async def check_scrapers_running(
    request: Request,
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    """
    Get the status of Redis queues specifically for the Scraping pipeline and render HTML.
    """
    try:
        status = await manager.get_channels_status("scraping")
        return templates.TemplateResponse(
            "partials/scrapers_running.html",
            {"request": request, "channel_status": status.get("scraping", {})}
        )
    except HTTPException as e:
        raise e
    finally:
        await manager.redis_conn.aclose()

# Health and Monitoring
@app.get("/healthz")
async def healthcheck():
    return {"message": "OK"}

@app.get("/service_health", response_class=HTMLResponse)
async def service_health(request: Request):
    health_status = {}
    services_to_check = [
        "app-opol-core",
        "service-postgres",
        "service-embeddings",
        "service-scraper",
        "service-entities",
        "service-geo",
        "ollama",
    ]
    async with httpx.AsyncClient() as client:
        for service in services_to_check:
            url = config.service_urls.get(service)
            if url:
                try:
                    response = await client.get(f"{url}/healthz", timeout=5.0)
                    if response.status_code == 200:
                        health_status[service] = "green"
                    else:
                        health_status[service] = "red"
                except httpx.RequestError:
                    health_status[service] = "red"
            else:
                health_status[service] = "gray"
    
    return templates.TemplateResponse("partials/service_health.html", {"request": request, "service_health": health_status})

@app.get("/check_services")
async def check_services():
    service_statuses = {}
    for service, url in config.service_urls.items():
        try:
            response = await httpx.get(f"{url}/healthz", timeout=10.0)
            service_statuses[service] = response.status_code
        except httpx.RequestError as e:
            service_statuses[service] = str(e)
    return service_statuses

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("opol.html", {"request": request, "current_pool_type": current_pool_type})

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(
    background_tasks: BackgroundTasks, 
    request: Request, 
    query: str = "culture and arts"
):
    try:
        use_local_prefect_server = os.getenv("LOCAL_PREFECT", "false").lower() == "true"
        if use_local_prefect_server:
            prefect_dashboard_url = "http://localhost:4200/dashboard"
        else:
            workspace_id = os.getenv("PREFECT_WORKSPACE_ID")
            workspace = os.getenv("PREFECT_WORKSPACE")
            prefect_dashboard_url = f"https://app.prefect.cloud/account/{workspace_id}/workspace/{workspace}/dashboard"

        return templates.TemplateResponse("index.html", {
            "request": request,
            "search_query": query,
            "prefect_dashboard_url": prefect_dashboard_url,
            "current_pool_type": current_pool_type
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dashboard: {str(e)}")


@app.get("/outward_irrelevant_articles", response_class=HTMLResponse)
async def outward_irrelevant_articles(request: Request):
    try:
        postgres_service_url = f"{config.service_urls['service-postgres']}/outward_irrelevant"
        async with httpx.AsyncClient() as client:
            response = await client.get(postgres_service_url)

        if response.status_code == 200:
            articles = response.json()
            return templates.TemplateResponse("partials/outward_irrelevant_articles.html", {"request": request, "articles": articles})
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch outward/irrelevant articles")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching outward/irrelevant articles: {str(e)}")

# Helper Functions
async def setup_redis_connection():
    try:
        redis_conn = Redis.from_url(
            url=str(get_redis_url()),
            decode_responses=True
        )
        return redis_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to connect to Redis")

async def get_redis_queue_length(redis_db: int, queue_key: str):
    try:
        redis_conn = Redis(host=os.getenv('REDIS_HOST', 'redis'), port=int(os.getenv('REDIS_PORT', 6379)), db=redis_db)
        queue_length = await redis_conn.llen(queue_key)
        return queue_length
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")

class SearchType(str, Enum):
    TEXT = "text"
    SEMANTIC = "semantic"

@app.post("/clear_redis")
async def clear_redis_data():
    redis_url = get_redis_url()
    if not redis_url:
        raise HTTPException(status_code=500, detail="Could not get Redis URL")
    try:
        redis = Redis.from_url(redis_url, decode_responses=True)
        await redis.flushall()
        await redis.aclose()
        return {"message": "Redis data cleared"}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Invalid Redis URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing Redis data: {str(e)}")

async def log_redis_url():
    try:
        redis_url = get_redis_url()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Redis URL: {str(e)}")

@app.post("/log_redis_url")
async def log_redis_url_endpoint():
    await log_redis_url()
    return {"message": "Redis URL logged"}

def is_number(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

templates.env.filters['is_number'] = is_number
templates.env.tests['is_number'] = is_number
