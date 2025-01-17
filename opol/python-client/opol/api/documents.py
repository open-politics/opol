from .client_base import BaseClient
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel
import requests

# ----------------------------
# Client-Side Document Model
# ----------------------------
class Document(BaseModel):
    id: Optional[str] = None
    url: Optional[str]
    title: str
    content_type: Optional[str] = 'article'  # e.g., 'article', 'video', etc.
    source: Optional[str] = None
    text_content: Optional[str] = None
    insertion_date: Optional[str] = None
    summary: Optional[str] = None
    meta_summary: Optional[str] = None
    media_details: Optional[Dict[str, Any]] = None  # Nested media details

class Documents(BaseModel):
    documents: List[Document]


# ----------------------------
# Response Models
# ----------------------------
class IngestDocsRequest(BaseModel):
    documents: Union[Document, List[Document]]
    overwrite: bool = False

class IngestDocsResponse(BaseModel):
    message: str
    content_ids: Optional[List[str]] = None
    contents: Optional[List[Document]] = None

# ----------------------------
# Documents Client
# ----------------------------
class DocumentManager(BaseClient):
    """
    The `Documents` class interacts with the Postgres service to manage documents.
    It provides methods to ingest new documents and retrieve existing ones by ID or URL.
    """
    def __init__(self, mode: str, api_key: str = None, timeout: int = 60):
        super().__init__(mode, api_key=api_key, timeout=timeout, service_name="service-postgres", port=5434)
    
    def ingest(self, 
                documents: Union[Document, List[Document]],
                overwrite: bool = False
               ) -> IngestDocsResponse:
        """
        Ingest one or multiple documents into the database via HTTP POST request.
        """
        
        payload = IngestDocsRequest(documents=documents, overwrite=overwrite)
        
        endpoint = "api/v2/documents/ingest"

        try:
            response = self.post(endpoint, json=payload.model_dump())
            return IngestDocsResponse(**response)
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors if needed
            raise e

    def read(self, 
             id: Optional[str] = None, 
             ids: Optional[List[str]] = None, 
             url: Optional[str] = None,
             urls: Optional[List[str]] = None

             ) -> Union[Document, Documents]:
        """
        Retrieve a document by its ID or URL via HTTP GET request.

        Args:
            id (Optional[str]): The UUID of the document.
            url (Optional[str]): The URL of the document.

        Returns:
            Document: The retrieved document data.
        """
        if id and ids:
            raise ValueError("Either 'id' (single) or 'ids' (list) must be provided to retrieve a document.")
        if url and urls:
            raise ValueError("Either 'url' (single) or 'urls' (list) must be provided to retrieve a document.")

        if id:
            ids = [id]
        if url:
            urls = [url]

        class ReadDocsRequest(BaseModel):
            ids: Optional[List[str]] = None
            urls: Optional[List[str]] = None 
        
        payload = ReadDocsRequest(ids=ids, urls=urls)
        
        endpoint = "api/v2/documents/read"
        try:
            response = self.post(endpoint, json=payload.model_dump())
            _documents = response.get("documents")
            # Serialisation check & return
            return Documents(documents=[Document(**document) for document in _documents]).documents
        
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors if needed
            raise e
    
    def delete(self, id: Optional[str] = None, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a document by its ID or URL via HTTP DELETE request.
        """
        if not id and not url:
            raise ValueError("Either 'id' or 'url' must be provided to delete a document.")
        if id and url:
            raise ValueError("Only one of 'id' or 'url' must be provided to delete a document.")
        
        class DeleteDocsRequest(BaseModel):
            DocumentId: Optional[str] = None
            DocumentUrl: Optional[str] = None
        
        payload = DeleteDocsRequest(DocumentId=id, DocumentUrl=url)
            
        endpoint = "api/v2/documents/delete"
        try:
            response = self.post(endpoint, json=payload.model_dump())
            return response
        except requests.exceptions.HTTPError as e:
            raise e