from typing import Dict
from .client_base import BaseClient
from datetime import datetime
from pydantic import BaseModel
class Scores(BaseClient):
    """
    Client to interact with the Scores API endpoints.
    """
    def __init__(self, mode: str, api_key: str = None, timeout: int = 60):
        super().__init__(mode, api_key=api_key, timeout=timeout, service_name="service-postgres", port=5434)
    
    def __call__(self, *args, **kwargs):
        return self.get_scores(*args, **kwargs)
    
    class GetScoresRequest(BaseModel):
        entity: str
        timeframe_from: str = "2000-01-01"
        timeframe_to: str = datetime.now().strftime("%Y-%m-%d")
        score_type: str = "sociocultural_interest"

    def get_scores(self, entity: str, timeframe_from: str = "2000-01-01", timeframe_to: str = datetime.now().strftime("%Y-%m-%d"), score_type: str = "sociocultural_interest") -> dict:
        endpoint = f"api/v2/search/scores/by_entity/{entity}"
        params = {"timeframe_from": timeframe_from, "timeframe_to": timeframe_to}
        return self.get(endpoint, params)
    
    def by_entity(self, entity: str, timeframe_from: str = "2000-01-01", timeframe_to: str = datetime.now().strftime("%Y-%m-%d")) -> dict:
        endpoint = f"api/v2/search/scores/by_entity/{entity}"
        params = {"timeframe_from": timeframe_from, "timeframe_to": timeframe_to}
        return self.get(endpoint, params)