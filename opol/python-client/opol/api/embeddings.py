from typing import Dict, List, Union, Optional
from .client_base import BaseClient
import numpy as np
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
    def __init__(self, mode: str, api_key: str = None, timeout: int = 60):
        super().__init__(mode, api_key=api_key, timeout=timeout, service_name="service-embeddings", port=420)
    
    def __call__(self, *args, **kwargs):
        return self.get_embeddings(*args, **kwargs)
    
    def generate(self, text: Union[str, List[str]], embedding_type: Optional[str] = "separation") -> dict:
        """
        Fetch embeddings for a given text and embedding type.

        Args:
            text (str): The text to generate embeddings for.
            embedding_type (str): The type of embedding task.
            
        Returns:
            dict: The embeddings for the text.
        """
        if isinstance(text, str):
            text = [text]
        endpoint = f"/embeddings"
        
        # Convert string embedding_type to EmbeddingTypes Enum if possible
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
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def rerank(self, 
               query: str, 
               passages: List[str],
               lean: bool = False
               ) -> Union[List[Dict[str, Union[str, float, int]]], List[int]]:
        query_embedding = self.generate(query, embedding_type="separation")
        passages_embeddings = self.generate(passages, embedding_type="separation")

        ranked_vectors = sorted(
            [{"content": passages[i], "similarity": self.cosine(query_embedding, vector), "index": i} for i, vector in enumerate(passages_embeddings)],
            key=lambda x: x["similarity"],
            reverse=True
        )

        if lean:
            return [item["index"] for item in ranked_vectors]
        return ranked_vectors
    
    def rerank_articles(self, 
               query: str, 
               articles: List[Dict], 
               query_emb_type: str = "retrieval.query", 
               articles_emb_type: str = "retrieval.passage", 
               text_field: str = "title",
               lean: bool = False
               ) -> Union[List[Dict[str, Union[Dict, float]]], List[int]]:
        """
        Reranks articles based on the cosine similarity of their embeddings to the query embedding.

        Args:
            query_embedding (List[float]): The embedding of the query.
            articles (List[Dict]): List of articles to rerank.
            text_field (str): The article field to embed ('title', 'content', or 'both').

        Returns:
            List[Dict[str, Union[Dict, float]]]: Sorted list of dictionaries containing articles and their similarity scores.
        """
        if text_field == "title":
            texts = [article.title for article in articles]
        elif text_field == "content":
            texts = [article.content[:300] for article in articles]
        elif text_field == "both":
            texts = [f"{article.title}\n{article.content[:300]}" for article in articles]
        else:
            raise ValueError("Invalid text_field value. Choose 'title', 'content', or 'both'.")

        query_embedding = self.generate(query, embedding_type=query_emb_type)
        article_embeddings = [self.generate(text, embedding_type=articles_emb_type) for text in texts]

        ranked_articles = sorted(
            [{"article": article, "similarity": self.cosine(query_embedding, embedding)} for article, embedding in zip(articles, article_embeddings)],
            key=lambda x: x["similarity"],
            reverse=True
        )

        if lean:
            return [articles.index(item["article"]) for item in ranked_articles]
        return ranked_articles
