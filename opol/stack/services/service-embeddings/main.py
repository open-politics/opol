from fastapi import FastAPI, HTTPException, status, Depends
from sentence_transformers import SentenceTransformer
from enum import Enum
from pydantic import BaseModel, Field
from typing import List
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Core imports
from core.models import Content
from core.service_mapping import ServiceConfig
from core.utils import logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI application setup with lifespan event
async def lifespan(app: FastAPI):
    """Lifespan event for initializing the SentenceTransformer model."""
    logger.info("Initializing SentenceTransformer model...")
    model = SentenceTransformer("jinaai/jina-embeddings-v3", backend="onnx", trust_remote_code=True)
    app.state.encoder = EmbeddingEncoder(model)
    logger.info("Model initialized successfully.")
    yield

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Health check endpoint
@app.get("/healthz", summary="Health Check", response_description="Service health status")
async def healthcheck():
    """
    Check the health of the NLP service. Returns a 200 if healthy
    """
    return {"message": "NLP Service Running"}, 200


# Enum for Embedding Types
class EmbeddingTypes(str, Enum):
    """Enumeration of possible embedding types."""
    QUERY = "retrieval.query"
    PASSAGE = "retrieval.passage"
    MATCHING = "text-matching"
    CLASSIFICATION = "classification"
    SEPARATION = "separation"

# Pydantic model for embedding request
class EmbeddingRequest(BaseModel):
    """Model for embedding request data."""
    embedding_type: EmbeddingTypes = Field(
        default=EmbeddingTypes.CLASSIFICATION, 
        description="Type of embedding task"
    )
    texts: List[str] = Field(
        ..., 
        description="List of texts to generate embeddings for"
    )

# Encoder class for handling embedding generation
class EmbeddingEncoder:
    """Handles the generation of embeddings using a SentenceTransformer model."""
    def __init__(self, model: SentenceTransformer):
        self.model = model

    async def encode(self, texts: List[str], embedding_type: EmbeddingTypes):
        """Encode texts asynchronously using the specified embedding type."""
        logger.info(f"Encoding texts with task: {embedding_type}")
        return self.model.encode(
            texts,
            task=embedding_type.value,  # Pass as task
            prompt_name=embedding_type.value  # Pass as prompt_name
        )


# Endpoint for generating embeddings
@app.post("/embeddings", summary="Generate Embeddings", response_description="Generated embeddings")
async def generate_embeddings(
    request: EmbeddingRequest, 
    encoder: EmbeddingEncoder = Depends(lambda: app.state.encoder)
):
    """
    Generate embeddings for a list of texts using a specified task type.
    """
    if not request.texts:
        logger.error("No texts provided for embedding generation")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No texts provided")

    try:
        embeddings = await encoder.encode(request.texts, request.embedding_type)
        embeddings_list = embeddings.tolist()  # Ensure JSON serializability
        logger.info(f"Generated embeddings for {len(request.texts)} texts with task '{request.embedding_type}'")
        return {"embeddings": embeddings_list}
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generating embeddings")


## Example usage in opol:
# from opol import OPOL

# opol = OPOL(mode="local")
# articles = opol.search.engine("Articles about german Politics")
# texts = [article.content for article in articles[:10]]

# query = "This article talks about finance and the german elections."
# reranked_passages = opol.embeddings.rerank(query, texts)
# print(reranked_passages)
