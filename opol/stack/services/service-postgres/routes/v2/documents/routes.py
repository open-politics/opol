from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.adb import get_session
from core.models import Content, MediaDetails
from core.utils import logger
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Union
import uuid
from core.utils import logging

router = APIRouter()

# ----------------------------
# Pydantic Models for Ingestion
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
# Request & Response Models
# ----------------------------
class IngestDocsRequest(BaseModel):
    documents: Union[Document, List[Document]]
    overwrite: bool = False

class IngestDocsResponse(BaseModel):
    message: str
    content_ids: Optional[List[str]] = None
    contents: Optional[List[Document]] = None

# ----------------------------
# Route Handlers
# ----------------------------

@router.post("/ingest", summary="Ingest one or multiple documents into the database")
async def ingest_documents(
    request: IngestDocsRequest,
    session: AsyncSession = Depends(get_session)
) -> IngestDocsResponse:
    """
    Ingests single or multiple documents via HTTP POST request and saves them to the database.
    Now checks for existing documents by both URL and ID for overwriting.
    """
    try:
        if not request.documents:
            raise HTTPException(status_code=400, detail="No documents provided for ingestion.")
        
        logger.error(f"Received documents for ingestion: {request.documents}")
        if isinstance(request.documents, Document):
            request.documents = [request.documents]

        async with session.begin():
            documents_to_ingest = request.documents
            content_ids = []
            for doc in documents_to_ingest:
                query = select(Content)
                if doc.id:
                    query = query.where(Content.id == doc.id)
                elif doc.url:
                    query = query.where(Content.url == doc.url)
                else:
                    raise HTTPException(status_code=400, detail="Document must have either 'id' or 'url' for ingestion.")

                result = await session.execute(query)
                existing_content = result.scalar_one_or_none()
                
                if existing_content:
                    if request.overwrite:
                        # Overwrite existing document
                        existing_content.title = doc.title
                        existing_content.content_type = doc.content_type
                        existing_content.source = doc.source
                        existing_content.text_content = doc.text_content
                        existing_content.insertion_date = doc.insertion_date or datetime.now(timezone.utc).isoformat()
                        existing_content.summary = doc.summary
                        existing_content.meta_summary = doc.meta_summary
                        # Update media details if provided
                        if doc.media_details:
                            existing_content.media_details = MediaDetails(**doc.media_details)
                        content_ids.append(str(existing_content.id))
                    else:
                        logger.info(f"Document with {'ID ' + doc.id if doc.id else 'URL ' + doc.url} already exists. Skipping ingestion.")
                        continue  # Skip duplicate

                else:
                    # Create new Content instance
                    content = Content(
                        url=doc.url,
                        title=doc.title,
                        content_type=doc.content_type,
                        source=doc.source,
                        text_content=doc.text_content,
                        insertion_date=doc.insertion_date or datetime.now(timezone.utc).isoformat(),
                        summary=doc.summary,
                        meta_summary=doc.meta_summary
                    )

                    session.add(content)
                    await session.flush()  # Flush to assign an ID

                    if doc.media_details:
                        content.media_details = MediaDetails(**doc.media_details, content_id=content.id)

                    content_ids.append(str(content.id))

            await session.commit()

        logger.info(f"Ingested {len(content_ids)} document(s) successfully.")

        return IngestDocsResponse(message="Documents ingested successfully.", content_ids=content_ids)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error ingesting documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during document ingestion.")


class ReadDocsRequest(BaseModel):
    ids: Optional[List[str]] = None
    urls: Optional[List[str]] = None 


@router.post("/read", response_model=Documents, summary="Get a document by ID or URL")
async def get_document(
    request: ReadDocsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieves a document by its ID or URL from the database.
    At least one of id or url must be provided.
    """
    if not request.ids and not request.urls:
        raise HTTPException(status_code=400, detail="Either id or url must be provided")

    # Create list of jobs combining both IDs and URLs
    read_jobs = []
    if request.ids:
        read_jobs.extend({"value": str(id), "type": "id"} for id in request.ids)
    if request.urls:
        read_jobs.extend({"value": url, "type": "url"} for url in request.urls)

    return_documents = []
    for job in read_jobs:
        try:
            query = select(Content).where(
                Content.id == job["value"] if job["type"] == "id" 
                else Content.url == job["value"]
            )
            
            result = await session.execute(query)
            document = result.scalar_one_or_none()

            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            return_documents.append(document)
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error retrieving document: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error while retrieving document.")
    
    docs =  [Document(**{**document.model_dump(), "id": str(document.id)}) for document in return_documents]

    return Documents(documents=docs)

class DeleteDocsRequest(BaseModel):
    DocumentId: Optional[str] = None
    DocumentUrl: Optional[str] = None

@router.post("/delete", summary="Delete a document by ID or URL")
async def delete_document(
    request: DeleteDocsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Deletes a document by its ID or URL from the database.
    """
    if not request.DocumentId and not request.DocumentUrl:
        raise HTTPException(status_code=400, detail="Either id or url must be provided")
    if request.DocumentId and request.DocumentUrl:
        raise HTTPException(status_code=400, detail="Only one of id or url must be provided")

    try:
        query = select(Content)
        if request.DocumentId:
            query = query.where(Content.id == request.DocumentId)
        else:
            query = query.where(Content.url == request.DocumentUrl)

        result = await session.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        await session.delete(document)
        await session.commit()

        return {"message": "Document deleted successfully.", "id": str(document.id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while deleting document.")