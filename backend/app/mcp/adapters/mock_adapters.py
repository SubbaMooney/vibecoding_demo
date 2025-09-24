"""
Mock Adapter Implementations

This module provides mock implementations of the secondary port adapters
for development and testing purposes. These will be replaced with real
implementations as the system develops.
"""

import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.mcp.core.domain import Document, ProcessingStatus, SearchResult, SearchResultType
from app.mcp.adapters.base import (
    VectorSearchAdapter,
    DocumentStorageAdapter,
    SummarizationAdapter,
    TextExtractionAdapter,
    VectorIndexAdapter,
    SummaryResult,
    TextChunk
)

logger = logging.getLogger(__name__)


class MockVectorSearchAdapter(VectorSearchAdapter):
    """Mock implementation of vector search adapter."""
    
    def __init__(self):
        # Simple in-memory storage for demo
        self._documents = {}
        self._index = {}

    async def semantic_search(self, query: str, limit: int) -> List[SearchResult]:
        """Mock semantic search implementation."""
        logger.info(f"Mock semantic search: {query}")
        
        # Simulate search delay
        await asyncio.sleep(0.1)
        
        # Return mock results
        results = []
        for i in range(min(3, limit)):  # Return max 3 mock results
            results.append(SearchResult(
                id=f"doc_{i+1}",
                content=f"Mock search result {i+1} for query: {query}",
                metadata={
                    "source": "mock_search",
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                },
                score=0.9 - (i * 0.1),  # Decreasing scores
                result_type=SearchResultType.DOCUMENT,
                document_id=f"doc_{i+1}",
                chunk_index=0
            ))
        
        return results

    async def keyword_search(self, query: str, limit: int) -> List[SearchResult]:
        """Mock keyword search implementation."""
        logger.info(f"Mock keyword search: {query}")
        
        # Simulate search delay
        await asyncio.sleep(0.05)
        
        # Return mock results (similar to semantic but different scores)
        results = []
        for i in range(min(2, limit)):  # Return max 2 mock results
            results.append(SearchResult(
                id=f"keyword_doc_{i+1}",
                content=f"Mock keyword result {i+1} for: {query}",
                metadata={
                    "source": "mock_keyword_search",
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                },
                score=0.8 - (i * 0.2),  # Different scoring pattern
                result_type=SearchResultType.CHUNK,
                document_id=f"doc_{i+1}",
                chunk_index=i
            ))
        
        return results

    async def hybrid_search(self, query: str, limit: int) -> List[SearchResult]:
        """Mock hybrid search implementation."""
        logger.info(f"Mock hybrid search: {query}")
        
        # Combine semantic and keyword results
        semantic_results = await self.semantic_search(query, limit // 2)
        keyword_results = await self.keyword_search(query, limit // 2)
        
        # Simple combination
        all_results = semantic_results + keyword_results
        return sorted(all_results, key=lambda r: r.score, reverse=True)[:limit]


class MockDocumentStorageAdapter(DocumentStorageAdapter):
    """Mock implementation of document storage adapter."""
    
    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._document_content: Dict[str, bytes] = {}

    async def store_raw_document(
        self,
        document_id: str,
        filename: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> None:
        """Store raw document in mock storage."""
        logger.info(f"Mock storing document: {document_id}")
        
        # Simulate storage delay
        await asyncio.sleep(0.1)
        
        # Create document record
        content_hash = hashlib.sha256(content).hexdigest()
        now = datetime.utcnow()
        
        document = Document(
            id=document_id,
            filename=filename,
            content=content.decode('utf-8', errors='ignore'),  # Simple text extraction
            metadata=metadata,
            created_at=now,
            updated_at=now,
            processing_status=ProcessingStatus.COMPLETED,
            content_hash=content_hash,
            size_bytes=len(content)
        )
        
        self._documents[document_id] = document
        self._document_content[document_id] = content

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve document from mock storage."""
        return self._documents.get(document_id)

    async def list_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """List documents from mock storage."""
        documents = list(self._documents.values())
        
        # Apply filters if specified
        if filters:
            filtered_docs = []
            for doc in documents:
                if self._document_matches_filters(doc, filters):
                    filtered_docs.append(doc)
            documents = filtered_docs
        
        # Apply pagination
        end = offset + limit
        return documents[offset:end]

    async def delete_document(self, document_id: str) -> bool:
        """Delete document from mock storage."""
        if document_id in self._documents:
            del self._documents[document_id]
            self._document_content.pop(document_id, None)
            logger.info(f"Mock deleted document: {document_id}")
            return True
        return False

    async def update_processing_status(
        self, document_id: str, status: ProcessingStatus
    ) -> None:
        """Update document processing status."""
        if document_id in self._documents:
            self._documents[document_id].processing_status = status
            self._documents[document_id].updated_at = datetime.utcnow()

    async def get_processing_status(self, document_id: str) -> ProcessingStatus:
        """Get document processing status."""
        if document_id in self._documents:
            return self._documents[document_id].processing_status
        return ProcessingStatus.FAILED

    def _document_matches_filters(self, doc: Document, filters: Dict[str, Any]) -> bool:
        """Check if document matches the given filters."""
        for key, value in filters.items():
            if key == "processing_status":
                if doc.processing_status.value != value:
                    return False
            elif key == "filename":
                if value.lower() not in doc.filename.lower():
                    return False
            elif key in doc.metadata:
                if doc.metadata[key] != value:
                    return False
        return True


class MockSummarizationAdapter(SummarizationAdapter):
    """Mock implementation of summarization adapter."""

    async def generate_summary(
        self, documents: List[Document], request: "SummarizationRequest"
    ) -> SummaryResult:
        """Generate mock summary."""
        logger.info(f"Mock summarizing {len(documents)} documents")
        
        # Simulate processing time
        await asyncio.sleep(0.5)
        
        # Create mock summary
        doc_titles = [doc.filename for doc in documents]
        
        if request.summary_type == "extractive":
            summary = f"This is a mock extractive summary of documents: {', '.join(doc_titles)}. " \
                     f"Key points extracted from the content include main topics and important details."
        elif request.summary_type == "abstractive":
            summary = f"Mock abstractive summary: The documents {', '.join(doc_titles)} collectively " \
                     f"discuss various topics and provide insights into the subject matter."
        else:  # key_points
            summary = f"Key points from {', '.join(doc_titles)}:\n" \
                     f"• Main topic discussed\n" \
                     f"• Important findings\n" \
                     f"• Relevant conclusions"
        
        # Truncate to max length
        if len(summary) > request.max_length:
            summary = summary[:request.max_length-3] + "..."
        
        return SummaryResult(
            summary=summary,
            confidence_score=0.85,  # Mock confidence
            processing_time_ms=500.0
        )


class MockTextExtractionAdapter(TextExtractionAdapter):
    """Mock implementation of text extraction adapter."""

    async def extract_text(self, filename: str, content: bytes) -> str:
        """Mock text extraction."""
        logger.info(f"Mock extracting text from: {filename}")
        
        # Simulate processing delay
        await asyncio.sleep(0.2)
        
        # Simple text extraction based on file type
        if filename.lower().endswith('.pdf'):
            return f"Mock PDF content extracted from {filename}:\n\n" \
                   f"This is simulated text content from a PDF document. " \
                   f"In a real implementation, this would use PyPDF2 or similar " \
                   f"to extract actual text from the PDF file."
        
        elif filename.lower().endswith('.docx'):
            return f"Mock DOCX content from {filename}:\n\n" \
                   f"This represents text extracted from a Word document. " \
                   f"Real implementation would use python-docx library."
        
        else:
            # For text files, try to decode directly
            try:
                return content.decode('utf-8', errors='ignore')
            except:
                return f"Mock text content from {filename} (binary file detected)"

    async def process_and_chunk(self, text: str) -> List[TextChunk]:
        """Mock text processing and chunking."""
        logger.info("Mock processing and chunking text")
        
        # Simulate processing delay
        await asyncio.sleep(0.1)
        
        # Simple chunking by sentences or fixed length
        chunks = []
        chunk_size = 500  # Characters per chunk
        
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i + chunk_size]
            
            chunks.append(TextChunk(
                content=chunk_text,
                metadata={
                    "chunk_index": len(chunks),
                    "chunk_size": len(chunk_text),
                    "processing_method": "mock_chunking"
                },
                start_index=i,
                end_index=min(i + chunk_size, len(text))
            ))
        
        return chunks


class MockVectorIndexAdapter(VectorIndexAdapter):
    """Mock implementation of vector indexing adapter."""
    
    def __init__(self):
        self._indexed_documents = set()

    async def index_document(self, document_id: str, chunks: List[TextChunk]) -> None:
        """Mock document indexing."""
        logger.info(f"Mock indexing document: {document_id} ({len(chunks)} chunks)")
        
        # Simulate indexing delay
        await asyncio.sleep(0.3)
        
        self._indexed_documents.add(document_id)

    async def remove_document(self, document_id: str) -> None:
        """Mock document removal from index."""
        logger.info(f"Mock removing document from index: {document_id}")
        
        # Simulate removal delay
        await asyncio.sleep(0.1)
        
        self._indexed_documents.discard(document_id)

    async def update_document(self, document_id: str, chunks: List[TextChunk]) -> None:
        """Mock document update in index."""
        logger.info(f"Mock updating document in index: {document_id}")
        
        # Remove and re-add
        await self.remove_document(document_id)
        await self.index_document(document_id, chunks)