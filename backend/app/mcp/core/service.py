"""
Core RAG domain service implementation.

This module implements the core business logic for RAG operations,
following domain-driven design principles.
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import uuid4

from app.mcp.core.domain import (
    Document,
    DocumentProcessingPort,
    ProcessingStatus,
    RAGDomainPort,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchResultType,
    SummarizationRequest,
    SummarizationResponse,
)

logger = logging.getLogger(__name__)


class RAGDomainService:
    """
    Core domain service implementing RAG business logic.
    
    This service coordinates between different adapters and implements
    the core business rules for document search and processing.
    """

    def __init__(
        self,
        vector_search_adapter: "VectorSearchAdapter",
        document_storage_adapter: "DocumentStorageAdapter",
        summarization_adapter: "SummarizationAdapter",
    ):
        """
        Initialize the RAG domain service.
        
        Args:
            vector_search_adapter: Adapter for vector search operations
            document_storage_adapter: Adapter for document storage
            summarization_adapter: Adapter for document summarization
        """
        self._vector_search = vector_search_adapter
        self._document_storage = document_storage_adapter
        self._summarization = summarization_adapter

    async def search_documents(self, query: SearchQuery) -> SearchResponse:
        """
        Implement semantic document search with hybrid capabilities.
        
        This method orchestrates the search process, combining semantic
        and keyword search based on the query parameters.
        """
        logger.info(f"Processing search query: {query.query}")
        
        try:
            # Validate query parameters
            if not query.query.strip():
                raise ValueError("Search query cannot be empty")
            
            if query.limit <= 0 or query.limit > 100:
                raise ValueError("Search limit must be between 1 and 100")
            
            # Perform search based on type
            if query.search_type == "semantic":
                results = await self._perform_semantic_search(query)
            elif query.search_type == "keyword":
                results = await self._perform_keyword_search(query)
            elif query.search_type == "hybrid":
                results = await self._perform_hybrid_search(query)
            else:
                raise ValueError(f"Unsupported search type: {query.search_type}")
            
            # Apply post-processing filters
            filtered_results = await self._apply_filters(results, query.filters)
            
            # Apply threshold filtering
            thresholded_results = [
                r for r in filtered_results if r.score >= query.threshold
            ]
            
            # Limit results
            limited_results = thresholded_results[:query.limit]
            
            # Enrich results with additional metadata
            enriched_results = await self._enrich_search_results(limited_results)
            
            return SearchResponse(
                results=enriched_results,
                query=query,
                total_results=len(thresholded_results),
                processing_time_ms=0.0,  # Will be calculated by adapter
                search_metadata={
                    "search_type": query.search_type,
                    "threshold_applied": query.threshold,
                    "filters_applied": bool(query.filters),
                }
            )
            
        except Exception as e:
            logger.error(f"Error in document search: {str(e)}")
            raise

    async def summarize_documents(
        self, request: SummarizationRequest
    ) -> SummarizationResponse:
        """
        Generate summaries from specified documents.
        
        This method coordinates document retrieval and summarization,
        handling different summary types and validation.
        """
        logger.info(f"Generating summary for {len(request.document_ids)} documents")
        
        try:
            # Validate request
            if not request.document_ids:
                raise ValueError("Document IDs cannot be empty")
            
            if request.max_length <= 0:
                raise ValueError("Max length must be positive")
            
            # Retrieve documents
            documents = []
            for doc_id in request.document_ids:
                doc = await self.get_document(doc_id)
                if doc:
                    documents.append(doc)
                else:
                    logger.warning(f"Document not found: {doc_id}")
            
            if not documents:
                raise ValueError("No valid documents found for summarization")
            
            # Generate summary
            summary_result = await self._summarization.generate_summary(
                documents, request
            )
            
            return SummarizationResponse(
                summary=summary_result.summary,
                source_documents=request.document_ids,
                summary_type=request.summary_type,
                confidence_score=summary_result.confidence_score,
                processing_time_ms=summary_result.processing_time_ms,
            )
            
        except Exception as e:
            logger.error(f"Error in document summarization: {str(e)}")
            raise

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID from storage."""
        try:
            return await self._document_storage.get_document(document_id)
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {str(e)}")
            return None

    async def list_documents(
        self, 
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """List documents with pagination and filtering."""
        try:
            return await self._document_storage.list_documents(
                limit=limit, offset=offset, filters=filters
            )
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return []

    async def _perform_semantic_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform semantic vector search."""
        return await self._vector_search.semantic_search(
            query.query, query.limit * 2  # Get extra results for filtering
        )

    async def _perform_keyword_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform keyword-based search."""
        return await self._vector_search.keyword_search(
            query.query, query.limit * 2
        )

    async def _perform_hybrid_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform hybrid semantic + keyword search."""
        # Get results from both search types
        semantic_results = await self._perform_semantic_search(query)
        keyword_results = await self._perform_keyword_search(query)
        
        # Combine and rerank results
        return await self._combine_and_rerank(semantic_results, keyword_results)

    async def _apply_filters(
        self, 
        results: List[SearchResult], 
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Apply additional filters to search results."""
        if not filters:
            return results
        
        filtered = []
        for result in results:
            if self._passes_filters(result, filters):
                filtered.append(result)
        
        return filtered

    def _passes_filters(self, result: SearchResult, filters: Dict[str, Any]) -> bool:
        """Check if a result passes the specified filters."""
        for filter_key, filter_value in filters.items():
            if filter_key in result.metadata:
                if result.metadata[filter_key] != filter_value:
                    return False
            else:
                return False
        return True

    async def _enrich_search_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Enrich search results with additional metadata."""
        # This can be extended to add more metadata
        for result in results:
            result.metadata["enriched_at"] = "2024-09-24T22:00:00Z"
        return results

    async def _combine_and_rerank(
        self, 
        semantic_results: List[SearchResult], 
        keyword_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Combine semantic and keyword results with hybrid ranking."""
        # Simple hybrid ranking - can be made more sophisticated
        combined = {}
        
        # Add semantic results with weight
        for result in semantic_results:
            combined[result.id] = result
            combined[result.id].score *= 0.7  # Semantic weight
        
        # Add keyword results, boosting if already present
        for result in keyword_results:
            if result.id in combined:
                # Boost existing result
                combined[result.id].score += (result.score * 0.3)
            else:
                # Add new result with keyword weight
                result.score *= 0.3
                combined[result.id] = result
        
        # Sort by combined score
        return sorted(combined.values(), key=lambda r: r.score, reverse=True)


class DocumentProcessingService:
    """Service for handling document upload and processing operations."""

    def __init__(
        self,
        document_storage_adapter: "DocumentStorageAdapter",
        text_extraction_adapter: "TextExtractionAdapter",
        vector_index_adapter: "VectorIndexAdapter",
    ):
        """Initialize the document processing service."""
        self._document_storage = document_storage_adapter
        self._text_extraction = text_extraction_adapter
        self._vector_index = vector_index_adapter

    async def upload_document(
        self,
        filename: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Handle document upload and processing pipeline.
        
        This orchestrates the entire document processing workflow:
        1. Validate and store the raw document
        2. Extract text content
        3. Process and chunk the text
        4. Create vector embeddings
        5. Store in search index
        """
        logger.info(f"Processing document upload: {filename}")
        
        try:
            # Generate document ID
            document_id = str(uuid4())
            
            # Validate document
            await self._validate_document(filename, content)
            
            # Store raw document
            await self._document_storage.store_raw_document(
                document_id, filename, content, metadata or {}
            )
            
            # Extract text content
            text_content = await self._text_extraction.extract_text(
                filename, content
            )
            
            # Process and chunk text
            chunks = await self._text_extraction.process_and_chunk(text_content)
            
            # Create vector embeddings
            await self._vector_index.index_document(document_id, chunks)
            
            # Update document status
            await self._document_storage.update_processing_status(
                document_id, ProcessingStatus.COMPLETED
            )
            
            logger.info(f"Successfully processed document: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            # Update status to failed if document was created
            if 'document_id' in locals():
                await self._document_storage.update_processing_status(
                    document_id, ProcessingStatus.FAILED
                )
            raise

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and clean up all associated data."""
        try:
            # Remove from vector index
            await self._vector_index.remove_document(document_id)
            
            # Remove from storage
            result = await self._document_storage.delete_document(document_id)
            
            logger.info(f"Deleted document: {document_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return False

    async def get_processing_status(self, document_id: str) -> ProcessingStatus:
        """Get current processing status of a document."""
        try:
            return await self._document_storage.get_processing_status(document_id)
        except Exception as e:
            logger.error(f"Error getting status for {document_id}: {str(e)}")
            return ProcessingStatus.FAILED

    async def _validate_document(self, filename: str, content: bytes) -> None:
        """Validate document before processing."""
        if len(content) == 0:
            raise ValueError("Document content cannot be empty")
        
        if len(content) > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError("Document size exceeds 50MB limit")
        
        # Additional validation based on file type
        file_extension = filename.lower().split('.')[-1]
        if file_extension not in ['pdf', 'docx', 'txt', 'md']:
            raise ValueError(f"Unsupported file type: {file_extension}")