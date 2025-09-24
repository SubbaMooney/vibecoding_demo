"""
REST API Routes for MCP RAG Server

This module provides HTTP REST endpoints that mirror the MCP protocol tools,
allowing clients to use the same functionality through standard HTTP requests
when MCP protocol WebSocket connection is not available.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.mcp.core.domain import SearchQuery, SummarizationRequest
from app.mcp.core.service import RAGDomainService, DocumentProcessingService

logger = logging.getLogger(__name__)

# Create API router
api_router = APIRouter(prefix="/api/v1", tags=["rag"])


# Pydantic models for request/response validation
class SearchRequest(BaseModel):
    """Request model for document search."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    search_type: str = Field("semantic", regex="^(semantic|keyword|hybrid)$")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional search filters")


class SearchResultResponse(BaseModel):
    """Response model for search results."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    result_type: str
    document_id: Optional[str] = None
    chunk_index: Optional[int] = None


class SearchResponse(BaseModel):
    """Complete search response."""
    results: List[SearchResultResponse]
    total_results: int
    processing_time_ms: float
    query_metadata: Dict[str, Any]


class SummarizeRequest(BaseModel):
    """Request model for document summarization."""
    document_ids: List[str] = Field(..., description="List of document IDs to summarize")
    summary_type: str = Field("extractive", regex="^(extractive|abstractive|key_points)$")
    max_length: int = Field(500, ge=50, le=2000, description="Maximum summary length")
    language: str = Field("en", description="Summary language")


class SummarizeResponse(BaseModel):
    """Response model for summarization."""
    summary: str
    summary_type: str
    source_documents: List[str]
    confidence_score: float
    processing_time_ms: float


class DocumentResponse(BaseModel):
    """Response model for document information."""
    id: str
    filename: str
    created_at: str
    updated_at: str
    size_bytes: int
    processing_status: str
    metadata: Dict[str, Any]
    content_hash: Optional[str] = None
    content: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for document listing."""
    documents: List[DocumentResponse]
    total_count: int
    limit: int
    offset: int


class UploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str
    filename: str
    status: str
    uploaded_at: str


class DeleteResponse(BaseModel):
    """Response model for document deletion."""
    success: bool
    document_id: str
    deleted_at: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


# Global service instances (will be injected via dependency injection)
rag_service: Optional[RAGDomainService] = None
document_service: Optional[DocumentProcessingService] = None


def set_services(rag_svc: RAGDomainService, doc_svc: DocumentProcessingService) -> None:
    """Set the service instances for the API routes."""
    global rag_service, document_service
    rag_service = rag_svc
    document_service = doc_svc


@api_router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest) -> SearchResponse:
    """
    Perform semantic search across documents.
    
    This endpoint provides the same functionality as the MCP `rag_search` tool
    through a standard HTTP POST request.
    """
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")
    
    logger.info(f"REST API search request: {request.query}")
    
    try:
        # Convert request to domain object
        search_query = SearchQuery(
            query=request.query,
            limit=request.limit,
            threshold=request.threshold,
            search_type=request.search_type,
            filters=request.filters
        )
        
        # Execute search
        search_response = await rag_service.search_documents(search_query)
        
        # Convert to response model
        return SearchResponse(
            results=[
                SearchResultResponse(
                    id=result.id,
                    content=result.content,
                    score=result.score,
                    metadata=result.metadata,
                    result_type=result.result_type.value,
                    document_id=result.document_id,
                    chunk_index=result.chunk_index
                )
                for result in search_response.results
            ],
            total_results=search_response.total_results,
            processing_time_ms=search_response.processing_time_ms,
            query_metadata={
                "original_query": search_response.query.query,
                "search_type": search_response.query.search_type,
                "threshold": search_response.query.threshold,
            }
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/summarize", response_model=SummarizeResponse)
async def summarize_documents(request: SummarizeRequest) -> SummarizeResponse:
    """
    Generate summaries from specified documents.
    
    This endpoint provides the same functionality as the MCP `rag_summarize` tool
    through a standard HTTP POST request.
    """
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")
    
    logger.info(f"REST API summarization request for {len(request.document_ids)} documents")
    
    try:
        # Convert request to domain object
        summarization_request = SummarizationRequest(
            document_ids=request.document_ids,
            summary_type=request.summary_type,
            max_length=request.max_length,
            language=request.language
        )
        
        # Execute summarization
        summary_response = await rag_service.summarize_documents(summarization_request)
        
        # Convert to response model
        return SummarizeResponse(
            summary=summary_response.summary,
            summary_type=summary_response.summary_type,
            source_documents=summary_response.source_documents,
            confidence_score=summary_response.confidence_score,
            processing_time_ms=summary_response.processing_time_ms
        )
        
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    metadata: Optional[str] = Form(None, description="JSON metadata for the document")
) -> UploadResponse:
    """
    Upload and process a new document.
    
    This endpoint provides the same functionality as the MCP `document_upload` tool
    through a standard multipart form upload.
    """
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    
    logger.info(f"REST API document upload: {file.filename}")
    
    try:
        # Validate file
        if not file.filename:
            raise ValueError("Filename is required")
        
        # Read file content
        content = await file.read()
        
        # Parse metadata if provided
        doc_metadata = {}
        if metadata:
            import json
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in metadata field")
        
        # Upload document
        document_id = await document_service.upload_document(
            filename=file.filename,
            content=content,
            metadata=doc_metadata
        )
        
        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="uploaded",
            uploaded_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of documents"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    status_filter: Optional[str] = Query(None, description="Filter by processing status"),
    filename_filter: Optional[str] = Query(None, description="Filter by filename pattern")
) -> DocumentListResponse:
    """
    List documents with pagination and filtering.
    
    This endpoint provides the same functionality as the MCP `document_list` tool
    through a standard HTTP GET request.
    """
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")
    
    logger.info(f"REST API document list: limit={limit}, offset={offset}")
    
    try:
        # Build filters
        filters = {}
        if status_filter:
            filters["processing_status"] = status_filter
        if filename_filter:
            filters["filename"] = filename_filter
        
        # Get documents
        documents = await rag_service.list_documents(
            limit=limit,
            offset=offset,
            filters=filters if filters else None
        )
        
        # Convert to response model
        return DocumentListResponse(
            documents=[
                DocumentResponse(
                    id=str(doc.id),
                    filename=doc.filename,
                    created_at=doc.created_at.isoformat(),
                    updated_at=doc.updated_at.isoformat(),
                    size_bytes=doc.size_bytes,
                    processing_status=doc.processing_status.value,
                    metadata=doc.metadata,
                    content_hash=doc.content_hash
                )
                for doc in documents
            ],
            total_count=len(documents),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Document list error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    """
    Get a specific document by ID.
    
    This endpoint provides the same functionality as the MCP `document_get` tool
    through a standard HTTP GET request.
    """
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG service not initialized")
    
    logger.info(f"REST API get document: {document_id}")
    
    try:
        # Get document
        document = await rag_service.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        
        # Convert to response model
        return DocumentResponse(
            id=str(document.id),
            filename=document.filename,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
            size_bytes=document.size_bytes,
            processing_status=document.processing_status.value,
            metadata=document.metadata,
            content_hash=document.content_hash,
            content=document.content
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: str) -> DeleteResponse:
    """
    Delete a document from the system.
    
    This endpoint provides the same functionality as the MCP `document_delete` tool
    through a standard HTTP DELETE request.
    """
    if not document_service:
        raise HTTPException(status_code=500, detail="Document service not initialized")
    
    logger.info(f"REST API delete document: {document_id}")
    
    try:
        # Delete document
        success = await document_service.delete_document(document_id)
        
        return DeleteResponse(
            success=success,
            document_id=document_id,
            deleted_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Delete document error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the current status of the API and connected services.
    """
    services_status = {
        "rag_service": "healthy" if rag_service else "not_initialized",
        "document_service": "healthy" if document_service else "not_initialized",
    }
    
    overall_status = "healthy" if all(
        status == "healthy" for status in services_status.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        services=services_status
    )


@api_router.get("/protocol-info")
async def get_protocol_info() -> Dict[str, Any]:
    """
    Get information about supported MCP protocol versions and capabilities.
    
    This endpoint helps clients understand what MCP protocol features are available
    and can assist in fallback decision making.
    """
    return {
        "mcp_support": {
            "enabled": True,
            "websocket_endpoint": "/mcp/ws",
            "supported_versions": ["1.0"],
            "max_connections": 100
        },
        "rest_api": {
            "version": "1.0",
            "base_path": "/api/v1",
            "features": ["search", "summarize", "document_management"],
            "rate_limits": {
                "requests_per_minute": 1000,
                "upload_size_mb": 50
            }
        },
        "capabilities": {
            "tools": ["rag_search", "rag_summarize", "document_upload", "document_list", "document_get", "document_delete"],
            "search_types": ["semantic", "keyword", "hybrid"],
            "summary_types": ["extractive", "abstractive", "key_points"],
            "supported_formats": ["pdf", "docx", "txt", "md"]
        }
    }