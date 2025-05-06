from typing import Dict, List, Union, Optional
from .client_base import BaseClient
import numpy as np
from pydantic import BaseModel
from enum import Enum

# Define EmbeddingTypes Enum
class EmbeddingTypes(str, Enum):
    QUERY = "retrieval.query"
    PASSAGE = "retrieval.passage"
    MATCHING = "text-matching"
    CLASSIFICATION = "classification"
    SEPARATION = "separation"

class Embeddings(BaseClient):
    """
    Client to interact with the Embeddings API endpoints.
    """
    def __init__(self, 
                mode: str, 
                api_key: str = None, 
                timeout: int = 60, 
                use_api: bool = False, 
                api_provider: Optional[str] = None, 
                api_provider_key: Optional[str] = None
                ):
        
        super().__init__(mode, 
                         api_key=api_key, 
                         timeout=timeout, 
                         service_name="service-embeddings", 
                         port=420)
        
        self.use_api = use_api if use_api is not None else False
        self.api_provider = api_provider
        self.api_provider_key = api_provider_key
    
    def __call__(self, *args, **kwargs):
        return self.generate(*args, **kwargs)
    
    def generate(self, text: Union[str, List[str]], embedding_type: Optional[str] = "separation") -> dict:
        """
        Fetch embeddings for a given text and embedding type.
        
        Args:
            text (str): The text to generate embeddings for. 
            embedding_type (str): The type of embedding task.
            
        Returns:
            dict: The embeddings for the text.
        """
        if self.use_api and self.api_provider:
            # Use the specified API provider
            if self.api_provider == "jina":
                base_url = "https://api.jina.ai/v1"
                endpoint = f"/embeddings"
                data = {
                    "model": "jina-embeddings-v3", 
                    "task": EmbeddingTypes(embedding_type).value,
                    "late_chunking": False,
                    "dimensions": 1024,
                    "embedding_type": "float",
                    "input": [text] if isinstance(text, str) else text
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_provider_key}"
                }
            else:
                raise ValueError(f"Unsupported API provider: {self.api_provider}")
            
            response = self.post(endpoint, json=data, override_base_url=base_url, override_headers=headers)
            embedding = response['data'][0]['embedding']
            # If the input was a single string and Jina returns a list containing the actual embedding vector,
            # unwrap it to ensure a 1D vector is returned.
            if isinstance(text, str) and isinstance(embedding, list) and len(embedding) == 1 \
               and isinstance(embedding[0], list):
                return embedding[0]
            return embedding
        else:
            # Use the local model on the service-embeddings on port 420
            endpoint = "/embeddings"
            if isinstance(text, str):
                text = [text] 
            try:
                embedding_type_enum = EmbeddingTypes(embedding_type)
            except ValueError:
                raise ValueError(f"Invalid embedding type: {embedding_type}")

            params = {
                "embedding_type": embedding_type_enum.value,
                "texts": text  
            }
            response = self.post(endpoint, json=params)
            embeddings = response.get("embeddings", [])
        
        return embeddings
    
    def cosine(self, a, b):
        # Debugging statements to check input shapes and types
        print(f"Type of a: {type(a)}, Shape of a: {np.shape(a)}")
        print(f"Type of b: {type(b)}, Shape of b: {np.shape(b)}")
        
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def rerank(self, 
               query: str, 
               passages: List[str],
               lean: bool = False
               ) -> Union[List[Dict[str, Union[str, float, int]]], List[int]]:
        
        query_embedding = self.generate(query, embedding_type="separation")
        passages_embeddings = self.generate(passages, embedding_type="separation")
        # [0.056315333, -0.086833455, 0.010324996]

        class ReRankedObject(BaseModel):
            index: int
            similarity: float
            passage: Optional[str]

        class ReRankResults(BaseModel):
            query: str
            length: int
            ranked_passages: List[ReRankedObject]

        ranked_passages = [ReRankedObject(passage=passages[i], similarity=self.cosine(query_embedding, vector), index=i) for i, vector in enumerate(passages_embeddings)]

        ranked_passages.sort(key=lambda x: x.similarity, reverse=True)

        if lean:
            return ReRankResults(query=query, length=len(passages), ranked_passages=[item.index for item in ranked_passages])
        return ReRankResults(query=query, length=len(passages), ranked_passages=ranked_passages)

