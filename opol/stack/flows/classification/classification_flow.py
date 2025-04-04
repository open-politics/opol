import asyncio
import json
import os
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from prefect import flow, task
from prefect.task_runners import ThreadPoolTaskRunner

from core.utils import UUIDEncoder, logger
from core.models import Content
from core.service_mapping import get_redis_url, ServiceConfig
from opol import OPOL

# Initialize config
config = ServiceConfig()

opol = OPOL(mode=os.environ.get("OPOL_MODE", "container"), api_key=os.environ.get("OPOL_API_KEY", ""))

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
        model_name=os.environ.get("LLM_MODEL", "models/gemini-2.0-flash"), 
        llm_api_key=os.environ.get("GOOGLE_API_KEY", "")
    )


@task(log_prints=True)
async def retrieve_contents_from_redis(batch_size: int) -> List[Content]:
    """Retrieve contents from Redis queue asynchronously."""
    redis_conn = await Redis.from_url(get_redis_url(), db=4)
    _contents = await redis_conn.lrange('contents_without_classification_queue', 0, batch_size - 1)
    await redis_conn.ltrim('contents_without_classification_queue', batch_size, -1)

    contents = []
    for content_data in _contents:
        try:
            content = Content(**json.loads(content_data))
            contents.append(content)
        except Exception as e:
            logger.error(f"Invalid content: {content_data}")
            logger.error(f"Error: {e}")

    logger.info(f"Successfully retrieved {len(contents)} contents")
    return contents


# Initial Filter using Literal of either "Content" or "Other"
class ContentRelevance(BaseModel):
    """
    Assess whether the given headline represents a substantial article or merely unwanted scraped material.
    If the headline consists solely of a single keyword such as "Technology," "Asia," "404 - Page not found," or "Data Privacy," it is likely deemed unwanted and should be classified as "Other."
    """
    content_type: Literal["Content", "Other"]


@task(log_prints=True)
async def classify_content(content: Content) -> dict:
    """Classify the content for relevance asynchronously."""
    try:
        content_text = f"Content Title: {content.title}\n\nContent: {content.text_content[:320]}"

        sys_prompt = "Classify the content for relevance. If the headline consists solely of a single keyword such as 'Technology,' 'Asia,' '404 - Page not found,' or 'Data Privacy,' it is likely deemed unwanted and should be classified as 'Other'."

        classification_result = xclass.classify(ContentRelevance, sys_prompt, content_text)
        logger.debug(f"Model response: {classification_result}")
        return classification_result.model_dump()
    except Exception as e:
        logger.error(f"Error classifying content ID {content.id}: {e}")
        return {}
    

# Second, more comprehensive classiication
class ContentEvaluation(BaseModel):
    """
    Evaluate content for political analysis across dimensions: locations, rhetoric, impact, events, and categories.

    1. Locations: Identify and classify locations.
    2. Rhetoric: Determine tone: "neutral," "emotional," "argumentative," "optimistic," "pessimistic."
    3. Impact: Assess sociocultural, global/regional political, and economic impacts on a scale of 0-10.
       - Sociocultural: Cultural and societal relevance.
       - Political: Implications on global and regional politics.
       - Economic: Implications on global and regional economies.
    4. Events: Classify event type and provide specific subtype if applicable. Choose from:
    5. Categories: List content/ news categories.
    """

    top_locations: Optional[List[str]] = Field(None)

    # Impact Analysis
    sociocultural_interest: Optional[int] = Field(None, ge=0, le=10)
    global_political_impact: Optional[int] = Field(None, ge=0, le=10)
    regional_political_impact: Optional[int] = Field(None, ge=0, le=10)
    global_economic_impact: Optional[int] = Field(None, ge=0, le=10)
    regional_economic_impact: Optional[int] = Field(None, ge=0, le=10)

    # Event Classification
    event_type: Optional[Literal[
        "Protests", "Elections", "Politics", "Economic", "Legal", 
        "Social", "Crisis", "War", "Peace", "Diplomacy", 
        "Technology", "Science", "Culture", "Sports", "Other"
    ]] = Field(None)
    event_subtype: Optional[str] = Field(None)

    categories: Optional[List[str]] = Field(None)

    # Validators
    @field_validator(
        'sociocultural_interest', 
        'global_political_impact', 
        'regional_political_impact', 
        'global_economic_impact', 
        'regional_economic_impact', 
        mode='before'
    )
    def score_must_be_within_range(cls, v, info):
        if not isinstance(v, int):
            raise ValueError(f"{info.field_name} must be an integer.")
        if not 0 <= v <= 10:
            raise ValueError(f"{info.field_name} must be between 0 and 10.")
        return v

    @field_validator('categories', mode='before')
    def validate_lists(cls, v, info):
        if v is None:
            return v

        # If the input is a string that looks like a list, try to parse it
        if isinstance(v, str):
            try:
                v = json.loads(v.replace("'", '"'))
            except json.JSONDecodeError:
                raise ValueError(f"{info.field_name} must be a list of strings.")

        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of strings.")

        # Ensure all elements are strings
        if not all(isinstance(item, str) for item in v):
            raise ValueError(f"All items in {info.field_name} must be strings.")

        return v


@task(log_prints=True)
async def evaluate_content(content: Content) -> ContentEvaluation:
    """Evaluate the content if it is relevant asynchronously."""
    try:
        content_text = f"Content Title: {content.title}\n\nContent: {content.text_content[:320]}"
        sys_prompt = f"""
        Evaluate this content for political analysis. The domain is open source political intelligence.

        Pay special attention to identifying top locations - important geographical areas that this content relates to.
        These locations will be used for mapping visualization, so include only significant geographical entities
        (countries, regions, cities) that are central to the content.
        """
        classification_result = xclass.classify(ContentEvaluation, sys_prompt, content_text)
        return classification_result
    except Exception as e:
        logger.error(f"Error evaluating content ID {content.id}: {e}")
        return ContentEvaluation()


@task(log_prints=True)
async def write_contents_to_redis(serialized_contents):
    """Write serialized contents to Redis asynchronously."""
    if not serialized_contents:
        logger.info("No contents to write to Redis")
        return

    # Ensure each content is serialized to JSON
    serialized_contents = [json.dumps(content, cls=UUIDEncoder) for content in serialized_contents]

    redis_conn_processed = await Redis.from_url(get_redis_url(), db=4)
    await redis_conn_processed.lpush('contents_with_classification_queue', *serialized_contents)
    logger.info(f"Wrote {len(serialized_contents)} contents with classification to Redis")


@flow(task_runner=ThreadPoolTaskRunner(max_workers=50))
async def classify_contents_flow(batch_size: int):
    """Process a batch of contents: retrieve, classify, and store them asynchronously."""
    contents = await retrieve_contents_from_redis(batch_size=batch_size)

    if not contents:
        logger.warning("No contents to process.")
        return []

    futures = [classify_content.submit(content) for content in contents]
    results = [future.result() for future in futures]  # Resolve futures
    evaluated_contents = []

    for content_dict, content in zip(results, contents):
        if not content_dict:
            continue
        try:
            if content_dict.get("content_type") != "Other":
                llm_evaluation = await evaluate_content(content)
                
                # Create content dict with top_locations already in the evaluation
                content_dict_processed = {
                    'url': content.url,
                    'title': content.title,
                    'evaluations': llm_evaluation.model_dump(exclude={'id'})
                    # No need to map thematic_locations to top_locations - it's already top_locations
                }
                evaluated_contents.append(content_dict_processed)
            else:
                logger.info(f"Content classified as irrelevant: {content.title[:50]}...")
                redis_conn = await Redis.from_url(get_redis_url(), db=4)
                await redis_conn.rpush('filtered_out_queue', json.dumps(content.model_dump(), cls=UUIDEncoder))
        except Exception as e:
            logger.error(f"Error processing content: {content.title[:50]}...")
            logger.error(f"Error: {e}")
            continue

    if evaluated_contents:
        logger.info(f"Writing {len(evaluated_contents)} evaluated contents to Redis")
        await write_contents_to_redis(evaluated_contents)
    return evaluated_contents


@task(log_prints=True)
async def process_content(content):
    """
    This function can be used for individual content processing if needed.
    """
    try:
        relevance = await classify_content(content)
        logger.info(f"Relevance result: {relevance}")
        if relevance.get("content_type") == "Other":
            logger.info(f"Content classified as irrelevant: {content.title[:50]}...")
            redis_conn = await Redis.from_url(get_redis_url(), db=4)
            await redis_conn.rpush('filtered_out_queue', json.dumps(content.model_dump(), cls=UUIDEncoder))
            return None
        else:
            llm_evaluation = await evaluate_content(content)
            logger.info(f"Evaluation completed for: {content.title[:50]}")
            
            db_evaluation = ContentEvaluation(
                content_id=content.id,
                **llm_evaluation.model_dump()
            )

            content_dict = {
                'url': content.url,
                'title': content.title,
                'evaluations': db_evaluation.model_dump(exclude={'id'})
            }
            return content_dict
    except Exception as e:
        logger.error(f"Error processing content: {content.title[:50]}...")
        logger.error(f"Error: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(classify_contents_flow(batch_size=40))