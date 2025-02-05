import json
import logging
import math
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, desc, func, select, exists, distinct, DateTime
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
class EntityScoreRequest(BaseModel):
    entity: str
    score_type: str
    timeframe_from: str
    timeframe_to: str

    @field_validator('timeframe_from', 'timeframe_to')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')

class TopEntitiesByScoreRequest(BaseModel):
    score_type: str
    timeframe_from: str
    timeframe_to: str
    limit: int = 10

    @field_validator('timeframe_from', 'timeframe_to')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')

# ----------------------------
# Helper Functions
# ----------------------------
def calculate_confidence_score(article_count: int, std_dev: float, source_count: int) -> float:
    if std_dev is None:
        return 0.0

    count_confidence = min(1.0, article_count / 10)
    std_confidence = 1.0 / (1.0 + float(std_dev))
    source_confidence = min(1.0, source_count / 5)

    confidence = (count_confidence * 0.4) + (std_confidence * 0.3) + (source_confidence * 0.3)

    return round(confidence, 2)

# ----------------------------
# Route Handlers
# ----------------------------
@router.post("/entity_score_over_time")
async def entity_score_over_time(
    request: EntityScoreRequest,
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    try:
        timeframe_from = datetime.strptime(request.timeframe_from, '%Y-%m-%d')
        timeframe_to = datetime.strptime(request.timeframe_to, '%Y-%m-%d')

        truncated_date = func.date_trunc('day', func.cast(Content.insertion_date, DateTime)).label('date')

        query = (
            select(
                truncated_date,
                func.avg(getattr(ContentEvaluation, request.score_type)).label('average_score'),
                func.min(getattr(ContentEvaluation, request.score_type)).label('min_score'),
                func.max(getattr(ContentEvaluation, request.score_type)).label('max_score'),
                func.stddev(getattr(ContentEvaluation, request.score_type)).label('std_dev'),
                func.count(Content.id).label('article_count'),
                func.sum(ContentEntity.frequency).label('total_frequency'),
                func.avg(ContentEvaluation.sociocultural_interest).label('avg_interest'),
                func.array_agg(distinct(ContentEvaluation.event_type)).label('event_types'),
                func.array_agg(distinct(Content.source)).label('sources')
            )
            .join(ContentEvaluation, Content.id == ContentEvaluation.content_id)
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .where(
                Entity.name == request.entity,
                func.cast(Content.insertion_date, DateTime).between(timeframe_from, timeframe_to)
            )
            .group_by(truncated_date)
            .order_by(truncated_date)
        )

        result = await session.execute(query)
        scores = result.all()

        formatted_data = []
        for row in scores:
            entry = {
                "date": row.date.strftime("%Y-%m-%d"),
                "metrics": {
                    "average_score": float(row.average_score) if row.average_score is not None else None,
                    "min_score": float(row.min_score) if row.min_score is not None else None,
                    "max_score": float(row.max_score) if row.max_score is not None else None,
                    "standard_deviation": float(row.std_dev) if row.std_dev is not None else None
                },
                "context": {
                    "article_count": row.article_count,
                    "total_mentions": row.total_frequency,
                    "source_diversity": len(row.sources),
                    "sources": row.sources,
                    "event_types": row.event_types,
                    "sociocultural_interest": float(row.avg_interest) if row.avg_interest is not None else None
                },
                "reliability": {
                    "confidence_score": calculate_confidence_score(
                        article_count=row.article_count,
                        std_dev=row.std_dev,
                        source_count=len(row.sources)
                    )
                }
            }
            formatted_data.append(entry)

        return formatted_data

    except Exception as e:
        logger.error(f"Error in entity_score_over_time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/top_entities_by_score")
async def top_entities_by_score(
    request: TopEntitiesByScoreRequest,
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    try:
        valid_scores = {
            'sociocultural_interest',
            'global_political_impact',
            'regional_political_impact',
            'global_economic_impact',
            'regional_economic_impact'
        }

        if request.score_type not in valid_scores:
            logger.error(f"Invalid score type: {request.score_type}")
            raise HTTPException(status_code=400, detail=f"Invalid score type: {request.score_type}")

        timeframe_from = datetime.strptime(request.timeframe_from, '%Y-%m-%d')
        timeframe_to = datetime.strptime(request.timeframe_to, '%Y-%m-%d')

        query = (
            select(
                Entity.name.label('entity_name'),
                func.avg(getattr(ContentEvaluation, request.score_type)).label('average_score'),
                func.count(Content.id).label('article_count')
            )
            .join(ContentEntity, Entity.id == ContentEntity.entity_id)
            .join(Content, ContentEntity.content_id == Content.id)
            .join(ContentEvaluation, Content.id == ContentEvaluation.content_id)
            .where(
                Content.insertion_date.between(timeframe_from, timeframe_to)
            )
            .group_by(Entity.id, Entity.name)
            .order_by(desc('average_score'))
            .limit(request.limit)
        )

        result = await session.execute(query)
        entities = result.all()

        formatted_entities = [
            {
                "entity_name": row.entity_name,
                "average_score": round(row.average_score, 2) if row.average_score is not None else None,
                "article_count": row.article_count
            }
            for row in entities
        ]

        return formatted_entities

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in top_entities_by_score: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/time_series_entity_in_dimensions")
async def get_entity_time_relevance(
    entity: str,
    timeframe_from: str,
    timeframe_to: str,
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    try:
        timeframe_from_dt = datetime.strptime(timeframe_from, '%Y-%m-%d')
        timeframe_to_dt = datetime.strptime(timeframe_to, '%Y-%m-%d')

        query = (
            select(
                Content.insertion_date,
                func.sum(ContentEntity.frequency).label('total_weight'),
                func.array_agg(ContentEvaluation.topics).label('topics')
            )
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .join(ContentEvaluation, Content.id == ContentEvaluation.content_id)
            .where(
                Entity.name == entity,
                Content.insertion_date.between(timeframe_from_dt, timeframe_to_dt)
            )
            .group_by(Content.insertion_date)
            .order_by(Content.insertion_date)
        )

        result = await session.execute(query)
        time_series_data = result.all()

        formatted_data = [
            {
                "date": row.insertion_date.strftime("%Y-%m-%d"),
                "total_weight": row.total_weight,
                "topics": row.topics
            }
            for row in time_series_data
        ]

        return formatted_data

    except Exception as e:
        logger.error(f"Error in get_entity_time_relevance: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/by_entity/{entity}")
async def get_classification_scores(
    entity: str,
    timeframe_from: Optional[str] = "2000-01-01",
    timeframe_to: Optional[str] = datetime.now().strftime("%Y-%m-%d"),
    score_type: Optional[str] = "sociocultural_interest",
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    try:
        # Log the timeframe parameters
        logger.info(f"Timeframe from: {timeframe_from}, Timeframe to: {timeframe_to}")

        # Validate and parse the date strings
        if not timeframe_from or not timeframe_to:
            raise HTTPException(status_code=400, detail="Timeframe parameters cannot be empty")

        try:
            timeframe_from_dt = datetime.strptime(timeframe_from, '%Y-%m-%d')
            timeframe_to_dt = datetime.strptime(timeframe_to, '%Y-%m-%d')
        except ValueError as ve:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        # Ensure score_type is valid
        valid_scores = {
            'sociocultural_interest',
            'global_political_impact',
            'regional_political_impact',
            'global_economic_impact',
            'regional_economic_impact'
        }

        if score_type not in valid_scores:
            logger.error(f"Invalid score type: {score_type}")
            raise HTTPException(status_code=400, detail=f"Invalid score type: {score_type}")

        # Building the query
        truncated_date = func.date_trunc('day', func.cast(Content.insertion_date, DateTime)).label('date')

        query = (
            select(
                truncated_date,
                func.avg(getattr(ContentEvaluation, score_type)).label('average_score'),
                func.min(getattr(ContentEvaluation, score_type)).label('min_score'),
                func.max(getattr(ContentEvaluation, score_type)).label('max_score'),
                func.stddev(getattr(ContentEvaluation, score_type)).label('std_dev'),
                func.count(Content.id).label('article_count'),
                func.sum(ContentEntity.frequency).label('total_frequency'),
                func.avg(ContentEvaluation.sociocultural_interest).label('avg_interest'),
                func.array_agg(distinct(ContentEvaluation.event_type)).label('event_types'),
                func.array_agg(distinct(Content.source)).label('sources')
            )
            .join(ContentEvaluation, Content.id == ContentEvaluation.content_id)
            .join(ContentEntity, Content.id == ContentEntity.content_id)
            .join(Entity, ContentEntity.entity_id == Entity.id)
            .where(
                Entity.name == entity,
                func.cast(Content.insertion_date, DateTime).between(timeframe_from_dt, timeframe_to_dt)
            )
            .group_by(truncated_date)
            .order_by(truncated_date)
        )

        result = await session.execute(query)
        scores = result.all()

        formatted_data = []
        for row in scores:
            entry = {
                "date": row.date.strftime("%Y-%m-%d"),
                "metrics": {
                    "average_score": float(row.average_score) if row.average_score is not None else None,
                    "min_score": float(row.min_score) if row.min_score is not None else None,
                    "max_score": float(row.max_score) if row.max_score is not None else None,
                    "standard_deviation": float(row.std_dev) if row.std_dev is not None else None
                },
                "context": {
                    "article_count": row.article_count,
                    "total_mentions": row.total_frequency,
                    "source_diversity": len(row.sources),
                    "sources": row.sources,
                    "event_types": row.event_types,
                    "sociocultural_interest": float(row.avg_interest) if row.avg_interest is not None else None
                },
                "reliability": {
                    "confidence_score": calculate_confidence_score(
                        article_count=row.article_count,
                        std_dev=row.std_dev,
                        source_count=len(row.sources)
                    )
                }
            }
            formatted_data.append(entry)

        return formatted_data

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in get_classification_scores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")