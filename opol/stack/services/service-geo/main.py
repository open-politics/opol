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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> dict:
        """
        Generate a GeoJSON FeatureCollection based on the provided filters.
        Query strategy: top locations → date range → event type (optional)
        
        If date range is not specified, defaults to the last 7 days.
        """
        # If both dates are None, default to last 7 days
        if start_date is None and end_date is None:
            end_date = datetime.now(timezone.utc).isoformat()
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        # If only end_date is None, default to now
        elif end_date is None:
            end_date = datetime.now(timezone.utc).isoformat()
        # If only start_date is None, default to 7 days before end_date
        elif start_date is None:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
            start_date = (end_dt - timedelta(days=7)).isoformat()

        # Log the final date range
        self.logger.info(f"Using date range: {start_date[:19]} to {end_date[:19]}")

        # Base query always filters for top locations, valid coordinates, and date range
        location_query = (
            select(Location)
            .options(
                selectinload(Location.contents).selectinload(Content.evaluation),
                selectinload(Location.contents).selectinload(Content.entities)
            )
            .join(
                ContentLocation, ContentLocation.location_id == Location.id
            )
            .join(
                Content, Content.id == ContentLocation.content_id
            )
            .where(
                Location.coordinates != None,
                ContentLocation.is_top_location == True,
                Content.insertion_date >= start_date,
                Content.insertion_date <= end_date
            )
            .order_by(Content.insertion_date.desc())
            .limit(limit)
        )

        # Add event type filter if specified
        if filter_event_type:
            location_query = location_query.join(
                ContentEvaluation, ContentEvaluation.content_id == Content.id
            ).where(
                ContentEvaluation.event_type == filter_event_type
            )

        result = await self.session.execute(location_query)
        locations = result.scalars().unique().all()
        self.logger.info(
            f"Retrieved {len(locations)} locations from the DB, "
            f"filter_event_type={filter_event_type}, "
            f"date_range={start_date[:10]} to {end_date[:10]}"
        )

        features = []
        for loc in locations:
            if loc.coordinates is not None and len(loc.coordinates) == 2:
                coords = [float(c) for c in loc.coordinates]
                
                contents_list = []
                for content in loc.contents:
                    # Double-check date filter on content level
                    if (content.insertion_date < start_date or content.insertion_date > end_date):
                        self.logger.debug(f"Skipping content ID {content.id} outside date range: {content.insertion_date}")
                        continue
                    
                    # Double-check event type filter on content level if needed
                    if filter_event_type and content.evaluation and content.evaluation.event_type != filter_event_type:
                        self.logger.debug(f"Skipping content ID {content.id} due to event type mismatch: {content.evaluation.event_type}")
                        continue

                    # Process content as before
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

                    top_entities = [ent.name for ent in content.entities if getattr(ent, 'is_top', False)]

                    contents_list.append({
                        "content_id": str(content.id),
                        "title": content.title,
                        "url": content.url,
                        "source": content.source,
                        "insertion_date": content.insertion_date,
                        "classification": record_eval,
                        "top_entities": top_entities,
                    })

                # Only create feature if there are contents in the specified range
                if contents_list:
                    feature = Feature(
                        geometry=Point(coords),
                        properties={
                            "location_id": str(loc.id),
                            "location_name": loc.name,
                            "location_type": loc.location_type,
                            "content_count": len(contents_list),
                            "contents": contents_list,
                        }
                    )
                    features.append(feature)
                else:
                    self.logger.debug(f"No valid contents for location ID {loc.id} after filtering")
            else:
                self.logger.warning(f"Invalid coordinates for location ID {loc.id}: {loc.coordinates}")

        return FeatureCollection(features)

@app.get("/dynamic_geojson")
async def get_dynamic_geojson(
    event_type: Optional[str] = Query(None, description="If set, filter by event_type"),
    start_date: Optional[str] = Query(None, description="ISO formatted start date, defaults to 7 days ago if both dates are unspecified"),
    end_date: Optional[str] = Query(None, description="ISO formatted end date, defaults to now if unspecified"),
    limit: int = Query(100, description="Maximum number of locations to return"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get dynamic GeoJSON, optionally filtering by event_type and date range.
    If no date range is specified, defaults to the last 7 days.
    Cache temporarily removed for troubleshooting.
    """
    # Handle date defaults
    if start_date is None and end_date is None:
        # Default to last 7 days
        end_date = datetime.now(timezone.utc).isoformat()
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        logger.info(f"No date range specified, defaulting to last 7 days: {start_date[:10]} to {end_date[:10]}")
    elif end_date is None:
        # Default end date to now
        end_date = datetime.now(timezone.utc).isoformat()
    elif start_date is None:
        # Default start date to 7 days before end date
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
            start_date = (end_dt - timedelta(days=7)).isoformat()
        except ValueError:
            logger.error(f"Invalid end_date format: {end_date}")
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS+00:00)")

    # Validate date order
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00') if 'Z' in start_date else start_date)
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
        
        if start_dt > end_dt:
            logger.warning(f"Start date {start_date} is after end date {end_date}, swapping them")
            start_date, end_date = end_date, start_date
    except ValueError as e:
        logger.error(f"Date parsing error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}. Use ISO format.")

    try:
        # Create manager and generate fresh data (no cache)
        manager = GeoManager(session)
        logger.info(f"Generating fresh GeoJSON with filters: event_type={event_type}, date_range={start_date[:10]} to {end_date[:10]}")
        
        feature_collection = await manager.generate_geojson(
            filter_event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        return JSONResponse(content=feature_collection)
    except Exception as e:
        logger.error(f"Error generating dynamic GeoJSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/geojson_events")
async def get_geojson_events(
    event_type: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100, 
    session: AsyncSession = Depends(get_session)
):
    return await get_dynamic_geojson(
        event_type=event_type, 
        start_date=start_date,
        end_date=end_date,
        limit=limit, 
        session=session
    )

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