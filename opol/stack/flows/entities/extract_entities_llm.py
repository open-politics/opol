import os
import json
import logging
import re
import string
from typing import List, Tuple, Set, Literal
from pydantic import BaseModel, Field
from pydantic import field_validator
from redis import Redis
from prefect import flow, task
from redis.exceptions import RedisError

from core.models import Content
from core.utils import logger, UUIDEncoder, get_redis_url
from opol import OPOL

opol = OPOL(mode=os.getenv("OPOL_MODE"), api_key=os.getenv("OPOL_API_KEY"))

# Entity type definitions
ENTITY_LABELS = Literal[
    "person",           # Political figures, leaders, diplomats
    "organization",     # Government bodies, NGOs, companies
    "location",         # Physical locations, cities, regions
    "geopolitical_entity"  # Countries, unions, administrative regions
]

class Entity(BaseModel):
    """A political entity with its classification."""
    text: str
    label: ENTITY_LABELS
    is_top: bool = Field(default=False, description="Reserved for primary entities and locations that are most relevant to the content.")

    @field_validator('label', mode='after')
    def validate_label(cls, v, info):
        valid_labels = [label.lower() for label in ENTITY_LABELS.__args__]
        if v.lower() not in valid_labels:
            raise ValueError(f"Invalid label: {v}")
        return v.lower()

class EntityList(BaseModel):
    """
    Analyze the text and identify key political entities. Focus on:

    1. PERSONS: Political figures, leaders, diplomats, and key decision makers
    2. ORGANIZATIONS: Government bodies, international organizations, NGOs, significant companies
    3. LOCATIONS: Specific cities, regions, geographical areas
    4. GEOPOLITICAL ENTITIES: Countries, political unions, administrative territories

    Extract only clearly defined entities, not general concepts. Each entity must be:
    - Specific and named (e.g., "Joe Biden" not "the president")
    - Relevant to political analysis
    - Actually present in the text (no inference)

    Additional rules:
    - Use canonical names (e.g., "Israel" not "Israeli" or "Israelis")
    - Use singular form for geopolitical entities (e.g., "country" becomes "countries")
    - Prefer noun forms over adjectives ("Palestinian authorities" not "Palestinian")
    - Combine different references to the same entity (e.g., "Americans" → "United States")
    """
    entities: List[Entity]

class EntityExtractor:
    @staticmethod
    def load_fastclass():
        # Simplified initialization
        try:
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
            return xclass
        except Exception as e:
            logger.error(f"Classification service init failed: {e}")
            raise

    def __init__(self):
        self.ner_tagger = self.load_fastclass()
        logger.debug("EntityExtractor initialized")

    @task(log_prints=True, cache_policy=None)
    def predict_entities(self, text: str) -> List[Tuple[str, str]]:
        result = self.ner_tagger.classify(
            EntityList,
            "Extract specific named entities: people, places, orgs, geopolitical entities",
            text
        )
        return [(entity.text, entity.label) for entity in result.entities]

@task(retries=3, retry_delay_seconds=60, log_prints=True, cache_policy=None)
def retrieve_contents(batch_size: int) -> List[Content]:
    try:
        redis_conn = Redis.from_url(get_redis_url(), db=2, decode_responses=True)
        batch = redis_conn.lrange('contents_without_entities_queue', 0, batch_size - 1)
        if not batch:
            logger.info("No contents found in the queue.")
            return []
        redis_conn.ltrim('contents_without_entities_queue', batch_size, -1)
        contents = [Content(**json.loads(content)) for content in batch]
        logger.info(f"Retrieved {len(contents)} contents from Redis.")
        return contents
    except RedisError as e:
        logger.error(f"Redis error: {e}")
        return []
    finally:
        redis_conn.close()

@task(log_prints=True)
def merge_entities(
    entities: List[Tuple[str, str]], 
    title_entities_texts: Set[str],
    source: str = None
) -> List[Tuple[str, str, bool]]:
    # Keep original case but check lowercase for matches
    title_lower = {t.lower() for t in title_entities_texts}
    
    return [
        (t, l, t.lower() in title_lower)  # Preserve original case but check lowercase
        for t, l in entities
    ]

@task(log_prints=True, cache_policy=None)
def process_content(content: Content) -> Tuple[Content, List[Tuple[str, str, bool]]]:
    extractor = EntityExtractor()
    
    # Direct text concatenation without cleaning
    full_text = ". ".join(filter(None, [
        content.title,
        content.meta_summary,
        content.text_content
    ]))
    
    entities = extractor.predict_entities(full_text)
    title_lower = content.title.lower() if content.title else ""
    
    # Check which entities appear in title (case-insensitive)
    title_entities_texts = {
        entity_text 
        for entity_text, _ in entities
        if entity_text.lower() in title_lower
    }
    
    logger.error(f"Entities found in title: {title_entities_texts}")
    logger.error(f"First 8 entities: {entities[:5]}")
    
    return content, merge_entities(entities, title_entities_texts, content.source)

@task(log_prints=True, cache_policy=None)
def push_entities(contents_with_entities: List[Tuple[Content, List[Tuple[str, str, bool]]]]):
    try:
        redis_conn = Redis.from_url(get_redis_url(), db=2, decode_responses=True)
        for content, entities in contents_with_entities:
            content_data = content.model_dump()
            content_data.update({
                'entities': [
                    {"text": text, "tag": label, "is_top": is_top}
                    for (text, label, is_top) in entities
                ],
            })
            redis_conn.lpush('contents_with_entities_queue', json.dumps(content_data, cls=UUIDEncoder))
            logger.info(f"Pushed Content ID {content.id} to queue.")
        redis_conn.close()
    except RedisError as e:
        logger.error(f"Redis error while pushing entities: {e}")

@flow(log_prints=True)
def extract_entities_flow(batch_size: int = 20):
    contents = retrieve_contents(batch_size=batch_size)

    if not contents:
        logger.info("No contents to process. Exiting flow.")
        return

    processed_contents = [process_content(content) for content in contents]
    push_entities(processed_contents)

if __name__ == "__main__":
    extract_entities_flow(20)