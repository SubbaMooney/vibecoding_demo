"""
MCP Protocol v1.0 Adapter Implementation

This module implements the MCP v1.0 protocol adapter, translating
between MCP v1.0 protocol messages and domain operations.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.mcp.core.domain import (
    ProtocolAdapter,
    SearchQuery, 
    SummarizationRequest,
    RAGDomainPort,
    DocumentProcessingPort,
)

logger = logging.getLogger(__name__)


class MCPv1Adapter(ProtocolAdapter):
    """
    MCP Protocol v1.0 implementation.
    
    This adapter handles MCP v1.0 protocol messages and translates
    them to domain operations using the RAG domain service.
    """

    def __init__(
        self, 
        rag_service: RAGDomainPort,
        document_service: DocumentProcessingPort
    ):
        """
        Initialize MCP v1.0 adapter.
        
        Args:
            rag_service: RAG domain service instance
            document_service: Document processing service instance
        """
        self._rag_service = rag_service
        self._document_service = document_service
        self._supported_tools = [
            "rag_search",
            "rag_summarize", 
            "document_upload",
            "document_list",
            "document_get",
            "document_delete",
        ]

    def get_supported_version(self) -> str:
        """Return the MCP protocol version this adapter supports."""
        return "1.0"

    def get_supported_tools(self) -> List[str]:
        """Return list of tool names supported by this adapter."""
        return self._supported_tools.copy()

    async def handle_tool_call(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle a tool call from MCP v1.0 client.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters from MCP client
            
        Returns:
            Tool execution result in MCP v1.0 format
        """
        logger.info(f"Handling MCP v1.0 tool call: {tool_name}")
        
        try:
            if tool_name == "rag_search":
                return await self._handle_rag_search(parameters)
            elif tool_name == "rag_summarize":
                return await self._handle_rag_summarize(parameters)
            elif tool_name == "document_upload":
                return await self._handle_document_upload(parameters)
            elif tool_name == "document_list":
                return await self._handle_document_list(parameters)
            elif tool_name == "document_get":
                return await self._handle_document_get(parameters)
            elif tool_name == "document_delete":
                return await self._handle_document_delete(parameters)
            else:
                raise ValueError(f"Unsupported tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Error handling tool call {tool_name}: {str(e)}")
            return {
                "error": {
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": str(e),
                    "tool": tool_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    async def _handle_rag_search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle rag_search tool call.
        
        MCP v1.0 rag_search schema:
        {
            "query": str,
            "limit": int (optional, default: 10),
            "threshold": float (optional, default: 0.7),
            "search_type": str (optional, default: "semantic")
        }
        """
        # Validate required parameters
        if "query" not in parameters:
            raise ValueError("Missing required parameter: query")
        
        # Build search query
        search_query = SearchQuery(
            query=parameters["query"],
            limit=parameters.get("limit", 10),
            threshold=parameters.get("threshold", 0.7),
            search_type=parameters.get("search_type", "semantic"),
            filters=parameters.get("filters")
        )
        
        # Execute search
        search_response = await self._rag_service.search_documents(search_query)
        
        # Convert to MCP v1.0 format
        return {
            "results": [
                {
                    "id": result.id,
                    "content": result.content,
                    "score": result.score,
                    "metadata": result.metadata,
                    "type": result.result_type.value,
                    "document_id": result.document_id,
                }
                for result in search_response.results
            ],
            "total_results": search_response.total_results,
            "processing_time_ms": search_response.processing_time_ms,
            "query_metadata": {
                "original_query": search_response.query.query,
                "search_type": search_response.query.search_type,
                "threshold": search_response.query.threshold,
            }
        }

    async def _handle_rag_summarize(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle rag_summarize tool call.
        
        MCP v1.0 rag_summarize schema:
        {
            "document_ids": List[str],
            "summary_type": str (optional, default: "extractive"),
            "max_length": int (optional, default: 500)
        }
        """
        # Validate required parameters
        if "document_ids" not in parameters:
            raise ValueError("Missing required parameter: document_ids")
        
        if not isinstance(parameters["document_ids"], list):
            raise ValueError("document_ids must be a list")
        
        # Build summarization request
        summarization_request = SummarizationRequest(
            document_ids=parameters["document_ids"],
            summary_type=parameters.get("summary_type", "extractive"),
            max_length=parameters.get("max_length", 500),
            language=parameters.get("language", "en")
        )
        
        # Execute summarization
        summary_response = await self._rag_service.summarize_documents(
            summarization_request
        )
        
        # Convert to MCP v1.0 format
        return {
            "summary": summary_response.summary,
            "summary_type": summary_response.summary_type,
            "source_documents": summary_response.source_documents,
            "confidence_score": summary_response.confidence_score,
            "processing_time_ms": summary_response.processing_time_ms,
        }

    async def _handle_document_upload(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle document_upload tool call.
        
        MCP v1.0 document_upload schema:
        {
            "filename": str,
            "content": str (base64 encoded),
            "metadata": dict (optional)
        }
        """
        # Validate required parameters
        if "filename" not in parameters:
            raise ValueError("Missing required parameter: filename")
        
        if "content" not in parameters:
            raise ValueError("Missing required parameter: content")
        
        # Decode base64 content
        import base64
        try:
            content_bytes = base64.b64decode(parameters["content"])
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {str(e)}")
        
        # Upload document
        document_id = await self._document_service.upload_document(
            filename=parameters["filename"],
            content=content_bytes,
            metadata=parameters.get("metadata", {})
        )
        
        return {
            "document_id": document_id,
            "status": "uploaded",
            "filename": parameters["filename"],
            "uploaded_at": datetime.utcnow().isoformat(),
        }

    async def _handle_document_list(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle document_list tool call.
        
        MCP v1.0 document_list schema:
        {
            "limit": int (optional, default: 50),
            "offset": int (optional, default: 0),
            "filters": dict (optional)
        }
        """
        # Get parameters with defaults
        limit = parameters.get("limit", 50)
        offset = parameters.get("offset", 0)
        filters = parameters.get("filters")
        
        # List documents
        documents = await self._rag_service.list_documents(
            limit=limit, offset=offset, filters=filters
        )
        
        # Convert to MCP v1.0 format
        return {
            "documents": [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "size_bytes": doc.size_bytes,
                    "processing_status": doc.processing_status.value,
                    "metadata": doc.metadata,
                }
                for doc in documents
            ],
            "total_count": len(documents),
            "limit": limit,
            "offset": offset,
        }

    async def _handle_document_get(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle document_get tool call.
        
        MCP v1.0 document_get schema:
        {
            "document_id": str
        }
        """
        # Validate required parameters
        if "document_id" not in parameters:
            raise ValueError("Missing required parameter: document_id")
        
        # Get document
        document = await self._rag_service.get_document(parameters["document_id"])
        
        if not document:
            return {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document not found: {parameters['document_id']}"
                }
            }
        
        # Convert to MCP v1.0 format
        return {
            "document": {
                "id": str(document.id),
                "filename": document.filename,
                "content": document.content,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "size_bytes": document.size_bytes,
                "processing_status": document.processing_status.value,
                "content_hash": document.content_hash,
                "metadata": document.metadata,
            }
        }

    async def _handle_document_delete(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle document_delete tool call.
        
        MCP v1.0 document_delete schema:
        {
            "document_id": str
        }
        """
        # Validate required parameters  
        if "document_id" not in parameters:
            raise ValueError("Missing required parameter: document_id")
        
        # Delete document
        success = await self._document_service.delete_document(
            parameters["document_id"]
        )
        
        return {
            "success": success,
            "document_id": parameters["document_id"],
            "deleted_at": datetime.utcnow().isoformat(),
        }

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the JSON schema for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            JSON schema for the tool, or None if tool not found
        """
        schemas = {
            "rag_search": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum number of results to return"
                    },
                    "threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.7,
                        "description": "Minimum similarity score threshold"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "default": "semantic",
                        "description": "Type of search to perform"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Additional filters to apply"
                    }
                },
                "required": ["query"]
            },
            "rag_summarize": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document IDs to summarize"
                    },
                    "summary_type": {
                        "type": "string",
                        "enum": ["extractive", "abstractive", "key_points"],
                        "default": "extractive",
                        "description": "Type of summary to generate"
                    },
                    "max_length": {
                        "type": "integer",
                        "minimum": 50,
                        "maximum": 2000,
                        "default": 500,
                        "description": "Maximum length of summary in characters"
                    },
                    "language": {
                        "type": "string",
                        "default": "en",
                        "description": "Language for the summary"
                    }
                },
                "required": ["document_ids"]
            },
            "document_upload": {
                "type": "object", 
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Original filename"
                    },
                    "content": {
                        "type": "string",
                        "description": "Base64 encoded file content"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata for the document"
                    }
                },
                "required": ["filename", "content"]
            },
            "document_list": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                        "description": "Maximum number of documents to return"
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of documents to skip"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filters to apply to document list"
                    }
                }
            },
            "document_get": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "ID of the document to retrieve"
                    }
                },
                "required": ["document_id"]
            },
            "document_delete": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string", 
                        "description": "ID of the document to delete"
                    }
                },
                "required": ["document_id"]
            }
        }
        
        return schemas.get(tool_name)