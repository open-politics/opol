from typing import List, Optional
from pydantic import BaseModel
import json
from datetime import datetime, timedelta, timezone

from .client_base import BaseClient

class Geo(BaseClient):
    def __init__(self, mode: str, api_key: str = None, timeout: int = 60):
        super().__init__(mode, api_key=api_key, timeout=timeout, service_name="service-geo", port=3690)

    class ByIdRequest(BaseModel):
        content_ids: List[str]

    def __call__(self, *args, **kwargs):
        if args:
            kwargs['ids'] = args[0]
        return self.by_id(*args, **kwargs)
    
    def json_by_event(
        self, 
        event_type: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = 100, 
        pretty: Optional[bool] = False
    ) -> dict:
        """
        Get GeoJSON data for a specific event type and optional date range.
        
        Args:
            event_type: Type of event to filter (e.g. "Politics", "Protests")
            start_date: Optional ISO format start date (e.g. "2023-01-01T00:00:00+00:00") 
            end_date: Optional ISO format end date (e.g. "2023-12-31T23:59:59+00:00")
            limit: Maximum number of locations to return
            pretty: If True, pretty-print the JSON response
        """
        endpoint = f"dynamic_geojson?event_type={event_type}&limit={limit}"
        
        if start_date:
            endpoint += f"&start_date={start_date}"
        if end_date:
            endpoint += f"&end_date={end_date}"
        
        if pretty:
            response = self.get(endpoint)
            print(json.dumps(response, indent=4))
            return response
        else:
            return self.get(endpoint)
    
    def code(self, location: str) -> dict:
        endpoint = f"geocode_location?location={location}"
        return self.get(endpoint)

    def json(
        self,
        event_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        pretty: bool = False
    ) -> dict:
        """
        Get GeoJSON data with optional filtering.
        If event_type is not specified, returns all event types.
        
        Args:
            event_type: Optional event type to filter by
            start_date: Optional ISO format start date 
            end_date: Optional ISO format end date
            limit: Maximum number of locations
            pretty: If True, pretty-print the JSON response
        """
        endpoint = f"dynamic_geojson?limit={limit}"
        
        if event_type:
            endpoint += f"&event_type={event_type}"
        if start_date:
            endpoint += f"&start_date={start_date}"
        if end_date:
            endpoint += f"&end_date={end_date}"
        
        if pretty:
            response = self.get(endpoint)
            print(json.dumps(response, indent=4))
            return response
        else:
            return self.get(endpoint)
    
    def by_id(self, ids: List[str], pretty: bool = False) -> dict:
        endpoint = "geojson_by_content_ids"
        request = self.ByIdRequest(content_ids=ids)
        params = request.model_dump()
        if pretty:
            response = self.post(endpoint, json=params)
            print(json.dumps(response, indent=4))
            return response
        else:
            return self.post(endpoint, json=params)

    def json_for_timeframe(
        self,
        event_type: str,
        days_back: int = 30,
        limit: int = 100,
        pretty: bool = False
    ) -> dict:
        """
        Get GeoJSON data for a specific number of days back from now.
        
        Args:
            event_type: Type of event to filter
            days_back: Number of days back from today to include
            limit: Maximum number of locations
            pretty: If True, pretty-print the JSON
        """
        end_date = datetime.now(timezone.utc).isoformat()
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        
        return self.json_by_event(
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            pretty=pretty
        )
