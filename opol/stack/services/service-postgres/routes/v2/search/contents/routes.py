import json
import logging
import math
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from enum import Enum

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, desc, func, select, exists, distinct
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator

from core.adb import get_session
from core.models import (
    Content,
    Entity,
    Location,
    ContentEvaluation,
    ContentEntity,
    EntityLocation,
)
from core.service_mapping import config
from core.utils import logger
import uuid

from opol import OPOL
import os
opol = OPOL(mode=os.getenv("OPOL_MODE"), api_key=os.getenv("OPOL_API_KEY"))

from opol.api.embeddings import Embeddings
embedder = Embeddings(
    mode="local", use_api=True,
    api_provider="jina", api_provider_key=os.getenv("JINA_API_KEY")
)

router = APIRouter()

# ----------------------------
# Pydantic Models for Queries
# ----------------------------
class SearchType(str, Enum):
    TEXT = "text"
    SEMANTIC = "semantic"

class ContentsQueryParams(BaseModel):
    url: Optional[str] = None
    search_query: Optional[str] = None
    search_type: Optional[str] = None
    skip: Optional[int] = 0
    limit: int = 10
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    filters: Optional[str] = None
    news_category: Optional[str] = None
    secondary_category: Optional[str] = None
    keyword: Optional[str] = None
    entities: Optional[str] = None
    locations: Optional[str] = None
    topics: Optional[str] = None
    classification_scores: Optional[str] = None
    keyword_weights: Optional[str] = None
    exclude_keywords: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None

    @field_validator('from_date', 'to_date', mode='before')
    def validate_date(cls, v):
        if v:
            try:
                return datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v

# ----------------------------
# Helper Functions
# ----------------------------
def apply_date_filters(query, from_date: Optional[datetime], to_date: Optional[datetime]):
    if from_date and to_date:
        return query.where(Content.insertion_date.between(from_date, to_date))
    elif from_date:
        return query.where(Content.insertion_date >= from_date)
    elif to_date:
        return query.where(Content.insertion_date <= to_date)
    return query

def apply_search_filters(query, search_query: Optional[str], search_type: SearchType):
    if not search_query:
        return query

    if search_type.lower() == 'text':
        search_condition = or_(
            func.lower(Content.title).contains(func.lower(search_query)),
            func.lower(Content.text_content).contains(func.lower(search_query)),
            exists().where(
                and_(
                    ContentEntity.content_id == Content.id,
                    Entity.id == ContentEntity.entity_id,
                    func.lower(Entity.name).contains(func.lower(search_query))
                )
            )
        )
        return query.where(search_condition)
    elif search_type.lower() == 'semantic':
        embedder = Embeddings(
            mode="local", use_api=True,
            api_provider="jina", api_provider_key=os.getenv("JINA_API_KEY")
        )
        embeddings = embedder.generate(search_query, "retrieval.query")
        return (
            select(
                Content,
                Content.embeddings.l2_distance(embeddings).label('distance')
            )
            .options(
                selectinload(Content.entities).selectinload(Entity.locations),
                selectinload(Content.tags),
                selectinload(Content.evaluation),
                selectinload(Content.media_details)
            )
            .order_by('distance')
            .distinct()
        )
    return query

def apply_common_filters(query, params: ContentsQueryParams):
    if params.url:
        query = query.where(Content.url == params.url)

    # Category Filters
    category_conditions = []
    if params.news_category:
        category_conditions.append(ContentEvaluation.news_category == params.news_category)
    if params.secondary_category:
        category_conditions.append(ContentEvaluation.secondary_categories.any(params.secondary_category))
    if params.keyword:
        category_conditions.append(ContentEvaluation.keywords.any(params.keyword))
    if category_conditions:
        query = query.where(or_(*category_conditions))

    # Entity Filters
    if params.entities:
        entity_list = params.entities.split(",")
        query = query.where(Entity.name.in_(entity_list))

    # Location Filters
    if params.locations:
        location_list = params.locations.split(",")
        query = query.where(Location.name.in_(location_list))

    # Topic Filters
    if params.topics:
        topic_list = params.topics.split(",")
        query = query.where(ContentEvaluation.secondary_categories.any(topic_list))

    # Classification Score Filters
    if params.classification_scores:
        score_filters = json.loads(params.classification_scores)
        for score_type, score_range in score_filters.items():
            min_score, max_score = score_range
            query = query.where(
                and_(
                    getattr(ContentEvaluation, score_type) >= min_score,
                    getattr(ContentEvaluation, score_type) <= max_score
                )
            )

    # Keyword Weights
    if params.keyword_weights:
        keyword_weights_dict = json.loads(params.keyword_weights)
        for keyword, weight in keyword_weights_dict.items():
            query = query.where(
                or_(
                    Content.title.ilike(f'%{keyword}%') * weight,
                    Content.text_content.ilike(f'%{keyword}%') * weight
                )
            )

    # Exclude Keywords
    if params.exclude_keywords:
        exclude_keywords_list = params.exclude_keywords.split(",")
        for keyword in exclude_keywords_list:
            query = query.where(
                and_(
                    ~Content.title.ilike(f'%{keyword}%'),
                    ~Content.text_content.ilike(f'%{keyword}%')
                )
            )

    return query

# ----------------------------
# Route Handlers
# ----------------------------
@router.get("/")
async def get_contents(
    params: ContentsQueryParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    try:
        async with session.begin():
            embedder = Embeddings(
                mode="local", use_api=True,
                api_provider="jina", api_provider_key=os.getenv("JINA_API_KEY")
            )
            query_embeddings = embedder.generate(params.search_query, "retrieval.query")
            
            query = (
                select(
                    Content,
                    Content.embeddings.cosine_distance(query_embeddings).label('distance')
                )
                .options(
                    selectinload(Content.entities).selectinload(Entity.locations),
                    selectinload(Content.tags),
                    selectinload(Content.evaluation),
                    selectinload(Content.media_details)
                )
                .order_by('distance')
                .distinct()
            )

            # Apply date filters
            query = apply_date_filters(query, params.from_date, params.to_date)

            # Apply search filters
            query = apply_search_filters(query, params.search_query, params.search_type)

            # Apply other common filters
            query = apply_common_filters(query, params)

            # Apply sorting
            if params.sort_by:
                sort_column = getattr(ContentEvaluation, params.sort_by, None)
                if sort_column:
                    if params.sort_order == "desc":
                        query = query.order_by(desc(sort_column))
                    else:
                        query = query.order_by(sort_column)

            # Execute query with pagination
            result = await session.execute(query.offset(params.skip).limit(params.limit))
            contents = result.unique().scalars().all()

            # Format response
            contents_data = [
                {
                    "id": str(content.id),
                    "url": content.url,
                    "title": content.title,
                    "source": content.source,
                    "insertion_date": content.insertion_date,
                    "text_content": content.text_content,
                    "top_image": content.media_details.top_image if content.media_details else None,
                    "entities": [
                        {
                            "id": str(e.id),
                            "name": e.name,
                            "entity_type": e.entity_type,
                            "locations": [
                                {
                                    "name": loc.name,
                                    "location_type": loc.location_type,
                                    "coordinates": loc.coordinates.tolist() if loc.coordinates is not None and loc.coordinates.size > 0 else None
                                } for loc in e.locations
                            ] if e.locations else []
                        } for e in content.entities
                    ] if content.entities else [],
                    "tags": [
                        {
                            "id": str(t.id),
                            "name": t.name
                        } for t in (content.tags or [])
                    ],
                    "evaluation": content.evaluation.model_dump() if content.evaluation else None
                }
                for content in contents
            ]

            return contents_data

    except ValueError as e:
        logger.error(f"Invalid value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving contents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving contents")

@router.get("/by_entity/{entity}")
async def get_articles_by_entity(
    entity: str,
    date: Optional[str] = None,
    skip: Optional[int] = 0,
    limit: Optional[int] = 10,
    session: AsyncSession = Depends(get_session)
):
    try:
        if date:
            date_filter = datetime.strptime(date, "%Y-%m-%d").isoformat()
        else:
            date_filter = (datetime.now(timezone.utc) - timedelta(weeks=24)).isoformat()

        query = (
            select(Content)
            .options(
                selectinload(Content.entities).selectinload(Entity.locations),
                selectinload(Content.tags),
                selectinload(Content.evaluation),
                selectinload(Content.media_details)
            )
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .where(Entity.name == entity)
            .where(Content.insertion_date >= date_filter)  # Use the date filter
            .distinct()
            .offset(skip)
            .limit(limit)
        )

        result = await session.execute(query)
        contents = result.unique().scalars().all()

        # Format response to include media details
        contents_data = [
            {
                "id": str(content.id),
                "url": content.url,
                "title": content.title,
                "source": content.source,
                "insertion_date": content.insertion_date,
                "text_content": content.text_content,
                "top_image": content.media_details.top_image if content.media_details else None,
                "entities": [
                    {
                        "id": str(e.id),
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "locations": [
                            {
                                "name": loc.name,
                                "location_type": loc.location_type,
                                "coordinates": loc.coordinates.tolist() if loc.coordinates is not None and loc.coordinates.size > 0 else None
                            } for loc in e.locations
                        ] if e.locations else []
                    } for e in content.entities
                ] if content.entities else [],
                "tags": [
                    {
                        "id": str(t.id),
                        "name": t.name
                    } for t in (content.tags or [])
                ],
                "evaluation": content.evaluation.model_dump() if content.evaluation else None
            }
            for content in contents
        ]

        return contents_data

    except Exception as e:
        logger.error(f"Error retrieving articles for entity '{entity}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving articles")

@router.get("/by_location/{location}")
async def get_articles_by_location(
    location: str,
    skip: int = 0,
    limit: int = 10,
    session: AsyncSession = Depends(get_session)
):
    try:
        async with session.begin():
            query = (
                select(Content)
                .options(
                    selectinload(Content.entities).selectinload(Entity.locations),
                    selectinload(Content.tags),
                    selectinload(Content.evaluation),
                    selectinload(Content.media_details)
                )
                .join(ContentEntity, Content.id == ContentEntity.content_id)
                .join(Entity, ContentEntity.entity_id == Entity.id)
                .join(EntityLocation, Entity.id == EntityLocation.entity_id)
                .join(Location, EntityLocation.location_id == Location.id)
                .where(Location.name == location)
                .distinct()
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(query)
            contents = result.unique().scalars().all()
            logger.info(f"Retrieved {len(contents)} contents for location '{location}'")

            # Format response like in get_contents
            contents_data = [
                {
                    "id": str(content.id),
                    "url": content.url,
                    "title": content.title,
                    "source": content.source,
                    "insertion_date": content.insertion_date if content.insertion_date else None,
                    "text_content": content.text_content,
                    "top_image": content.media_details.top_image if content.media_details else None,
                    "entities": [
                        {
                            "id": str(e.id),
                            "name": e.name,
                            "entity_type": e.entity_type,
                            "locations": [
                                {
                                    "name": loc.name,
                                    "location_type": loc.location_type,
                                    "coordinates": loc.coordinates.tolist() if loc.coordinates is not None and loc.coordinates.size > 0 else None
                                } for loc in e.locations
                            ] if e.locations else []
                        } for e in content.entities
                    ] if content.entities else [],
                    "tags": [
                        {
                            "id": str(t.id),
                            "name": t.name
                        } for t in (content.tags or [])
                    ],
                    "evaluation": content.evaluation.model_dump() if content.evaluation else None
                }
                for content in contents
            ]

            # Reverse the list before returning
            contents_data.reverse()
            return contents_data

    except Exception as e:
        logger.error(f"Error retrieving articles for location '{location}': {e}")
        raise HTTPException(status_code=500, detail="Error retrieving articles")