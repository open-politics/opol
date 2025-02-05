from typing import List
import os
import json
from functools import lru_cache

import numpy as np
from prefect import flow, task
from sentence_transformers import SentenceTransformer
from redis import Redis
from core.models import Content
from core.utils import get_redis_url, logger
from prefect.task_runners import ConcurrentTaskRunner

# Configuration Management
model_name = os.getenv("EMBEDDING_MODEL_NAME", "jinaai/jina-embeddings-v3")

@lru_cache(maxsize=1)
def get_model():
    """Lazy loads the SentenceTransformer model using a singleton pattern."""
    logger.info(f"Loading SentenceTransformer model: {model_name}")
    return SentenceTransformer(model_name, trust_remote_code=True)

# Load the model once, using the cached function
model = get_model()

@task(retries=3, retry_delay_seconds=60, log_prints=True)
def retrieve_contents_from_redis(batch_size: int) -> List[Content]:
    """
    Retrieves a batch of contents from Redis for processing.
    Utilizes Redis pipelines for optimized operations.
    """
    redis_conn = Redis.from_url(get_redis_url(), db=5, decode_responses=True)
    try:
        batch = redis_conn.lrange('contents_without_embedding_queue', 0, batch_size - 1)
        redis_conn.ltrim('contents_without_embedding_queue', batch_size, -1)
        contents = [Content(**json.loads(content)) for content in batch]
        logger.info(f"Retrieved {len(contents)} contents from Redis")
        return contents
    except Exception as e:
        logger.error(f"Error retrieving contents from Redis: {e}")
        return []
    finally:
        redis_conn.close()

@task
def split_into_batches(contents: List[Content], batch_size: int) -> List[List[Content]]:
    """Splits the list of contents into smaller batches."""
    return [contents[i:i + batch_size] for i in range(0, len(contents), batch_size)]

@task
def process_batch(texts: List[str], embedding_type: str = "retrieval.passage") -> List[dict]:
    """
    Processes a list of texts by generating their embeddings.
    This function is now atomic and only handles encoding.
    """
    if texts:
        try:
            embeddings = model.encode(
                texts,
                task=embedding_type,
                prompt_name=embedding_type
            )
            logger.info(f"Generated embeddings for {len(texts)} texts")
            return [embedding.tolist() for embedding in embeddings]
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}")
            return []
    else:
        logger.info("No texts provided for embedding generation")
        return []

@task(log_prints=True)
def write_contents_to_redis(contents_with_embeddings: List[dict]):
    """
    Writes the processed contents with embeddings back to Redis.
    """
    redis_conn = Redis.from_url(get_redis_url(), db=6, decode_responses=True)
    try:
        serialized_contents = [json.dumps(content) for content in contents_with_embeddings if content]
        if serialized_contents:
            redis_conn.lpush('contents_with_embeddings', *serialized_contents)
            logger.info(f"Wrote {len(serialized_contents)} contents with embeddings to Redis")
        else:
            logger.info("No contents to write to Redis")
    finally:
        redis_conn.close()

@flow(task_runner=ConcurrentTaskRunner(max_workers=2), log_prints=True)
def generate_embeddings_flow(batch_size: int = 10):
    """
    The main flow to retrieve, process, and store content embeddings using batch processing.
    """
    logger.info("Starting embeddings generation process")
    raw_contents = retrieve_contents_from_redis(batch_size)

    if not raw_contents:
        logger.info("No contents retrieved. Exiting flow.")
        return

    batches = split_into_batches(raw_contents, batch_size)
    logger.info(f"Split contents into {len(batches)} batches")

    # Extract texts from contents
    texts_batches = []
    for batch in batches:
        texts = []
        for content in batch:
            text = ""
            if content.title:
                text += f"### Title: {content.title}. \n"
            if content.text_content:
                text += content.text_content[:400] + "\n"
            if text.strip():
                texts.append(text)
            else:
                logger.info(f"No text available to generate embeddings for content: {content.url}")
        texts_batches.append(texts)

    # Submit process_batch tasks
    future_embeddings = [
        process_batch.submit(texts) for texts in texts_batches
    ]

    all_embeddings = []
    for future in future_embeddings:
        result = future.result()
        if result:
            all_embeddings.extend(result)
    
    contents_with_embeddings = []
    for batch in batches:
        for content in batch:
            content_dict = {
                'url': content.url,
                'title': content.title,
                'text_content': content.text_content,
                'embeddings': all_embeddings[batch.index(content)]
            }
            contents_with_embeddings.append(content_dict)

    # Write results to Redis
    write_contents_to_redis(contents_with_embeddings)

# # -------------------------------------------------------------------
# # OPTIONAL: For local testing only (without Prefect deployment)
# # -------------------------------------------------------------------
# if __name__ == "__main__":
#     # Just run flow once with default params
#     generate_embeddings_flow(batch_size=50)