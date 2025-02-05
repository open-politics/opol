from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from geojson import Feature, FeatureCollection, Point
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload
from uuid import UUID
import logging
import pickle
import json
import requests
from datetime import datetime, timezone, timedelta
    
from core.adb import get_session, get_redis_url
from core.models import Location, Content, Entity, ContentLocation, ContentEvaluation
from redis import Redis
from sqlalchemy import and_
from core.utils import logger
from core.service_mapping import ServiceConfig

from pydantic import BaseModel
from typing import Union

config = ServiceConfig()

CACHE_EXPIRY = timedelta(minutes=15)
LAST_WARM_KEY = "geojson_last_warm"

def lifespan(app: FastAPI):
    logger.info("Starting lifespan")
    yield
    logger.info("Stopping lifespan")

app = FastAPI(lifespan=lifespan)


def get_redis_cache():
    return Redis.from_url(get_redis_url(), db=5)

# Pydantic Models for Serialization
class Classification(BaseModel):
    event_type: Optional[str]
    event_subtype: Optional[str]
    sociocultural_interest: Optional[int]
    global_political_impact: Optional[int]
    regional_political_impact: Optional[int]
    global_economic_impact: Optional[int]
    regional_economic_impact: Optional[int]

class ContentProperties(BaseModel):
    content_id: str
    title: Optional[str]
    url: Optional[str]
    source: Optional[str]
    insertion_date: Optional[str]
    classification: Optional[Classification]
    top_entities: List[str]

class LocationProperties(BaseModel):
    location_id: str
    location_name: Optional[str]
    location_type: Optional[str]
    content_count: int
    contents: List[ContentProperties]

class GeoFeature(BaseModel):
    type: str
    geometry: dict
    properties: LocationProperties

class GeoFeatureCollection(BaseModel):
    type: str
    features: List[GeoFeature]

# Defaults to 3 months back in time
class GeoManager:
    """
    A manager class to handle dynamic retrieval of content,
    generation of geojson, and caching strategies.
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logging.getLogger("GeoManager")

    async def generate_geojson(
        self,
        filter_event_type: Optional[str] = None,
        limit: int = 100
    ) -> dict:
        """
        Generate a GeoJSON FeatureCollection based on the provided filters.
        """
        # Build base query for Locations with optional event_type filtering
        location_query = select(Location).options(
            selectinload(Location.contents).selectinload(Content.evaluation),
            selectinload(Location.contents).selectinload(Content.entities)
        ).where(Location.coordinates != None).limit(limit)

        if filter_event_type:
            location_query = location_query.join(
                ContentLocation, ContentLocation.location_id == Location.id
            ).join(
                Content, Content.id == ContentLocation.content_id
            ).join(
                ContentEvaluation, ContentEvaluation.content_id == Content.id
            ).where(
                ContentEvaluation.event_type == filter_event_type,
                ContentLocation.is_top_location == True
            ).where(
                Content.insertion_date >= (datetime.now(timezone.utc) - timedelta(weeks=12)).isoformat()
            ).order_by(Content.insertion_date.desc()).limit(limit)

        result = await self.session.execute(location_query)
        locations = result.scalars().unique().all()
        self.logger.info(f"Retrieved {len(locations)} locations from the DB, filter_event_type={filter_event_type}")

        features = []
        for loc in locations:
            if loc.coordinates is not None and len(loc.coordinates) == 2:
                coords = [float(c) for c in loc.coordinates]
                
                contents_list = []
                for content in loc.contents:
                    if filter_event_type and content.evaluation and content.evaluation.event_type != filter_event_type:
                        self.logger.debug(f"Skipping content ID {content.id} due to event type mismatch: {content.evaluation.event_type}")
                        continue

                    eval_data = content.evaluation
                    record_eval = {}
                    if eval_data:
                        record_eval = {
                            "event_type": eval_data.event_type,
                            "event_subtype": eval_data.event_subtype,
                            "sociocultural_interest": eval_data.sociocultural_interest,
                            "global_political_impact": eval_data.global_political_impact,
                            "regional_political_impact": eval_data.regional_political_impact,
                            "global_economic_impact": eval_data.global_economic_impact,
                            "regional_economic_impact": eval_data.regional_economic_impact,
                        }
                        self.logger.debug(f"Evaluation data for content ID {content.id}: {record_eval}")

                    top_entities = [ent.name for ent in content.entities if getattr(ent, 'is_top', False)]

                    contents_list.append({
                        "content_id": str(content.id),
                        "title": content.title,
                        "url": content.url,
                        "source": content.source,
                        "insertion_date": content.insertion_date,
                        "classification": record_eval,
                        "top_entities": top_entities
                    })

                feature = Feature(
                    geometry=Point(coords),
                    properties={
                        "location_id": str(loc.id),
                        "location_name": loc.name,
                        "location_type": loc.location_type,
                        "content_count": len(contents_list),
                        "contents": contents_list
                    }
                )
                features.append(feature)
            else:
                self.logger.warning(f"Invalid coordinates for location ID {loc.id}: {loc.coordinates}")

        return FeatureCollection(features)

    async def warm_cache(self):
        """
        Warm up the main "all-locations" cache and some sample event types.
        """
        self.logger.info("Starting cache warm-up")
        redis_cache = get_redis_cache()
        try:
            # Generate base (all) data
            base_fc = await self.generate_geojson(filter_event_type=None, limit=1000)
            redis_cache.setex("geojson_all", CACHE_EXPIRY, pickle.dumps(base_fc))

            # Generate some example event types
            for ev_type in ["Protests", "Crisis", "Politics"]:
                ev_fc = await self.generate_geojson(filter_event_type=ev_type, limit=250)
                redis_cache.setex(f"geojson_events_{ev_type}", CACHE_EXPIRY, pickle.dumps(ev_fc))

            redis_cache.set(LAST_WARM_KEY, datetime.now(timezone.utc).isoformat())
            self.logger.info("Finished cache warm-up")
        except Exception as e:
            self.logger.error(f"Error during cache warm-up: {e}")
        finally:
            redis_cache.close()


@app.get("/dynamic_geojson")
async def get_dynamic_geojson(
    background_tasks: BackgroundTasks,
    event_type: Optional[str] = Query(None, description="If set, filter by event_type"),
    limit: int = 100,
    session: AsyncSession = Depends(get_session)
):
    """
    Get dynamic GeoJSON, optionally filtering by event_type, with an upper limit on returned contents.
    Caches the "all-locations" data if not present, or if event_type is set, generates fresh data.
    """
    redis_cache = get_redis_cache()
    manager = GeoManager(session)

    # Try retrieving from cache if no event filter
    cache_key = "geojson_all" if not event_type else f"geojson_events_{event_type}"
    try:
        if not event_type:
            cached_data = redis_cache.get(cache_key)
            if cached_data:
                # If data is stale, we can do a warm-up in background
                last_warm = redis_cache.get(LAST_WARM_KEY)
                if last_warm:
                    last_warm_time = datetime.fromisoformat(last_warm.decode())
                    if datetime.now(timezone.utc) - last_warm_time > timedelta(minutes=14):
                        background_tasks.add_task(manager.warm_cache)
                return JSONResponse(content=pickle.loads(cached_data))

        # If no cache or event_type is specified, generate fresh.
        feature_collection = await manager.generate_geojson(filter_event_type=event_type, limit=limit)

        # If no event type, store in cache to speed up subsequent calls
        if not event_type:
            redis_cache.setex(cache_key, CACHE_EXPIRY, pickle.dumps(feature_collection))

        return JSONResponse(content=feature_collection)

    except Exception as e:
        logger.error(f"Error generating dynamic GeoJSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        redis_cache.close()


@app.post("/warm_cache_now")
async def force_cache_warm_up(session: AsyncSession = Depends(get_session)):
    """
    Force an immediate warm-up of the geojson caches.
    """
    manager = GeoManager(session)
    await manager.warm_cache()
    return {"message": "Cache warmed up successfully"}



def call_pelias_api(location, lang=None):
    custom_mappings = {
        "europe": {
            'coordinates': [13.405, 52.52],
            'location_type': 'continent',
            'bbox': [-24.539906, 34.815009, 69.033946, 81.85871],
            'area': 1433.861436
        },
    }

    if location.lower() in custom_mappings:
        return custom_mappings[location.lower()]

    try:
        pelias_url = config.service_urls['pelias-placeholder']
        url = f"{pelias_url}/parser/search?text={location}"
        if lang:
            url += f"&lang={lang}"

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                top_result = data[0]
                geometry = top_result.get('geom')
                location_type = top_result.get('placetype', 'location')
                if geometry:
                    bbox = geometry.get('bbox')
                    area = geometry.get('area')
                    return {
                        'coordinates': [geometry.get('lon'), geometry.get('lat')],
                        'location_type': location_type if location_type else 'location',
                        'bbox': bbox.split(',') if bbox else None,
                        'area': area
                    }
                else:
                    logger.warning(f"No geometry found for location: {location}")
            else:
                logger.warning(f"No data returned from API for location: {location}")
        else:
            logger.error(f"API call failed with status code: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"API call exception for location {location}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error for location {location}: {str(e)}")
    return None


@app.get("/geocode_location")
def geocode_location(location: str):
    logger.info(f"Geocoding location: {location}")
    coordinates = call_pelias_api(location, lang='en')
    logger.warning(f"Coordinates: {coordinates}")

    if coordinates:
        return {
            "coordinates": coordinates['coordinates'],
            "location_type": coordinates['location_type'],
            "bbox": coordinates.get('bbox'),
            "area": coordinates.get('area')
        }
    else:
        return {"error": "Unable to geocode location"}

@app.get("/get_country_data")
def get_country_data(country):
    url = f"https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": country,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True
    }
    response = requests.get(url, params=params)
    data = response.json()
    pages = data['query']['pages']
    for page_id, page_data in pages.items():
        if 'extract' in page_data:
            return page_data['extract']
    return None


@app.get("/healthz")
def healthcheck():
    return {"message": "ok"}, 200


@app.get("/geojson_events")
async def get_geojson_events(event_type: str, limit: int = 100, session: AsyncSession = Depends(get_session), background_tasks: BackgroundTasks = None):
    return await get_dynamic_geojson(event_type=event_type, limit=limit, session=session, background_tasks=background_tasks)