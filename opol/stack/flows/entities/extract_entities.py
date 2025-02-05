import json
import logging
import re
import string
from typing import List, Tuple, Set

from redis import Redis
from prefect import flow, task
from redis.exceptions import RedisError

from core.models import Content
from core.utils import logger, UUIDEncoder, get_redis_url
from gliner import GLiNER


class EntityExtractor:
    def __init__(self, model_name: str = "EmergentMethods/gliner_medium_news-v2.1"):
        self.ner_tagger = self.load_model(model_name)
        logger.info("EntityExtractor initialized successfully.")

    @staticmethod
    def load_model(model_name: str) -> GLiNER:
        try:
            logger.info(f"Loading NER model: {model_name}")
            return GLiNER.from_pretrained(model_name)
        except Exception as e:
            logger.error(f"Failed to load NER model '{model_name}': {e}")
            raise

    @staticmethod
    def normalize_entity(text: str) -> str:
        """Normalize entity text by removing possessive endings."""
        return re.sub(r"'s$|\'s$", "", text).strip()

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove unwanted characters and normalize whitespace."""
        text = text.translate(str.maketrans('', '', string.punctuation))
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @task(log_prints=True)
    def predict_entities(self, text: str, labels: List[str]) -> List[Tuple[str, str]]:
        max_length = 512  # Adjust based on model's capabilities
        entities = []

        logger.debug(f"Starting NER prediction on text of length {len(text)}")

        for start in range(0, len(text), max_length):
            chunk = text[start:start + max_length]
            chunk_entities = self.ner_tagger.predict_entities(chunk, labels)
            logger.debug(f"Chunk {start//max_length + 1}: Extracted {len(chunk_entities)} entities.")
            entities.extend(chunk_entities)

        # Directly return all extracted entities without filtering
        all_entities = [
            (entity["text"], entity["label"])
            for entity in entities
        ]

        logger.debug(f"Total entities extracted: {len(all_entities)}")
        return all_entities

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
    extractor: EntityExtractor, 
    title_entities_texts: List[str],
    source: str = None
) -> List[Tuple[str, str, bool]]:
    """
    Merges and filters entities by:
    1) Normalizing duplicates.
    2) Removing any entity that appears within the source string.
    3) Removing longer entities if a shorter substring entity is present.
    4) Marking entities as top if they appear in the title or summary.
    Returns a list of tuples: (entity_text, label, is_top).
    """

    # Step 1: Count occurrences of each normalized entity.
    entity_counts = {}
    for text, label in entities:
        normalized_text = extractor.normalize_entity(text)
        key = (normalized_text, label)
        entity_counts[key] = entity_counts.get(key, 0) + 1

    # Build an initial list
    merged_entities = [(k[0], k[1]) for k in entity_counts.keys()]

    # Step 2: Remove any entity that appears within the source string
    if source:
        # Normalize the source
        normalized_source = extractor.normalize_entity(source).lower()
        # Extract words/entities from the source
        # This regex extracts word boundaries; adjust as necessary
        source_entities = set(re.findall(r'\b\w+\b', normalized_source))
        logger.debug(f"Source entities to exclude: {source_entities}")

        # Remove entities that match any word in the source
        merged_entities = [
            (text, label)
            for (text, label) in merged_entities
            if extractor.normalize_entity(text).lower() not in source_entities
        ]

    # Step 3: Remove longer entities if a shorter substring entity exists
    merged_entities_sorted = sorted(merged_entities, key=lambda x: len(x[0]))
    to_remove = set()
    for i, (ent_i, label_i) in enumerate(merged_entities_sorted):
        for j, (ent_j, label_j) in enumerate(merged_entities_sorted):
            if i != j and ent_i in ent_j and ent_i != ent_j:
                to_remove.add((ent_j, label_j))

    filtered_entities = [item for item in merged_entities_sorted if item not in to_remove]

    # Step 4: Mark as top if present in title_entities_texts
    final_entities = []
    for (text, label) in filtered_entities:
        is_top = text in title_entities_texts
        final_entities.append((text, label, is_top))

    logger.debug(f"Final merged entities: {final_entities}")
    return final_entities

@task(log_prints=True)
def process_content(content: Content, extractor: EntityExtractor) -> Tuple[
    Content,
    List[Tuple[str, str, bool]],
    Set[str],
    List[str],
    Set[str]
]:
    # Clean up text from title, text_content, meta_summary, etc.
    title = extractor.clean_text(content.title) if content.title else ""
    meta_summary = extractor.clean_text(content.meta_summary) if content.meta_summary else ""
    text_content = extractor.clean_text(content.text_content) if content.text_content else ""

    # Combine everything for overall entity detection.
    full_text = f"{title}. {meta_summary}. {text_content}".strip()
    logger.debug(f"Processing Content ID: {content.id} with text length: {len(full_text)}")

    # Extract all entities from the full_text
    entities = extractor.predict_entities(full_text, labels=["person", "location", "geopolitical_entity", "organization"])
    logger.debug(f"Extracted Entities: {entities}")

    # Extract entities from title and meta_summary for top marking
    top_entities_from_title = extractor.predict_entities(title, labels=["person", "location", "geopolitical_entity", "organization"])
    top_entities_from_summary = extractor.predict_entities(meta_summary, labels=["person", "location", "geopolitical_entity", "organization"]) if meta_summary else []

    # Merge top entities from title and meta_summary
    combined_top_entities = list(set(top_entities_from_title + top_entities_from_summary))
    top_entities_texts = [extractor.normalize_entity(t[0]) for t in combined_top_entities]

    # Merged entities now carry an is_top field
    merged_entities = merge_entities(entities, extractor, top_entities_texts, source=content.source)

    # For "top locations" we only use ones that appear in "combined_top_entities" and have label in {"location", "geopolitical_entity"}:
    top_locations = {
        extractor.normalize_entity(text)
        for text, label, is_top in merged_entities 
        if is_top and label in {"location", "geopolitical_entity"}
    }

    # For the sake of storing them in Redis, we keep the entire set of all recognized locations in all_locations
    all_locations = {
        extractor.normalize_entity(text)
        for text, label, is_top in merged_entities 
        if label in {"location", "geopolitical_entity"}
    }

    logger.debug(f"Top Locations: {top_locations}, Top Entities: {[text for text, _, _ in merged_entities if _]}")
    return content, merged_entities, top_locations, top_entities_texts, all_locations

@task(log_prints=True, cache_policy=None)
def push_entities(contents_with_entities: List[Tuple[Content, List[Tuple[str, str, bool]], Set[str], List[str], Set[str]]]):
    try:
        redis_conn = Redis.from_url(get_redis_url(), db=2, decode_responses=True)
        for content, entities, top_locations, top_entities_texts, all_locations in contents_with_entities:
            content_data = content.model_dump()
            content_data.update({
                'entities': [
                    {"text": text, "tag": label, "is_top": is_top}
                    for (text, label, is_top) in entities
                ],
                'top_locations': list(top_locations),
                'locations': list(all_locations),
                # 'top_entities' no longer needed if we store is_top in each entity,
                # but you can keep it if needed for reference
                'top_entities': list(set(top_entities_texts)),
            })

            redis_conn.lpush('contents_with_entities_queue', json.dumps(content_data, cls=UUIDEncoder))
            logger.info(f"Pushed Content ID {content.id} to queue.")
        redis_conn.close()
    except RedisError as e:
        logger.error(f"Redis error while pushing entities: {e}")

@flow(log_prints=True)
def extract_entities_flow(batch_size: int = 50):
    logger.info("Starting entity extraction flow.")
    contents = retrieve_contents(batch_size=batch_size)
    if not contents:
        logger.info("No contents to process. Exiting flow.")
        return

    extractor = EntityExtractor()
    processed_contents = [process_content(content, extractor) for content in contents]

    logger.info(f"Processed {len(processed_contents)} contents.")
    logger.info(f"First content: {processed_contents[0]}")
    # Uncomment the following line if you want to push entities to Redis, comment out for testing
    push_entities(processed_contents)
    logger.info("Entity extraction flow completed successfully.")

# if __name__ == "__main__":
#     extract_entities_flow(2)