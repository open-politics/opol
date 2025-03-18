import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Body, APIRouter
from sqlmodel import SQLModel, Field, create_engine, Session, select, update
from sqlmodel import Column, JSON
from contextlib import asynccontextmanager
from enum import Enum
import httpx
import math
import pandas as pd
import uuid
from uuid import UUID
from io import StringIO

from fastapi import Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from sqlalchemy import and_, delete, func, insert, or_, text, update
from sqlalchemy import inspect
from sqlalchemy import desc
from sqlalchemy import join
from sqlalchemy import alias, distinct
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session
from typing import AsyncGenerator
from sqlalchemy.dialects.postgresql import insert

from core.adb import engine, get_session, create_db_and_tables
from core.middleware import add_cors_middleware
from core.models import Content, ContentEntity, Entity, Location, Tag, ContentEvaluation, EntityLocation, ContentTag, MediaDetails, Image, ContentLocation
from core.service_mapping import config
from core.utils import logger
from core.service_mapping import get_redis_url

from datetime import datetime, timezone

## Setup 
# App API Router
router = APIRouter()
# Redis connection
redis_conn_flags = Redis.from_url(get_redis_url(), db=0)  # For flags


########################################################################################
## 1. SCRAPING PIPELINE

# Produce Flags for scraping
@router.get("/flags")
async def produce_flags():
    await redis_conn_flags.delete("scrape_sources")
    flags = ["cnn", "bbc", "dw", "pynews"]
    for flag in flags:
        await redis_conn_flags.lpush("scrape_sources", flag)
    return {"message": f"Flags produced: {', '.join(flags)}"}

@router.post("/store_raw_contents")
async def store_raw_contents(
    session: AsyncSession = Depends(get_session),
    overwrite: bool = True
):
    """
    Ingest raw contents from Redis and store them in PostgreSQL.
    If 'overwrite' is True, update existing content with the same URL.
    Otherwise skip if content already exists.
    """
    try:
        logger.info("Starting to store raw contents.")

        redis_conn = await Redis.from_url(get_redis_url(), db=1, decode_responses=True)
        raw_contents = await redis_conn.lrange('raw_contents_queue', 0, -1)
        logger.info(f"Fetched {len(raw_contents)} raw contents from Redis.")
        contents = [json.loads(content) for content in raw_contents]

        async with session.begin():
            for content_data in contents:
                url = content_data.get('url')
                logger.debug(f"Processing content with URL: {url}")

                # Check if the URL already exists
                result = await session.execute(
                    select(Content).where(Content.url == url)
                )
                existing_content = result.scalar_one_or_none()

                if existing_content:
                    logger.info(f"Content with URL {url} found in database.")
                    if overwrite:
                        logger.info(f"Overwriting content with URL {url}.")
                        # Overwrite fields on the existing record
                        existing_content.text_content = content_data.get('text_content')
                        existing_content.last_updated = datetime.now(timezone.utc).isoformat()
                        existing_content.summary = content_data.get('summary')
                        existing_content.meta_summary = content_data.get('meta_summary')

                        # Overwrite or update media details if provided
                        # Create a new MediaDetails object if any images/top_image are present
                        if content_data.get('images') or content_data.get('top_image'):
                            media_details_obj = MediaDetails(
                                top_image=content_data.get('top_image'),
                                images=[Image(image_url=img) for img in content_data.get('images', [])]
                            )
                            # Assign the new media details to the existing content
                            existing_content.media_details = media_details_obj
                        else:
                            # Optionally clear media details if desired
                            existing_content.media_details = None
                    else:
                        # Not overwriting; skip ingestion
                        logger.info(f"Skip existing content (no overwrite) for URL {url}.")
                        continue
                else:
                    # Create a new Content if none exist for this URL
                    new_content = Content(
                        url=content_data['url'],
                        title=content_data.get('title'),
                        text_content=content_data.get('text_content'),
                        source=content_data.get('source'),
                        summary=content_data.get('summary'),
                        meta_summary=content_data.get('meta_summary'),
                        publication_date=content_data.get('publish_date'),
                        author=", ".join(content_data.get('authors', [])) if 'authors' in content_data else None
                    )

                    # Add media details if present
                    if content_data.get('images') or content_data.get('top_image'):
                        media_details_obj = MediaDetails(
                            top_image=content_data.get('top_image'),
                            images=[Image(image_url=img) for img in content_data.get('images', [])]
                        )
                        new_content.media_details = media_details_obj

                    session.add(new_content)
                    await session.flush()
                    logger.info(f"Created new content record for URL: {url}")

        await session.commit()
        logger.info("Session committed successfully.")

        # Trim the processed contents from Redis
        await redis_conn.ltrim('raw_contents_queue', len(raw_contents), -1)
        logger.info("Trimmed processed contents from Redis queue.")
        await redis_conn.close()
        logger.info("Closed Redis connection.")

        return {"message": "Raw contents processed successfully."}

    except Exception as e:
        logger.error(f"Error processing contents: {e}", exc_info=True)
        await session.rollback()
        logger.info("Session rollback due to error.")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await session.close()
        logger.info("Session closed.")

########################################################################################
## 2. EMBEDDING PIPELINE

@router.post("/create_embedding_jobs")
async def create_embedding_jobs(session: AsyncSession = Depends(get_session)):
    logger.info("Trying to create embedding jobs.")
    try:
        async with session.begin():
            query = select(Content).where(Content.embeddings == None)
            result = await session.execute(query)
            contents_without_embeddings = result.scalars().all()
            logger.info(f"Found {len(contents_without_embeddings)} contents without chunk embeddings.")

            redis_conn_unprocessed_contents = await Redis.from_url(get_redis_url(), db=5)

            # Get existing contents in the queue
            existing_urls = set(await redis_conn_unprocessed_contents.lrange('contents_without_embedding_queue', 0, -1))
            existing_urls = {json.loads(url)['url'] for url in existing_urls}

            contents_list = []
            not_pushed_count = 0
            for content in contents_without_embeddings:
                if content.url not in existing_urls:
                    contents_list.append(json.dumps({
                        'url': content.url,
                        'title': content.title,
                        'text_content': content.text_content
                    }))
                else:
                    not_pushed_count += 1

            logger.info(f"{not_pushed_count} contents already in queue, not pushed again.")

        if contents_list:
            await redis_conn_unprocessed_contents.rpush('contents_without_embedding_queue', *contents_list)
            logger.info(f"Pushed {len(contents_list)} contents to Redis queue.")
        else:
            logger.info("No new contents found that need embeddings.")

        await redis_conn_unprocessed_contents.close()
        return {"message": f"Embedding jobs created for {len(contents_list)} contents."}
    except Exception as e:
        logger.error(f"Failed to create embedding jobs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/store_contents_with_embeddings")
async def store_contents_with_embeddings(session: AsyncSession = Depends(get_session)):
    try:
        redis_conn = await Redis.from_url(get_redis_url(), db=6, decode_responses=True)
        contents_with_embeddings = await redis_conn.lrange('contents_with_embeddings', 0, -1)

        async with session.begin():
            for index, content_json in enumerate(contents_with_embeddings, 1):
                try:
                    content_data = json.loads(content_json)
                    logger.info(f"Processing content {index}/{len(contents_with_embeddings)}: {content_data.get('url')}")

                    # Find the content by URL and eagerly load the content
                    result = await session.execute(
                        select(Content).where(Content.url == content_data['url'])
                    )
                    content = result.scalar_one_or_none()

                    if content:
                        # Update the overall content embeddings
                        content.embeddings = content_data.get('embeddings')

                        session.add(content)

                except ValidationError as e:
                    logger.error(f"Validation error for content: {e}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding error: {e}")
                except Exception as e:
                    logger.error(f"Error processing content: {e}", exc_info=True)

        await session.commit()
        logger.info("Stored contents with embeddings in PostgreSQL")

        # Clear the processed contents from Redis
        await redis_conn.ltrim('contents_with_embeddings', len(contents_with_embeddings), -1)
        await redis_conn.close()
    except Exception as e:
        logger.error(f"Error storing contents with embeddings: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await session.close()

########################################################################################
## 3. ENTITY PIPELINE

@router.post("/create_entity_extraction_jobs")
async def create_entity_extraction_jobs(session: AsyncSession = Depends(get_session)):
    logger.info("Starting to create entity extraction jobs.")
    try:
        query = select(Content).where(Content.entities == None)
        result = await session.execute(query)
        _contents = result.scalars().all()

        redis_conn = await Redis.from_url(get_redis_url(), db=2)

        # Get existing contents in the queue
        existing_urls = set(await redis_conn.lrange('contents_without_entities_queue', 0, -1))
        existing_urls = {json.loads(url)['url'] for url in existing_urls}   
        
        contents_list = []
        not_pushed_count = 0
        for content in _contents:
            if content.url not in existing_urls:
                contents_list.append(json.dumps({
                    'url': content.url,
                    'title': content.title,
                    'text_content': content.text_content
                }))
            else:
                not_pushed_count += 1

        logger.info(f"{not_pushed_count} contents already in queue, not pushed again.")

        if contents_list:
            await redis_conn.rpush('contents_without_entities_queue', *contents_list)
            logger.info(f"Pushed {len(contents_list)} contents to Redis queue.")
        else:
            logger.info("No new contents found that need entities.")

        await redis_conn.close()  # Close the Redis connection

        logger.info(f"Entity extraction jobs for {len(_contents)} contents created.")
        return {"message": "Entity extraction jobs created successfully."}
    except Exception as e:
        logger.error(f"Error creating entity extraction jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store_contents_with_entities")
async def store_contents_with_entities(
    session: AsyncSession = Depends(get_session)
):
    redis_conn = await Redis.from_url(get_redis_url(), db=2, decode_responses=True)
    contents_json_array = await redis_conn.lrange('contents_with_entities_queue', 0, -1)
    logger.info(f"Retrieved {len(contents_json_array)} contents from Redis queue")

    try:
        async with session.begin():
            for idx, content_json in enumerate(contents_json_array, 1):
                content_data = json.loads(content_json)
                logger.info(f"Processing content {idx}/{len(contents_json_array)}: {content_data.get('url')}")

                # Locate content by URL
                result = await session.execute(
                    select(Content).where(Content.url == content_data.get('url'))
                )
                content = result.scalar_one_or_none()

                if not content:
                    logger.error(f"Content not found in DB: {content_data.get('url')}")
                    continue

                # Store Entities in ContentEntity table
                entities_data = content_data.get('entities', [])
                for entity_obj in entities_data:
                    entity_name = entity_obj.get('text')
                    entity_type = entity_obj.get('tag')
                    is_top_flag = entity_obj.get('is_top', False)

                    # Upsert into Entity
                    stmt_entity = select(Entity).where(Entity.name == entity_name)
                    entity_result = await session.execute(stmt_entity)
                    entity = entity_result.scalar_one_or_none()

                    if not entity:
                        entity = Entity(name=entity_name, entity_type=entity_type if entity_type else "Unknown")
                        session.add(entity)
                        await session.flush()

                    # Upsert into ContentEntity pivot
                    stmt_content_entity = insert(ContentEntity).values(
                        content_id=content.id,
                        entity_id=entity.id,
                        frequency=1,
                        is_top=is_top_flag
                    ).on_conflict_do_update(
                        index_elements=['content_id', 'entity_id'],
                        set_={
                            'frequency': ContentEntity.frequency + 1,
                            'is_top': True if is_top_flag else ContentEntity.is_top
                        }
                    )
                    await session.execute(stmt_content_entity)

                # Cross-check the top_entities array
                top_entity_names = set(content_data.get('top_entities', []))
                if top_entity_names:
                    logger.debug("Marking top entities from top_entities list.")
                    for top_e_name in top_entity_names:
                        stmt = select(Entity).where(Entity.name == top_e_name)
                        entity_res = await session.execute(stmt)
                        existing_top_e = entity_res.scalar_one_or_none()
                        if existing_top_e:
                            # Mark that pivot as is_top
                            update_stmt = (
                                update(ContentEntity)
                                .where(
                                    ContentEntity.content_id == content.id,
                                    ContentEntity.entity_id == existing_top_e.id
                                )
                                .values(is_top=True)
                            )
                            await session.execute(update_stmt)

                # Store Locations in ContentLocation table
                location_names = content_data.get('locations', [])
                top_location_names = set(content_data.get('top_locations', []))
                for loc_name in location_names:
                    # Upsert or retrieve location
                    stmt_loc = select(Location).where(Location.name == loc_name)
                    loc_result = await session.execute(stmt_loc)
                    location = loc_result.scalar_one_or_none()

                    if not location:
                        location = Location(name=loc_name)
                        session.add(location)
                        await session.flush()

                    # Insert/Update pivot
                    upsert_content_location = insert(ContentLocation).values(
                        content_id=content.id,
                        location_id=location.id,
                        frequency=1,
                        is_top_location=(loc_name in top_location_names)
                    ).on_conflict_do_update(
                        index_elements=['content_id', 'location_id'],
                        set_={
                            'frequency': ContentLocation.frequency + 1,
                            'is_top_location': True if loc_name in top_location_names else ContentLocation.is_top_location
                        }
                    )
                    await session.execute(upsert_content_location)

        await session.commit()
        logger.info("Stored contents with entities and (optionally) locations in PostgreSQL.")

        # Trim the processed items from Redis
        await redis_conn.ltrim('contents_with_entities_queue', len(contents_json_array), -1)
        logger.info("Redis queue trimmed")
        await redis_conn.close()

        return {"message": "Processed and stored content with entities and locations successfully."}

    except Exception as e:
        logger.error(f"Error storing contents with entities: {e}", exc_info=True)
        await session.rollback()
        await redis_conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await session.close()

########################################################################################
## 4. GEOCODING PIPELINE

@router.post("/create_geocoding_jobs")
async def create_geocoding_jobs(session: AsyncSession = Depends(get_session)):
    logger.info("Starting to create geocoding jobs.")
    try:
        async with session.begin():
            # Select locations that lack geocoding
            query = select(Location).where(Location.coordinates == None)
            result = await session.execute(query)
            locations = result.scalars().all()
            logger.info(f"Found {len(locations)} locations needing geocoding.")

            redis_conn = await Redis.from_url(get_redis_url(), db=3)

            # Get existing locations in the queue
            existing_locations = set(await redis_conn.lrange('locations_without_geocoding_queue', 0, -1))

            locations_list = []
            not_pushed_count = 0
            for location in locations:
                if location.name not in existing_locations:
                    locations_list.append(json.dumps({
                        'name': location.name
                    }))
                else:
                    not_pushed_count += 1

            logger.info(f"{not_pushed_count} locations already in queue, not pushed again.")

        if locations_list:
            await redis_conn.rpush('locations_without_geocoding_queue', *locations_list)
            logger.info(f"Pushed {len(locations_list)} locations to Redis queue.")
        else:
            logger.info("No new locations found that need geocoding.")

        await redis_conn.close()
        return {"message": f"Geocoding jobs created for {len(locations_list)} locations."}
    except Exception as e:
        logger.error(f"Error creating geocoding jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store_contents_with_geocoding")
async def store_contents_with_geocoding(session: AsyncSession = Depends(get_session)):
    try:
        logger.info("Starting store_contents_with_geocoding function")
        redis_conn = await Redis.from_url(get_redis_url(), db=4, decode_responses=True)
        geocoded_contents = await redis_conn.lrange('contents_with_geocoding_queue', 0, -1)
        logger.info(f"Retrieved {len(geocoded_contents)} geocoded locations from Redis queue")
        
        async with session.begin():
            for index, geocoded_content in enumerate(geocoded_contents, 1):
                try:
                    geocode_data = json.loads(geocoded_content)
                    location_name = geocode_data['name']
                    
                    # Update or create the Location entry
                    stmt = select(Location).where(Location.name == location_name)
                    result = await session.execute(stmt)
                    location = result.scalar_one_or_none()

                    if not location:
                        location = Location(
                            name=location_name,
                            location_type=geocode_data.get('type', 'unknown'),
                            coordinates=geocode_data.get('coordinates'),
                            bbox=geocode_data.get('bbox'),
                            area=geocode_data.get('area'),
                            weight=geocode_data.get('weight', 1.0)
                        )
                        session.add(location)
                        logger.info(f"Added new location: {location_name}")
                    else:
                        # Update existing location details if necessary
                        location.coordinates = geocode_data.get('coordinates', location.coordinates)
                        # location.bbox = geocode_data.get('bbox', location.bbox)
                        # location.area = geocode_data.get('area', location.area)
                        location.weight = max(location.weight, geocode_data.get('weight', location.weight))
                        logger.info(f"Updated location: {location_name}")

                except Exception as e:
                    logger.error(f"Error processing geocoded location {geocode_data.get('name', 'unknown')}: {e}", exc_info=True)

        await session.commit()
        logger.info("Stored geocoded locations in PostgreSQL")

        # Clear the processed geocoded contents from Redis
        await redis_conn.ltrim('contents_with_geocoding_queue', len(geocoded_contents), -1)
        await redis_conn.close()
        return {"message": "Geocoded locations stored successfully in PostgreSQL."}
    except Exception as e:
        logger.error(f"Error storing geocoded locations: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await session.close()

########################################################################################
## 5. LLM CLASSIFICATION PIPELINE

@router.post("/create_classification_jobs")
async def create_classification_jobs(session: AsyncSession = Depends(get_session)):
    logger.info("Starting to create classification jobs.")
    try:
        async with session.begin():
            # Select contents with no evaluati
            query = select(Content).where(Content.evaluation == None)
            result = await session.execute(query)
            contents = result.scalars().all()
            logger.info(f"Found {len(contents)} contents with no classification.")

            redis_conn = await Redis.from_url(get_redis_url(), db=4)
            existing_urls = set(await redis_conn.lrange('contents_without_classification_queue', 0, -1))
            existing_urls = {json.loads(url)['url'] for url in existing_urls}

            contents_list = []
            not_pushed_count = 0
            for content in contents:
                if content.url not in existing_urls:
                    contents_list.append(json.dumps({
                        'url': content.url,
                        'title': content.title,
                        'text_content': content.text_content
                    }))
                else:
                    not_pushed_count += 1

            logger.info(f"{not_pushed_count} contents already in queue, not pushed again.")

        if contents_list:
            await redis_conn.rpush('contents_without_classification_queue', *contents_list)
            logger.info(f"Pushed {len(contents_list)} contents to Redis queue for classification.")
        else:
            logger.info("No new contents found for classification.")
        await redis_conn.close()
        return {"message": f"Classification jobs created for {len(contents_list)} contents."}
    except Exception as e:
        logger.error(f"Error creating classification jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store_contents_with_classification")
async def store_contents_with_classification(session: AsyncSession = Depends(get_session)):
    try:
        logger.info("Starting store_contents_with_classification function")
        redis_conn = await Redis.from_url(get_redis_url(), db=4, decode_responses=True)
        classified_contents = await redis_conn.lrange('contents_with_classification_queue', 0, -1)
        logger.info(f"Retrieved {len(classified_contents)} classified contents from Redis queue")
        
        for index, classified_content in enumerate(classified_contents, 1):
            try:
                content_data = json.loads(classified_content)
                logger.info(f"Processing content {index}/{len(classified_contents)}: {content_data['url']}")
                logger.debug(f"Content evaluation data: {content_data.get('evaluations', {})}")
                
                # Find the content by URL
                stmt = select(Content).where(Content.url == content_data['url'])
                result = await session.execute(stmt)
                content = result.scalar_one_or_none()

                if content:
                    evaluation_data = content_data.get('evaluations', {})
                    evaluation_obj = {
                        'content_id': content.id,
                        'rhetoric': evaluation_data.get('rhetoric', 'neutral'), 
                        'sociocultural_interest': evaluation_data.get('sociocultural_interest', 0),
                        'global_political_impact': evaluation_data.get('global_political_impact', 0),
                        'regional_political_impact': evaluation_data.get('regional_political_impact', 0),
                        'global_economic_impact': evaluation_data.get('global_economic_impact', 0),
                        'regional_economic_impact': evaluation_data.get('regional_economic_impact', 0),
                        'event_type': evaluation_data.get('event_type', 'other'),
                        'event_subtype': evaluation_data.get('event_subtype', 'other'),
                        'keywords': evaluation_data.get('keywords', []),
                        'categories': evaluation_data.get('categories', []),
                        'top_locations': evaluation_data.get('top_locations', [])
                    }
                    
                    # Check if evaluation exists
                    stmt = select(ContentEvaluation).where(ContentEvaluation.content_id == content.id)
                    result = await session.execute(stmt)
                    existing_eval = result.scalar_one_or_none()
                    
                    if existing_eval:
                        # Update existing evaluation
                        stmt = (
                            update(ContentEvaluation)
                            .where(ContentEvaluation.content_id == content.id)
                            .values(**evaluation_obj)
                        )
                        await session.execute(stmt)
                    else:
                        # Create new evaluation
                        evaluation = ContentEvaluation(**evaluation_obj)
                        session.add(evaluation)
                    
                    await session.flush()
                    logger.info(f"Updated content and evaluation: {content_data['url']}")

                    # Handle top locations directly from the evaluations
                    top_locations = evaluation_data.get('top_locations', [])
                    
                    if top_locations:
                        for loc_name in top_locations:
                            # Find or create location
                            stmt_loc = select(Location).where(Location.name == loc_name)
                            result = await session.execute(stmt_loc)
                            location = result.scalar_one_or_none()

                            if not location:
                                location = Location(name=loc_name)
                                session.add(location)
                                await session.flush()

                            # Set up content-location relationship with is_top_location=True
                            upsert_content_location = insert(ContentLocation).values(
                                content_id=content.id,
                                location_id=location.id,
                                frequency=1,
                                is_top_location=True  # This is the critical flag for geojson
                            ).on_conflict_do_update(
                                index_elements=['content_id', 'location_id'],
                                set_={
                                    'frequency': ContentLocation.frequency + 1,
                                    'is_top_location': True
                                }
                            )
                            await session.execute(upsert_content_location)
                else:
                    # if not existing, insert new content
                    content = Content(**content_data)
                    session.add(content)
                    logger.warning(f"Content not found in database: {content_data['url']}")

            except Exception as e:
                logger.error(f"Error processing content {content_data.get('url', 'unknown')}: {str(e)}")
                continue

        await session.commit()
        logger.info("Changes committed to database")
        
        # Clear processed contents from Redis
        await redis_conn.ltrim('contents_with_classification_queue', len(classified_contents), -1)
        logger.info("Redis queue trimmed")
        await redis_conn.close()
        
        return {"message": "Classified contents stored successfully in PostgreSQL."}
    except Exception as e:
        logger.error(f"Error storing classified contents: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))











