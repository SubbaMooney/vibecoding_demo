from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    processing_status: str
    upload_timestamp: datetime
    
    class Config:
        from_attributes = True

class DocumentMetadata(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    page_count: Optional[int] = None
    text_content_length: Optional[int] = None
    upload_timestamp: datetime
    processing_status: str
    storage_path: str
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]
    total_count: int
    page: int
    page_size: int

class DocumentUploadRequest(BaseModel):
    pass  # File will be handled via FastAPI's UploadFile

class DocumentProcessingStatus(BaseModel):
    status: str = Field(..., description="Processing status")
    message: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    
    @validator("status")
    def validate_status(cls, v):
        valid_statuses = ["uploaded", "processing", "ready", "error"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v