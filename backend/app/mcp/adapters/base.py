"""
Base adapter interfaces for the hexagonal architecture.

This module defines the secondary port interfaces that concrete
adapters must implement to integrate with external systems.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from app.mcp.core.domain import Document, SearchResult, ProcessingStatus


@dataclass
class SummaryResult:
    """Result of document summarization operation."""
    summary: str
    confidence_score: float
    processing_time_ms: float


@dataclass
class TextChunk:
    """Represents a chunk of processed text."""
    content: str
    metadata: Dict[str, Any]
    start_index: int
    end_index: int


class VectorSearchAdapter(ABC):
    """
    Secondary port for vector search operations.
    
    Concrete implementations will integrate with specific vector
    databases like Qdrant, Pinecone, or Weaviate.
    """

    @abstractmethod
    async def semantic_search(
        self, query: str, limit: int
    ) -> List[SearchResult]:
        """Perform semantic vector search."""
        pass

    @abstractmethod
    async def keyword_search(
        self, query: str, limit: int
    ) -> List[SearchResult]:
        """Perform keyword-based search."""
        pass

    @abstractmethod
    async def hybrid_search(
        self, query: str, limit: int
    ) -> List[SearchResult]:
        """Perform hybrid semantic + keyword search."""
        pass


class DocumentStorageAdapter(ABC):
    """
    Secondary port for document storage operations.
    
    Concrete implementations will integrate with databases
    like PostgreSQL, MongoDB, or cloud storage services.
    """

    @abstractmethod
    async def store_raw_document(
        self,
        document_id: str,
        filename: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> None:
        """Store raw document content."""
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve document by ID."""
        pass

    @abstractmethod
    async def list_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """List documents with pagination."""
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """Delete document and metadata."""
        pass

    @abstractmethod
    async def update_processing_status(
        self, document_id: str, status: ProcessingStatus
    ) -> None:
        """Update document processing status."""
        pass

    @abstractmethod
    async def get_processing_status(
        self, document_id: str
    ) -> ProcessingStatus:
        """Get current processing status."""
        pass


class SummarizationAdapter(ABC):
    """
    Secondary port for document summarization.
    
    Concrete implementations will integrate with LLM services
    or local summarization models.
    """

    @abstractmethod
    async def generate_summary(
        self, documents: List[Document], request: "SummarizationRequest"
    ) -> SummaryResult:
        """Generate summary from documents."""
        pass


class TextExtractionAdapter(ABC):
    """
    Secondary port for text extraction from documents.
    
    Concrete implementations will handle different file formats
    using libraries like PyPDF2, python-docx, etc.
    """

    @abstractmethod
    async def extract_text(self, filename: str, content: bytes) -> str:
        """Extract text content from document."""
        pass

    @abstractmethod
    async def process_and_chunk(self, text: str) -> List[TextChunk]:
        """Process text and split into chunks."""
        pass


class VectorIndexAdapter(ABC):
    """
    Secondary port for vector indexing operations.
    
    Handles creating embeddings and indexing documents
    for semantic search.
    """

    @abstractmethod
    async def index_document(
        self, document_id: str, chunks: List[TextChunk]
    ) -> None:
        """Index document chunks for search."""
        pass

    @abstractmethod
    async def remove_document(self, document_id: str) -> None:
        """Remove document from search index."""
        pass

    @abstractmethod
    async def update_document(
        self, document_id: str, chunks: List[TextChunk]
    ) -> None:
        """Update existing document in index."""
        pass


class ProtocolVersionRegistry:
    """
    Registry for managing different MCP protocol versions.
    
    This class maintains the mapping between protocol versions
    and their corresponding adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, "ProtocolAdapter"] = {}
        self._compatibility_matrix: Dict[str, Dict[str, bool]] = {}

    def register_adapter(self, adapter: "ProtocolAdapter") -> None:
        """Register a protocol adapter."""
        version = adapter.get_supported_version()
        self._adapters[version] = adapter

    def get_adapter(self, version: str) -> Optional["ProtocolAdapter"]:
        """Get adapter for specific protocol version."""
        return self._adapters.get(version)

    def get_supported_versions(self) -> List[str]:
        """Get list of supported protocol versions."""
        return list(self._adapters.keys())

    def set_compatibility(
        self, 
        version1: str, 
        version2: str, 
        compatible: bool
    ) -> None:
        """Set compatibility between two protocol versions."""
        if version1 not in self._compatibility_matrix:
            self._compatibility_matrix[version1] = {}
        self._compatibility_matrix[version1][version2] = compatible

    def are_compatible(self, version1: str, version2: str) -> bool:
        """Check if two protocol versions are compatible."""
        return self._compatibility_matrix.get(version1, {}).get(version2, False)

    def find_best_version(
        self, 
        client_versions: List[str]
    ) -> Optional[str]:
        """
        Find the best protocol version to use with a client.
        
        Args:
            client_versions: List of versions supported by client
            
        Returns:
            Best version to use, or None if no compatibility
        """
        # Prefer exact matches first
        for version in client_versions:
            if version in self._adapters:
                return version
        
        # Then look for compatible versions
        for client_version in client_versions:
            for server_version in self._adapters:
                if self.are_compatible(server_version, client_version):
                    return server_version
        
        return None