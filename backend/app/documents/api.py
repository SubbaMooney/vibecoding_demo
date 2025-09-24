from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime
import mimetypes

from backend.app.core.database import get_db
from backend.app.documents.models import Document
from backend.app.documents.schemas import (
    DocumentUploadResponse, 
    DocumentMetadata, 
    DocumentListResponse,
    DocumentProcessingStatus
)
from backend.app.documents.service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# File size limit: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document for processing.
    
    - **file**: PDF file to upload (max 50MB)
    
    Returns document metadata and processing status.
    """
    # Validate file size
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size {file.size} exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
        )
    
    # Validate MIME type
    if file.content_type not in ["application/pdf"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Only PDF files are supported. Got: {file.content_type}"
        )
    
    # Validate file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="File must have .pdf extension"
        )
    
    try:
        document_service = DocumentService(db)
        document = await document_service.upload_document(file)
        return DocumentUploadResponse.from_orm(document)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    filename: Optional[str] = Query(None, description="Filter by filename"),
    db: Session = Depends(get_db)
):
    """
    List uploaded documents with optional filtering and pagination.
    """
    try:
        document_service = DocumentService(db)
        documents, total_count = await document_service.list_documents(
            page=page,
            page_size=page_size,
            status_filter=status,
            filename_filter=filename
        )
        
        return DocumentListResponse(
            documents=[DocumentMetadata.from_orm(doc) for doc in documents],
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Get specific document metadata by ID.
    """
    try:
        document_service = DocumentService(db)
        document = await document_service.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return DocumentMetadata.from_orm(document)
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a document and clean up associated files.
    """
    try:
        document_service = DocumentService(db)
        success = await document_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return {"message": "Document deleted successfully"}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.get("/{document_id}/status", response_model=DocumentProcessingStatus)
async def get_document_status(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Get document processing status.
    """
    try:
        document_service = DocumentService(db)
        status = await document_service.get_processing_status(document_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return status
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Reprocess a document (e.g., after processing failure).
    """
    try:
        document_service = DocumentService(db)
        success = await document_service.reprocess_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return {"message": "Document reprocessing started"}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reprocess document: {str(e)}")