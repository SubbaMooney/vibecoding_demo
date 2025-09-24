import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import UploadFile
from pathlib import Path
import logging

from backend.app.documents.models import Document
from backend.app.documents.schemas import DocumentProcessingStatus
from backend.app.documents.storage import DocumentStorage
from backend.app.documents.processing import PDFProcessor

logger = logging.getLogger(__name__)

class DocumentService:
    """
    Service layer for document management operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.storage = DocumentStorage()
        self.pdf_processor = PDFProcessor()
    
    async def upload_document(self, file: UploadFile) -> Document:
        """
        Upload and process a document file.
        """
        try:
            # Read file content
            content = await file.read()
            file_size = len(content)
            
            # Validate file
            validation_result = await self.pdf_processor.validate_pdf(content)
            
            if not validation_result["is_valid"]:
                error_msg = validation_result.get("error_message", "Invalid PDF file")
                raise ValueError(error_msg)
            
            if validation_result["is_encrypted"]:
                raise ValueError("Password-protected PDFs are not supported")
            
            # Store file
            upload_time = datetime.utcnow()
            storage_result = await self.storage.store_file(
                file_content=content,
                original_filename=file.filename,
                file_type="pdf",
                upload_date=upload_time
            )
            
            # Create database record
            document = Document(
                filename=storage_result["secure_filename"],
                original_filename=file.filename,
                file_size=file_size,
                mime_type=file.content_type or "application/pdf",
                page_count=validation_result.get("page_count"),
                upload_timestamp=upload_time,
                processing_status="uploaded",
                storage_path=storage_result["storage_path"],
                metadata={
                    "validation_result": validation_result,
                    "storage_info": {
                        "original_dir": storage_result["original_dir"],
                        "processed_dir": storage_result["processed_dir"],
                        "metadata_dir": storage_result["metadata_dir"]
                    }
                }
            )
            
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            
            # Start background processing
            asyncio.create_task(self._process_document_background(document.id, content))
            
            logger.info(f"Document uploaded successfully: {document.id}")
            return document
            
        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}")
            self.db.rollback()
            raise
    
    async def _process_document_background(self, document_id: uuid.UUID, content: bytes):
        """
        Background task for document processing.
        """
        try:
            # Update status to processing
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                return
            
            document.processing_status = "processing"
            self.db.commit()
            
            # Extract text
            extraction_result = await self.pdf_processor.extract_text(
                content, document.original_filename
            )
            
            # Get document structure
            structure_result = await self.pdf_processor.get_document_structure(content)
            
            # Update document with results
            if extraction_result["processing_status"] == "success":
                document.text_content_length = extraction_result["text_length"]
                document.processing_status = "ready"
                
                # Store processed text
                processed_dir = document.metadata["storage_info"]["processed_dir"]
                text_filename = f"{document.filename.rsplit('.', 1)[0]}.txt"
                text_path = f"{processed_dir}/{text_filename}"
                
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(extraction_result["text"])
                
                # Update metadata
                document.metadata.update({
                    "extraction_result": extraction_result,
                    "document_structure": structure_result,
                    "processed_text_path": text_path,
                    "processing_completed_at": datetime.utcnow().isoformat()
                })
                
            else:
                document.processing_status = "error"
                document.metadata.update({
                    "extraction_error": extraction_result.get("error_message"),
                    "processing_failed_at": datetime.utcnow().isoformat()
                })
            
            self.db.commit()
            logger.info(f"Document processing completed: {document_id}")
            
        except Exception as e:
            logger.error(f"Background processing failed for {document_id}: {str(e)}")
            
            # Update status to error
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.processing_status = "error"
                document.metadata.update({
                    "processing_error": str(e),
                    "processing_failed_at": datetime.utcnow().isoformat()
                })
                self.db.commit()
    
    async def list_documents(self, page: int = 1, page_size: int = 20, 
                           status_filter: Optional[str] = None,
                           filename_filter: Optional[str] = None) -> Tuple[List[Document], int]:
        """
        List documents with filtering and pagination.
        """
        try:
            query = self.db.query(Document)
            
            # Apply filters
            if status_filter:
                query = query.filter(Document.processing_status == status_filter)
            
            if filename_filter:
                query = query.filter(
                    or_(
                        Document.filename.ilike(f"%{filename_filter}%"),
                        Document.original_filename.ilike(f"%{filename_filter}%")
                    )
                )
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            documents = query.order_by(Document.upload_timestamp.desc()).offset(offset).limit(page_size).all()
            
            return documents, total_count
            
        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}")
            raise
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID.
        """
        try:
            doc_uuid = uuid.UUID(document_id)
            return self.db.query(Document).filter(Document.id == doc_uuid).first()
            
        except ValueError:
            raise ValueError("Invalid document ID format")
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {str(e)}")
            raise
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete document and associated files.
        """
        try:
            doc_uuid = uuid.UUID(document_id)
            document = self.db.query(Document).filter(Document.id == doc_uuid).first()
            
            if not document:
                return False
            
            # Delete file from storage
            try:
                await self.storage.delete_file(document.storage_path)
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {str(e)}")
            
            # Delete from database
            self.db.delete(document)
            self.db.commit()
            
            logger.info(f"Document deleted successfully: {document_id}")
            return True
            
        except ValueError:
            raise ValueError("Invalid document ID format")
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {str(e)}")
            raise
    
    async def get_processing_status(self, document_id: str) -> Optional[DocumentProcessingStatus]:
        """
        Get document processing status.
        """
        try:
            document = await self.get_document(document_id)
            
            if not document:
                return None
            
            # Determine progress based on status
            progress_map = {
                "uploaded": 25,
                "processing": 50,
                "ready": 100,
                "error": 0
            }
            
            progress = progress_map.get(document.processing_status, 0)
            
            # Get status message
            message = None
            if document.processing_status == "error":
                metadata = document.metadata or {}
                message = (metadata.get("extraction_error") or 
                          metadata.get("processing_error") or 
                          "Processing failed")
            elif document.processing_status == "ready":
                message = f"Processing complete. {document.text_content_length} characters extracted."
            elif document.processing_status == "processing":
                message = "Extracting text and processing document..."
            elif document.processing_status == "uploaded":
                message = "Document uploaded, waiting for processing..."
            
            return DocumentProcessingStatus(
                status=document.processing_status,
                message=message,
                progress=progress
            )
            
        except Exception as e:
            logger.error(f"Failed to get processing status for {document_id}: {str(e)}")
            raise
    
    async def reprocess_document(self, document_id: str) -> bool:
        """
        Reprocess a document (e.g., after processing failure).
        """
        try:
            doc_uuid = uuid.UUID(document_id)
            document = self.db.query(Document).filter(Document.id == doc_uuid).first()
            
            if not document:
                return False
            
            # Reset processing status
            document.processing_status = "uploaded"
            document.text_content_length = None
            
            # Clear previous processing results from metadata
            if document.metadata:
                document.metadata.pop("extraction_result", None)
                document.metadata.pop("extraction_error", None)
                document.metadata.pop("processing_error", None)
                document.metadata.pop("processing_failed_at", None)
                document.metadata.pop("processing_completed_at", None)
            
            self.db.commit()
            
            # Read file and restart processing
            try:
                with open(document.storage_path, 'rb') as f:
                    content = f.read()
                
                asyncio.create_task(self._process_document_background(document.id, content))
                
                logger.info(f"Document reprocessing started: {document_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to read file for reprocessing: {str(e)}")
                document.processing_status = "error"
                document.metadata = document.metadata or {}
                document.metadata["reprocess_error"] = str(e)
                self.db.commit()
                return False
            
        except ValueError:
            raise ValueError("Invalid document ID format")
        except Exception as e:
            logger.error(f"Failed to reprocess document {document_id}: {str(e)}")
            raise
    
    async def get_document_text(self, document_id: str) -> Optional[str]:
        """
        Get extracted text content for a document.
        """
        try:
            document = await self.get_document(document_id)
            
            if not document or document.processing_status != "ready":
                return None
            
            # Try to read from processed text file
            metadata = document.metadata or {}
            processed_text_path = metadata.get("processed_text_path")
            
            if processed_text_path and Path(processed_text_path).exists():
                with open(processed_text_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get document text for {document_id}: {str(e)}")
            return None