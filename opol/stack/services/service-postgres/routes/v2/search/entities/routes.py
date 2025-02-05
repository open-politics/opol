import json
import logging
import math
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
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

router = APIRouter()

# ----------------------------
# Pydantic Models for Queries
# ----------------------------
class MostRelevantEntitiesRequest(BaseModel):
    article_ids: List[str]
    skip: int = 0
    limit: int = 10

# ----------------------------
# Helper Functions
# ----------------------------
def merge_entities(filtered_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged_entities = {}
    for entity in filtered_entities:
        name_key = entity['name'].lower()
        found = False
        for key in merged_entities:
            if name_key in key or key in name_key:
                merged_entities[key]['article_count'] += entity['article_count']
                merged_entities[key]['total_frequency'] += entity['total_frequency']
                merged_entities[key]['relevance_score'] += entity['relevance_score']
                if len(entity['name']) > len(merged_entities[key]['name']):
                    merged_entities[key]['name'] = entity['name']
                found = True
                break
        if not found:
            merged_entities[name_key] = entity
    return sorted(merged_entities.values(), key=lambda x: x['relevance_score'], reverse=True)

# ----------------------------
# Route Handlers
# ----------------------------
@router.get("/location_entities/{location_name}")
async def get_location_entities(
    location_name: str,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    entities = []
    try:
        subquery = (
            select(Content.id)
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .join(EntityLocation, Entity.id == EntityLocation.entity_id)
            .join(Location, EntityLocation.location_id == Location.id)
            .where(Location.name == location_name)
        ).subquery()

        query = (
            select(
                Entity.name,
                Entity.entity_type,
                func.count(distinct(Content.id)).label('article_count'),
                func.sum(ContentEntity.frequency).label('total_frequency')
            )
            .join(ContentEntity, Entity.id == ContentEntity.entity_id)
            .join(Content, ContentEntity.content_id == Content.id)
            .where(Content.id.in_(select(subquery)))
            .group_by(Entity.id, Entity.name, Entity.entity_type)
        )

        result = await session.execute(query)
        entities = result.all()

        logger.info(f"Query for location '{location_name}' returned {len(entities)} entities")

        # Filter and calculate relevance score
        filtered_entities = []
        for e in entities:
            cleaned_name = e.name.replace("'s", "").replace("'ss", "")
            comparison_name = cleaned_name.lower()

            if comparison_name != location_name.lower():
                relevance_score = (e.total_frequency * math.log(e.article_count + 1))

                if e.entity_type == 'PERSON':
                    relevance_score *= 1.75

                filtered_entities.append({
                    "name": cleaned_name,
                    "type": e.entity_type,
                    "article_count": e.article_count,
                    "total_frequency": e.total_frequency,
                    "relevance_score": relevance_score
                })

        # Merge similar entities
        merged_entities = merge_entities(filtered_entities)

        # Paginate
        paginated_entities = merged_entities[skip:skip+limit]

        logger.info(f"Query for location '{location_name}' returned {len(paginated_entities)} merged entities")

        return paginated_entities

    except Exception as e:
        logger.error(f"Error in get_location_entities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if not entities:
            location_check = await session.execute(select(Location).where(Location.name == location_name))
            location = location_check.scalar_one_or_none()
            if location:
                logger.info(f"Location '{location_name}' exists in the database but no related entities found")
            else:
                logger.warning(f"Location '{location_name}' does not exist in the database")

@router.post("/most_relevant_entities")
async def get_most_relevant_entities(
    request: MostRelevantEntitiesRequest,
    session: AsyncSession = Depends(get_session)
):
    try:
        article_uuids = [uuid.UUID(article_id) for article_id in request.article_ids]

        query = (
            select(
                Entity.name,
                Entity.entity_type,
                func.count(distinct(Content.id)).label('article_count'),
                func.sum(ContentEntity.frequency).label('total_frequency')
            )
            .join(ContentEntity, Entity.id == ContentEntity.entity_id)
            .join(Content, ContentEntity.content_id == Content.id)
            .where(Content.id.in_(article_uuids))
            .group_by(Entity.id, Entity.name, Entity.entity_type)
        )

        result = await session.execute(query)
        entities = result.all()

        # Calculate relevance score and filter entities
        filtered_entities = []
        for e in entities:
            cleaned_name = e.name.replace("'s", "").replace("'ss", "")
            relevance_score = (e.total_frequency * math.log(e.article_count + 1))
            if e.entity_type == 'PERSON':
                relevance_score *= 1.75

            filtered_entities.append({
                "name": cleaned_name,
                "type": e.entity_type,
                "article_count": e.article_count,
                "total_frequency": e.total_frequency,
                "relevance_score": relevance_score
            })

        # Merge similar entities
        merged_entities = merge_entities(filtered_entities)

        # Paginate
        paginated_entities = merged_entities[request.skip:request.skip+request.limit]

        logger.info(f"Returning {len(paginated_entities)} most relevant entities for given articles")

        return paginated_entities

    except Exception as e:
        logger.error(f"Error in get_most_relevant_entities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/by_entity/{entity}")
async def get_related_entities(
    entity: str,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    entities = []
    try:
        subquery = (
            select(Content.id)
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .where(Entity.name == entity)
        ).subquery()

        query = (
            select(
                Entity.name,
                Entity.entity_type,
                func.count(distinct(Content.id)).label('article_count'),
                func.sum(ContentEntity.frequency).label('total_frequency')
            )
            .join(ContentEntity, Entity.id == ContentEntity.entity_id)
            .join(Content, ContentEntity.content_id == Content.id)
            .where(Content.id.in_(select(subquery)))
            .where(Entity.name != entity)
            .group_by(Entity.id, Entity.name, Entity.entity_type)
        )

        result = await session.execute(query)
        entities = result.all()

        logger.info(f"Query for entity '{entity}' returned {len(entities)} related entities")

        # Filter and calculate relevance score
        filtered_entities = []
        for e in entities:
            cleaned_name = e.name.replace("'s", "").replace("'ss", "")
            comparison_name = cleaned_name.lower()

            if comparison_name != entity.lower():
                relevance_score = (e.total_frequency * math.log(e.article_count + 1))
                if e.entity_type == 'PERSON':
                    relevance_score *= 1.75

                filtered_entities.append({
                    "name": cleaned_name,
                    "type": e.entity_type,
                    "article_count": e.article_count,
                    "total_frequency": e.total_frequency,
                    "relevance_score": relevance_score
                })

        # Merge similar entities
        merged_entities = merge_entities(filtered_entities)

        # Paginate
        paginated_entities = merged_entities[skip:skip+limit]

        logger.info(f"Returning {len(paginated_entities)} merged related entities for '{entity}'")

        return paginated_entities

    except Exception as e:
        logger.error(f"Error in get_related_entities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if not entities:
            entity_check = await session.execute(select(Entity).where(Entity.name == entity))
            entity = entity_check.scalar_one_or_none()
            if entity:
                logger.info(f"Entity '{entity}' exists in the database but no related entities found")
            else:
                logger.warning(f"Entity '{entity}' does not exist in the database")