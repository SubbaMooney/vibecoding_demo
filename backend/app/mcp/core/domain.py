"""
Core domain models and interfaces for RAG operations.

This module defines the protocol-agnostic domain models and interfaces
that form the core of the MCP abstraction layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID


class SearchResultType(Enum):
    """Types of search results returned by RAG operations."""
    DOCUMENT = "document"
    CHUNK = "chunk"
    SUMMARY = "summary"


class ProcessingStatus(Enum):
    """Status of document processing operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SearchQuery:
    """Represents a search query with all necessary parameters."""
    query: str
    limit: int = 10
    threshold: float = 0.7
    filters: Optional[Dict[str, Any]] = None
    search_type: str = "semantic"  # semantic, keyword, hybrid


@dataclass
class SearchResult:
    """Represents a single search result."""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    result_type: SearchResultType
    document_id: Optional[str] = None
    chunk_index: Optional[int] = None


@dataclass
class SearchResponse:
    """Complete search response with results and metadata."""
    results: List[SearchResult]
    query: SearchQuery
    total_results: int
    processing_time_ms: float
    search_metadata: Dict[str, Any]


@dataclass
class Document:
    """Represents a document in the RAG system."""
    id: UUID
    filename: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    processing_status: ProcessingStatus
    content_hash: str
    size_bytes: int


@dataclass
class SummarizationRequest:
    """Request for document summarization."""
    document_ids: List[str]
    summary_type: str = "extractive"  # extractive, abstractive, key_points
    max_length: int = 500
    language: str = "en"


@dataclass
class SummarizationResponse:
    """Response containing document summary."""
    summary: str
    source_documents: List[str]
    summary_type: str
    confidence_score: float
    processing_time_ms: float


class RAGDomainPort(ABC):
    """
    Primary port for RAG domain operations.
    
    This interface defines the core business operations that can be
    performed regardless of the protocol used to access them.
    """

    @abstractmethod
    async def search_documents(self, query: SearchQuery) -> SearchResponse:
        """
        Perform semantic search across documents.
        
        Args:
            query: Search query with parameters
            
        Returns:
            Search response with results and metadata
        """
        pass

    @abstractmethod
    async def summarize_documents(
        self, request: SummarizationRequest
    ) -> SummarizationResponse:
        """
        Generate summaries from documents.
        
        Args:
            request: Summarization request with parameters
            
        Returns:
            Summary response with generated content
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        Retrieve a specific document by ID.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_documents(
        self, 
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        List documents with pagination and filtering.
        
        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip
            filters: Optional filters to apply
            
        Returns:
            List of documents matching criteria
        """
        pass


class DocumentProcessingPort(ABC):
    """
    Port for document processing operations.
    
    This interface defines operations for uploading, processing,
    and managing documents in the system.
    """

    @abstractmethod
    async def upload_document(
        self,
        filename: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload and process a new document.
        
        Args:
            filename: Original filename
            content: Document content as bytes
            metadata: Optional metadata
            
        Returns:
            Document ID of the uploaded document
        """
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the system.
        
        Args:
            document_id: Document to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_processing_status(self, document_id: str) -> ProcessingStatus:
        """
        Get the processing status of a document.
        
        Args:
            document_id: Document to check
            
        Returns:
            Current processing status
        """
        pass


class ProtocolAdapter(ABC):
    """
    Base class for MCP protocol adapters.
    
    Each MCP protocol version will have its own adapter implementation
    that translates protocol-specific messages to domain operations.
    """

    @abstractmethod
    def get_supported_version(self) -> str:
        """Return the MCP protocol version this adapter supports."""
        pass

    @abstractmethod
    def get_supported_tools(self) -> List[str]:
        """Return list of tool names supported by this adapter."""
        pass

    @abstractmethod
    async def handle_tool_call(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle a tool call from the MCP client.
        
        Args:
            tool_name: Name of the tool to call
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        pass


class ProtocolNegotiator(ABC):
    """
    Interface for MCP protocol version negotiation.
    
    This handles automatic detection and negotiation of the best
    protocol version to use with each client.
    """

    @abstractmethod
    async def negotiate_protocol(
        self, 
        client_capabilities: Dict[str, Any]
    ) -> str:
        """
        Negotiate the best protocol version with a client.
        
        Args:
            client_capabilities: Client's declared capabilities
            
        Returns:
            Negotiated protocol version
        """
        pass

    @abstractmethod
    def get_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """
        Get the compatibility matrix for protocol versions.
        
        Returns:
            Matrix showing compatibility between versions
        """
        pass