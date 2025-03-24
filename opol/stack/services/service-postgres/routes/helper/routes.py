import os
import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Body
from sqlmodel import SQLModel, Field, create_engine, Session, select, update
from sqlmodel import Column, JSON
from contextlib import asynccontextmanager
from enum import Enum
import httpx
import math
import pandas as pd
import uuid
from io import StringIO

from fastapi import Query, APIRouter
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
from core.utils import logger
from core.adb import engine, get_session, create_db_and_tables
from core.models import Content, ContentEntity, ContentTag, ContentLocation, Entity, EntityLocation, Location, Tag, ContentEvaluation as ORMContentEvaluation, MediaDetails, Image
from core.classification_models import ContentRelevance, ContentEvaluation as PydanticContentEvaluation
from core.service_mapping import ServiceConfig
from sqlalchemy.dialects.postgresql import insert
from opol import OPOL
import datetime
from datetime import timezone, timedelta
import asyncio

# App API Router
router = APIRouter()

# Config
config = ServiceConfig()

########################################################################################
## HELPER FUNCTIONS

@router.post("/deduplicate_contents")
async def deduplicate_contents(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            query = select(Content).group_by(Content.id, Content.url).having(func.count() > 1)
            result = await session.execute(query)
            duplicate_contents = result.scalars().all()

        for content in duplicate_contents:
            logger.info(f"Duplicate content: {content.url}")
            await session.delete(content)

        await session.commit()
        return {"message": "Duplicate contents deleted successfully."}
    except Exception as e:
        logger.error(f"Error deduplicating contents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

#### MISC

@router.delete("/delete_all_classifications")
async def delete_all_classifications(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            # Delete all records from the ContentEvaluation table
            await session.execute(delete(ORMContentEvaluation))
            await session.commit()
            logger.info("All classifications deleted successfully.")
            return {"message": "All classifications deleted successfully."}
    except Exception as e:
        logger.error(f"Error deleting classifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting classifications")

@router.delete("/delete_all_embeddings")
async def delete_all_embeddings(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            # Delete all embeddings from all contents
            await session.execute(update(Content).values(embeddings=None))
            await session.commit()
            logger.info("All embeddings deleted successfully.")
            return {"message": "All embeddings deleted successfully."}
    except Exception as e:
        logger.error(f"Error deleting embeddings: {e}")
        raise HTTPException(status_code=500, detail="Error deleting embeddings")

@router.get("/contents_csv_quick")
async def get_contents_csv_quick(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            query = select(Content.id, Content.url, Content.title, Content.source, Content.insertion_date)
            result = await session.execute(query)
            contents = result.fetchall()

        # Create a DataFrame
        df = pd.DataFrame(contents, columns=['id', 'url', 'title', 'source', 'insertion_date'])

        # Convert DataFrame to CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contents_quick.csv"})

    except Exception as e:
        logger.error(f"Error generating quick CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating quick CSV")
    
async def get_contents_csv(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            query = select(Content)
            result = await session.execute(query)
            contents = result.scalars().all()

        # Convert contents to a list of dictionaries
        contents_data = [content.dict() for content in contents]

        # Create a DataFrame
        df = pd.DataFrame(contents_data)

        # Convert DataFrame to CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contents.csv"})

    except Exception as e:
        logger.error(f"Error generating CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating CSV")

@router.get("/contents_csv_full")
async def get_contents_csv(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            query = select(Content).options(
                selectinload(Content.entities).selectinload(Entity.locations),
                selectinload(Content.tags),
                selectinload(Content.evaluation)
            )
            result = await session.execute(query)
            contents = result.scalars().all()

        # Convert contents to a list of dictionaries
        contents_data = []
        for content in contents:
            content_dict = {
                "id": str(content.id),
                "url": content.url,
                "title": content.title,
                "source": content.source,
                "insertion_date": content.insertion_date.isoformat() if content.insertion_date else None,
                "text_content": content.text_content,
                "embeddings": content.embeddings.tolist() if content.embeddings is not None else None,
                "entities": [
                    {
                        "id": str(e.id),
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "locations": [
                            {
                                "name": loc.name,
                                "type": loc.type,
                                "coordinates": loc.coordinates.tolist() if loc.coordinates is not None else None
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
                "evaluation": content.evaluation.dict() if content.evaluation else None
            }
            contents_data.append(content_dict)

        # Flatten the data for CSV
        flattened_data = []
        for content in contents_data:
            base_data = {
                "id": content["id"],
                "url": content["url"],
                "title": content["title"],
                "source": content["source"],
                "insertion_date": content["insertion_date"],
                "text_content": content["text_content"],
                "embeddings": content["embeddings"],
            }
            if content["entities"]:
                for entity in content["entities"]:
                    entity_data = {
                        "entity_id": entity["id"],
                        "entity_name": entity["name"],
                        "entity_type": entity["entity_type"],
                        "locations": json.dumps(entity["locations"]),
                    }
                    flattened_data.append({**base_data, **entity_data})
            else:
                flattened_data.append(base_data)

        # Create a DataFrame
        df = pd.DataFrame(flattened_data)

        # Convert DataFrame to CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return StreamingResponse(csv_buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contents.csv"})

    except Exception as e:
        logger.error(f"Error generating CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating CSV")

@router.get("/contents_with_chunks")
async def get_contents_with_chunks(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            # Query contents and eagerly load chunks
            query = select(Content).options(selectinload(Content.chunks))
            result = await session.execute(query)
            contents = result.scalars().all()

        contents_with_chunks = []
        for content in contents:
            if content.chunks:
                content_data = {
                    "id": str(content.id),
                    "url": content.url,
                    "title": content.title,
                    "source": content.source,
                    "insertion_date": content.insertion_date if content.insertion_date else None,
                    "chunks": [
                        {
                            "chunk_number": chunk.chunk_number,
                            "text": chunk.text,
                            "embeddings": chunk.embeddings
                        } for chunk in content.chunks
                    ]
                }
                contents_with_chunks.append(content_data)

        return contents_with_chunks

    except Exception as e:
        logger.error(f"Error retrieving contents with chunks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving contents with chunks")

@router.post("/fix_and_purge_null_content_type")
async def fix_and_purge_null_content_type(session: AsyncSession = Depends(get_session)):
    """
    Fixes entries with NULL content_type by setting a default value and purges any remaining NULL entries.
    """
    try:
        async with session.begin():
            # Fix entries where content_type is NULL by setting a default value
            fix_stmt = (
                update(Content)
                .where(Content.content_type == None)
                .values(content_type='default_type')  # Replace 'default_type' with an appropriate value
            )
            result = await session.execute(fix_stmt)
            fixed_count = result.rowcount
            logger.info(f"Fixed {fixed_count} entries with NULL content_type by setting a default value.")

            # Purge any remaining entries with NULL content_type, if any
            purge_stmt = select(Content).where(Content.content_type == None)
            result = await session.execute(purge_stmt)
            contents_to_purge = result.scalars().all()
            purge_count = len(contents_to_purge)

            for content in contents_to_purge:
                await session.delete(content)

            if purge_count > 0:
                logger.info(f"Purged {purge_count} additional articles with NULL content_type.")
                purge_message = f"Purged {purge_count} articles with NULL content_type successfully."
            else:
                purge_message = "No additional articles found with NULL content_type to purge."

        await session.commit()
        return {
            "message": f"Fixed {fixed_count} entries with NULL content_type and {purge_message}"
        }
    except Exception as e:
        logger.error(f"Error fixing and purging articles: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to fix and purge articles with NULL content_type.")


@router.delete("/clear_filtered_out_queue")
async def clear_filtered_out_queue():
    try:
        redis_conn = Redis(host='redis', port=ServiceConfig.REDIS_PORT, db=4)
        redis_conn.delete('filtered_out_queue')
        return {"message": "Filtered out queue cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing filtered out queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error clearing filtered out queue")

@router.get("/read_filtered_out_queue")
async def read_filtered_out_queue():
    try:
        redis_conn = Redis(host='redis', port=ServiceConfig.REDIS_PORT, db=4)
        filtered_out_contents = redis_conn.lrange('filtered_out_queue', 0, -1)
        
        # Convert bytes to JSON objects
        contents = [json.loads(content) for content in filtered_out_contents]
        
        return {"filtered_out_contents": contents}
    except Exception as e:
        logger.error(f"Error reading filtered out queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error reading filtered out queue")

@router.get("/dump_contents")
async def dump_contents(session: AsyncSession = Depends(get_session)) -> List[dict]:
    """Dump all contents with selected fields."""
    async with session.begin():
        query = select(Content)
        result = await session.execute(query)
        contents = result.scalars().all()

    # Prepare the dumped data
    dumped_contents = [
        content.model_dump()
        for content in contents
    ]

    return dumped_contents

@router.post("/ingest_json_backup")
async def ingest_json_backup(
    contents: List[Dict[str, Any]] = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Ingests JSON backups and saves them to the database using the Content model.
    """
    try:
        async with session.begin():
            for content_data in contents:
                # Check if content with the same URL already exists
                existing_content = await session.execute(
                    select(Content).where(Content.url == content_data.get("url"))
                )
                if existing_content.scalar_one_or_none() is None:
                    # Create a Content instance
                    content = Content(
                        url=content_data.get("url"),
                        title=content_data.get("title"),
                        text_content=content_data.get("text_content"),
                        source=content_data.get("source"),
                        content_type=content_data.get("content_type"),
                        insertion_date=content_data.get("insertion_date")
                    )
                    session.add(content)
                else:
                    logger.info(f"Content with URL {content_data.get('url')} already exists. Skipping.")

            await session.commit()
            logger.info("JSON backup ingested successfully.")
            return {"message": "JSON backup ingested successfully."}
    except Exception as e:
        logger.error(f"Error ingesting JSON backup: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Error ingesting JSON backup")

# @router.post("/restore_dates_from_backup")
# async def restore_dates_from_backup(
#     backup_path: str = "/.backups",
#     session: AsyncSession = Depends(get_session)
# ):
#     """
#     Restores original insertion dates from backup files while preserving all other current data.
#     """
#     import os
#     from datetime import datetime

#     try:
#         # Find all JSON files in backup directory
#         backup_files = [f for f in os.listdir(backup_path) if f.endswith('.json')]
#         if not backup_files:
#             return {"message": "No backup files found"}

#         date_updates = 0
#         errors = []

#         async with session.begin():
#             for backup_file in backup_files:
#                 try:
#                     with open(os.path.join(backup_path, backup_file), 'r') as f:
#                         backup_contents = json.load(f)

#                     # Create a mapping of URLs to original dates
#                     original_dates = {
#                         content['url']: datetime.fromisoformat(content['insertion_date'])
#                         for content in backup_contents 
#                         if content.get('url') and content.get('insertion_date')
#                     }

#                     # Update dates for existing contents
#                     for url, original_date in original_dates.items():
#                         result = await session.execute(
#                             update(Content)
#                             .where(Content.url == url)
#                             .values(insertion_date=original_date)
#                             .returning(Content.id)
#                         )
#                         if result.scalar_one_or_none():
#                             date_updates += 1
#                             logger.info(f"Restored date for {url}: {original_date}")

#                 except Exception as e:
#                     errors.append(f"Error processing {backup_file}: {str(e)}")
#                     logger.error(f"Error processing backup file {backup_file}: {e}", exc_info=True)

#         await session.commit()
        
#         return {
#             "message": f"Date restoration complete. Updated {date_updates} articles.",
#             "errors": errors if errors else None
#         }

#     except Exception as e:
#         logger.error(f"Error restoring dates: {e}", exc_info=True)
#         await session.rollback()
#         raise HTTPException(status_code=500, detail=str(e))

#healthz
@router.get("/healthz")
async def healthz():
    return {"status": "ok"}, 200

@router.get("/bbc_article_urls")
async def get_bbc_article_urls(
    limit: int = Query(10, description="Number of BBC articles to return"),
    session: AsyncSession = Depends(get_session)
):
    """
    Fetches URLs of BBC articles from the database.
    """
    try:
        async with session.begin():
            query = (
                select(Content.url)
                .where(Content.source == 'bbc')
                .limit(limit)
            )
            result = await session.execute(query)
            urls = result.scalars().all()
            
            return {"urls": urls}
            
    except Exception as e:
        logger.error(f"Error fetching BBC article URLs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching BBC article URLs")

@router.post("/update_articles")
async def update_articles(
    source: str = Query(..., description="Source to update (bbc, dw or cnn)"), 
    limit: int = Query(..., description="how many of them"),
    session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            # Fetch articles based on source
            url_pattern = '%www.bbc.com%' if source == 'bbc' else '%dw.com%' if source == 'dw' else '%www.cnn.com%'
            query = select(Content).options(selectinload(Content.media_details)).where(
                Content.url.ilike(url_pattern)
            )
            result = await session.execute(query)
            contents = result.scalars().all()[:limit]

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for content in contents:
                if content.url and '/video' not in content.url:
                    logger.info(f"Processing {source} article: {content.url}")
                    response = await client.get(
                        "http://service-scraper:8081/scrape_article",
                        params={"url": content.url}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        logger.error(data)
                        async with session.begin():
                            content.url = data.get("url") if data.get("url") else None
                            content.publication_date = data.get("publication_date")
                            content.source = source
                            content.text_content = data.get("text_content")
                            content.summary = data.get("summary") if data.get("summary") else None
                            content.meta_summary = data.get("meta_summary") if data.get("meta_summary") else None
                            content.last_updated = data.get("last_updated")
                            if data.get("top_image") or data.get("images"):
                                content.media_details = MediaDetails(
                                    top_image=data.get("top_image"),
                                    images=[
                                        Image(image_url=img) for img in data.get("images", [])
                                    ]
                                )
                            else:
                                logger.error(f"No top image or images found for {content.url}")
                                continue

                            await session.flush()
                    else:
                        logger.error(f"Failed to scrape {content.url}: {response.text}")
                else:
                    logger.error("Encountered an empty URL or Video, skipping.")

        await session.commit()
        return {"message": f"{source.upper()} articles updated successfully."}
    except Exception as e:
        logger.error(f"Error updating {source} articles: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating {source} articles")
    
@router.get("/articles_with_top_image")
async def get_articles_with_top_image(session: AsyncSession = Depends(get_session)):
    """
    Retrieve articles where the top image is not empty, returning article data and top image URL.
    """
    try:
        async with session.begin():
            query = (
                select(Content, MediaDetails.top_image)
                .join(Content.media_details)
                .where(MediaDetails.top_image.isnot(None))
            )
            result = await session.execute(query)
            articles_with_images = result.all()

            articles_data = []
            for article, top_image in articles_with_images:
                article_dict = article.model_dump(exclude={"embeddings"})
                article_dict["top_image"] = top_image
                articles_data.append(article_dict)

        return {"articles": articles_data}
    except Exception as e:
        logger.error(f"Error retrieving articles with top image: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving articles with top image")



@router.post("/fix_numpy_embeddings")
async def fix_numpy_embeddings(session: AsyncSession = Depends(get_session)):
    """
    Converts any numpy array embeddings to Python lists across all relevant models:
      - Content.embeddings
      - Image.embeddings
      - VideoFrame.embeddings
    This helps avoid serialization errors that arise when fastapi tries to JSON-encode numpy arrays.
    """
    import numpy as np

    try:
        async with session.begin():
            # 1. Fix Content.embeddings
            contents_query = select(Content).where(Content.embeddings.isnot(None))
            contents_result = await session.execute(contents_query)
            contents = contents_result.scalars().all()
            fixed_content = 0
            for content in contents:
                if isinstance(content.embeddings, np.ndarray):
                    content.embeddings = content.embeddings.tolist()
                    fixed_content += 1


            await session.commit()

        return {
            "message": "All numpy-based embeddings have been converted to lists.",
            "fixed_content_embeddings": fixed_content
        }

    except Exception as e:
        logger.error(f"Error converting numpy embeddings: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Error converting numpy embeddings.")


def standardize_source_name(source: Optional[str]) -> str:
    """
    Maps various source names to a standardized label.
    """
    if source is None:
        return None  # or return a default value if you prefer

    source_mapping = {
        "dw": "DW",
        "DW": "DW",
        "cnn": "CNN",
        "CNN": "CNN",
        "bbc": "BBC News",
        "BBC News": "BBC News"
    }
    return source_mapping.get(source.lower(), source)

@router.post("/standardize_sources")
async def standardize_sources(session: AsyncSession = Depends(get_session)):
    """
    Standardizes the source names in the Content table.
    """
    try:
        async with session.begin():
            query = select(Content)
            result = await session.execute(query)
            contents = result.scalars().all()

            for content in contents:
                if content.source is None:
                    logger.warning(f"Content with ID {content.id} has no source. URL: {content.url}")
                else:
                    standardized_source = standardize_source_name(content.source)
                    if content.source != standardized_source:
                        content.source = standardized_source
                        logger.info(f"Updated source for content {content.id} to {standardized_source}")

            await session.commit()
            return {"message": "Source names standardized successfully."}
    except Exception as e:
        logger.error(f"Error standardizing source names: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error standardizing source names")


## Take 50 most recent contents, create vectors for them, plot them in a 2D space
@router.get("/plot_contents")
async def plot_contents(session: AsyncSession = Depends(get_session)):
    try:
        async with session.begin():
            query = select(Content).order_by(Content.insertion_date.desc()).limit(50)
            result = await session.execute(query)
            contents = result.scalars().all()
            return {"contents": contents}
    except Exception as e:
        logger.error(f"Error plotting contents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error plotting contents")


# Initialize Opol
opol = OPOL(api_key=os.environ["OPOL_API_KEY"])

# Initialize Classification Service
if os.environ["LOCAL_LLM"] == "True":
    xclass = opol.classification(
        provider="ollama", 
        model_name=os.environ.get("LOCAL_LLM_MODEL", "llama3.2:latest"), 
        llm_api_key=""
    )
else:
    xclass = opol.classification(
        provider=os.environ.get("LLM_PROVIDER", "Google"), 
        model_name=os.environ.get("LLM_MODEL", "models/gemini-2.0-flash-exp"), 
        llm_api_key=os.environ.get("GOOGLE_API_KEY", "")
    )


@router.post("/classify_events_last_week")
async def classify_events_last_week(
    limit: Optional[int] = Query(20, description="Number of articles to process"),
    session: AsyncSession = Depends(get_session)
):
    """
    Classify articles from the last week for relevance and evaluate relevant ones.
    Tags irrelevant articles as 'anecdotal'.
    """
    try:
        logger.info("Starting classification of events from the last week.")
        
        # Calculate the date one week ago
        one_week_ago = datetime.datetime.now(timezone.utc) - timedelta(weeks=1)
        logger.debug(f"One week ago date calculated as: {one_week_ago.isoformat()}")

        # Single transaction block encompassing all operations
        async with session.begin():
            # Retrieve 'anecdotal' tag
            anecdotal_tag = await session.execute(
                select(Tag).where(Tag.name == "anecdotal")
            )
            anecdotal = anecdotal_tag.scalar_one_or_none()
            logger.debug(f"Anecdotal tag retrieved: {anecdotal}")

            if anecdotal:
                # Subquery to exclude articles with 'anecdotal' tag
                subquery = select(Content.id).join(ContentTag).where(ContentTag.tag_id == anecdotal.id)
                logger.debug("Subquery created to exclude articles with 'anecdotal' tag.")
            else:
                subquery = select(Content.id).where(False)  # No articles have the 'anecdotal' tag
                logger.debug("No 'anecdotal' tag found, subquery will exclude no articles.")

            # Get IDs of articles that already have evaluations
            evaluated_ids = await session.execute(select(ORMContentEvaluation.content_id))
            evaluated_ids = [row[0] for row in evaluated_ids.fetchall()]
            logger.debug(f"Evaluated article IDs retrieved: {evaluated_ids}")

            # Main query to fetch relevant articles
            query = (
                select(Content)
                .where(
                    and_(
                        Content.insertion_date >= one_week_ago.isoformat(),
                        Content.id.not_in(subquery),
                        Content.id.not_in(evaluated_ids)
                    )
                )
                .limit(limit)
            )
            result = await session.execute(query)
            articles = result.scalars().all()
            logger.info(f"Fetched {len(articles)} articles for classification.")

            if not articles:
                logger.info("No articles to classify from the last week.")
                return {"message": "No articles to classify from the last week."}

            relevant_articles = []
            irrelevant_articles = []

            for article in articles:
                logger.debug(f"Classifying article ID {article.id} for relevance.")
                # Initial Classification: Relevance
                relevance_result = xclass.classify(ContentRelevance, "", article.text_content)
                logger.debug(f"Relevance result for article ID {article.id}: {relevance_result.type}")

                if relevance_result.type == "Relevant":
                    logger.debug(f"Article ID {article.id} is relevant. Proceeding with evaluation.")
                    # Final Evaluation for relevant content
                    evaluation_result = xclass.classify(PydanticContentEvaluation, "", article.text_content)

                    # Extract string values from dictionaries
                    rhetoric = evaluation_result.rhetoric.type if evaluation_result.rhetoric else None
                    event_type = evaluation_result.event_type.type if evaluation_result.event_type else None
                    logger.debug(f"Evaluation result for article ID {article.id}: Rhetoric - {rhetoric}, Event Type - {event_type}")

                    # Create ORMContentEvaluation entry
                    content_evaluation = ORMContentEvaluation(
                        content_id=article.id,
                        rhetoric=rhetoric,
                        event_type=event_type,
                        **evaluation_result.model_dump(exclude={'rhetoric', 'event_type'})
                    )
                    session.add(content_evaluation)
                    relevant_articles.append((article, evaluation_result))
                else:
                    logger.debug(f"Article ID {article.id} is irrelevant and will be tagged as 'anecdotal'.")
                    # Tag as 'anecdotal'
                    irrelevant_articles.append(article)

            # Process Irrelevant Articles
            if irrelevant_articles:
                if not anecdotal:
                    logger.info("Creating 'anecdotal' tag as it does not exist.")
                    # Create the 'anecdotal' tag if it doesn't exist
                    anecdotal = Tag(name="anecdotal")
                    session.add(anecdotal)
                    await session.flush()

                for article in irrelevant_articles:
                    # Associate the 'anecdotal' tag with the article
                    association = ContentTag(content_id=article.id, tag_id=anecdotal.id)
                    session.add(association)
                    logger.debug(f"Article ID {article.id} tagged as 'anecdotal'.")

        await session.commit()
        logger.info("Classification completed successfully.")

        return {
            "message": "Classification completed successfully.",
            "classified_as_relevant": len(relevant_articles),
            "classified_as_irrelevant": len(irrelevant_articles),
            "relevant_articles": relevant_articles,
            "irrelevant_articles": irrelevant_articles
        }

    except Exception as e:
        logger.error(f"Error classifying events: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Error classifying events")