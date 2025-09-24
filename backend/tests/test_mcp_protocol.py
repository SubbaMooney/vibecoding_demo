"""
Tests for MCP Protocol Implementation

This module contains comprehensive tests for the MCP protocol
abstraction layer, adapters, and server implementation.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.mcp.core.domain import (
    SearchQuery, 
    SearchResponse, 
    SearchResult, 
    SearchResultType,
    SummarizationRequest,
    SummarizationResponse,
    Document,
    ProcessingStatus
)
from app.mcp.core.service import RAGDomainService, DocumentProcessingService
from app.mcp.adapters.base import ProtocolVersionRegistry
from app.mcp.adapters.mcp_v1 import MCPv1Adapter
from app.mcp.negotiation import MCPProtocolNegotiator
from app.mcp.server import MCPServer, MCPConnection
from app.mcp.monitoring import MCPMonitor
from app.mcp.adapters.mock_adapters import (
    MockVectorSearchAdapter,
    MockDocumentStorageAdapter,
    MockSummarizationAdapter
)


class TestMCPDomainService:
    """Test the core RAG domain service."""

    @pytest.fixture
    def domain_service(self):
        """Create a domain service with mock adapters."""
        return RAGDomainService(
            vector_search_adapter=MockVectorSearchAdapter(),
            document_storage_adapter=MockDocumentStorageAdapter(),
            summarization_adapter=MockSummarizationAdapter()
        )

    @pytest.mark.asyncio
    async def test_search_documents_semantic(self, domain_service):
        """Test semantic document search."""
        query = SearchQuery(
            query="test query",
            limit=5,
            threshold=0.7,
            search_type="semantic"
        )
        
        response = await domain_service.search_documents(query)
        
        assert isinstance(response, SearchResponse)
        assert response.query.query == "test query"
        assert len(response.results) <= 5
        assert all(result.score >= 0.7 for result in response.results)
        assert response.search_metadata["search_type"] == "semantic"

    @pytest.mark.asyncio
    async def test_search_documents_hybrid(self, domain_service):
        """Test hybrid document search."""
        query = SearchQuery(
            query="test query",
            search_type="hybrid"
        )
        
        response = await domain_service.search_documents(query)
        
        assert isinstance(response, SearchResponse)
        assert response.search_metadata["search_type"] == "hybrid"
        # Should have results from both semantic and keyword search
        assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_search_documents_validation(self, domain_service):
        """Test search query validation."""
        # Test empty query
        with pytest.raises(ValueError, match="cannot be empty"):
            await domain_service.search_documents(SearchQuery(query=""))
        
        # Test invalid limit
        with pytest.raises(ValueError, match="between 1 and 100"):
            await domain_service.search_documents(SearchQuery(query="test", limit=0))
        
        with pytest.raises(ValueError, match="between 1 and 100"):
            await domain_service.search_documents(SearchQuery(query="test", limit=101))

    @pytest.mark.asyncio
    async def test_summarize_documents(self, domain_service):
        """Test document summarization."""
        request = SummarizationRequest(
            document_ids=["doc1", "doc2"],
            summary_type="extractive",
            max_length=500
        )
        
        # Mock document retrieval
        with patch.object(domain_service, 'get_document') as mock_get:
            mock_get.side_effect = [
                Document(
                    id="doc1",
                    filename="test1.pdf",
                    content="Test content 1",
                    metadata={},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    processing_status=ProcessingStatus.COMPLETED,
                    content_hash="hash1",
                    size_bytes=100
                ),
                Document(
                    id="doc2", 
                    filename="test2.pdf",
                    content="Test content 2",
                    metadata={},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    processing_status=ProcessingStatus.COMPLETED,
                    content_hash="hash2",
                    size_bytes=100
                )
            ]
            
            response = await domain_service.summarize_documents(request)
            
            assert isinstance(response, SummarizationResponse)
            assert response.summary_type == "extractive"
            assert response.source_documents == ["doc1", "doc2"]
            assert len(response.summary) <= 500


class TestMCPv1Adapter:
    """Test the MCP v1.0 protocol adapter."""

    @pytest.fixture
    def adapter(self):
        """Create MCP v1.0 adapter with mock services."""
        rag_service = RAGDomainService(
            vector_search_adapter=MockVectorSearchAdapter(),
            document_storage_adapter=MockDocumentStorageAdapter(), 
            summarization_adapter=MockSummarizationAdapter()
        )
        
        from app.mcp.adapters.mock_adapters import (
            MockTextExtractionAdapter,
            MockVectorIndexAdapter
        )
        
        document_service = DocumentProcessingService(
            document_storage_adapter=MockDocumentStorageAdapter(),
            text_extraction_adapter=MockTextExtractionAdapter(),
            vector_index_adapter=MockVectorIndexAdapter()
        )
        
        return MCPv1Adapter(rag_service, document_service)

    def test_supported_version(self, adapter):
        """Test adapter returns correct version."""
        assert adapter.get_supported_version() == "1.0"

    def test_supported_tools(self, adapter):
        """Test adapter returns expected tools."""
        tools = adapter.get_supported_tools()
        expected_tools = [
            "rag_search", "rag_summarize", "document_upload",
            "document_list", "document_get", "document_delete"
        ]
        
        assert all(tool in tools for tool in expected_tools)

    @pytest.mark.asyncio
    async def test_rag_search_tool(self, adapter):
        """Test rag_search tool call."""
        parameters = {
            "query": "test search",
            "limit": 5,
            "threshold": 0.8,
            "search_type": "semantic"
        }
        
        result = await adapter.handle_tool_call("rag_search", parameters)
        
        assert "results" in result
        assert "total_results" in result
        assert "processing_time_ms" in result
        assert "query_metadata" in result
        assert result["query_metadata"]["original_query"] == "test search"

    @pytest.mark.asyncio
    async def test_rag_search_missing_query(self, adapter):
        """Test rag_search with missing query parameter."""
        result = await adapter.handle_tool_call("rag_search", {})
        
        assert "error" in result
        assert result["error"]["code"] == "TOOL_EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_document_upload_tool(self, adapter):
        """Test document_upload tool call."""
        import base64
        
        content = b"Test document content"
        encoded_content = base64.b64encode(content).decode()
        
        parameters = {
            "filename": "test.txt",
            "content": encoded_content,
            "metadata": {"author": "test"}
        }
        
        result = await adapter.handle_tool_call("document_upload", parameters)
        
        assert "document_id" in result
        assert result["filename"] == "test.txt"
        assert result["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_unsupported_tool(self, adapter):
        """Test calling unsupported tool."""
        result = await adapter.handle_tool_call("unknown_tool", {})
        
        assert "error" in result
        assert result["error"]["code"] == "TOOL_EXECUTION_ERROR"

    def test_tool_schemas(self, adapter):
        """Test tool schema retrieval."""
        schema = adapter.get_tool_schema("rag_search")
        
        assert schema is not None
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"


class TestMCPProtocolNegotiator:
    """Test MCP protocol version negotiation."""

    @pytest.fixture
    def negotiator(self):
        """Create protocol negotiator with test registry."""
        registry = ProtocolVersionRegistry()
        
        # Create mock adapter
        mock_adapter = MagicMock()
        mock_adapter.get_supported_version.return_value = "1.0"
        mock_adapter.get_supported_tools.return_value = ["rag_search", "rag_summarize"]
        
        registry.register_adapter(mock_adapter)
        registry.set_compatibility("1.0", "1.0", True)
        registry.set_compatibility("1.0", "0.9", True)
        
        return MCPProtocolNegotiator(registry)

    @pytest.mark.asyncio
    async def test_exact_version_match(self, negotiator):
        """Test negotiation with exact version match."""
        capabilities = {
            "protocolVersion": "1.0",
            "features": ["rag_search"]
        }
        
        version = await negotiator.negotiate_protocol(capabilities)
        assert version == "1.0"

    @pytest.mark.asyncio
    async def test_compatible_version(self, negotiator):
        """Test negotiation with compatible version."""
        capabilities = {
            "supportedVersions": ["0.9"],
            "features": ["rag_search"]
        }
        
        version = await negotiator.negotiate_protocol(capabilities)
        assert version == "1.0"  # Server can handle client v0.9

    @pytest.mark.asyncio
    async def test_no_compatible_version(self, negotiator):
        """Test negotiation failure with incompatible versions."""
        capabilities = {
            "supportedVersions": ["2.0"],
            "features": ["rag_search"]
        }
        
        with pytest.raises(ValueError, match="No compatible MCP protocol version"):
            await negotiator.negotiate_protocol(capabilities)

    @pytest.mark.asyncio
    async def test_default_version_fallback(self, negotiator):
        """Test fallback to default version when no version specified."""
        capabilities = {
            "features": ["rag_search"]
        }
        
        version = await negotiator.negotiate_protocol(capabilities)
        assert version == "1.0"

    def test_compatibility_matrix(self, negotiator):
        """Test compatibility matrix retrieval."""
        matrix = negotiator.get_compatibility_matrix()
        
        assert "1.0" in matrix
        assert matrix["1.0"]["1.0"] is True
        assert matrix["1.0"]["0.9"] is True


class TestMCPMonitor:
    """Test MCP protocol monitoring."""

    @pytest.fixture
    def monitor(self):
        """Create MCP monitor."""
        return MCPMonitor(retention_hours=1)

    @pytest.mark.asyncio
    async def test_connection_tracking(self, monitor):
        """Test connection lifecycle tracking."""
        connection_id = "test-conn-1"
        
        # Start connection
        await monitor.track_connection_started(
            connection_id, "1.0", {"client": "test"}
        )
        
        # Check metrics
        metrics = await monitor.get_metrics_summary()
        assert metrics["connections"]["active"] == 1
        
        # End connection
        await monitor.track_connection_ended(connection_id)
        
        # Check updated metrics
        updated_metrics = await monitor.get_metrics_summary()
        assert updated_metrics["connections"]["active"] == 0
        assert updated_metrics["connections"]["total_since_start"] == 1

    @pytest.mark.asyncio
    async def test_tool_call_tracking(self, monitor):
        """Test tool call metrics tracking."""
        await monitor.track_tool_call(
            "test-conn", "rag_search", 0.5, success=True
        )
        await monitor.track_tool_call(
            "test-conn", "rag_search", 1.0, success=False, error_type="ValueError"
        )
        
        metrics = await monitor.get_metrics_summary()
        
        assert "rag_search" in metrics["tools"]
        tool_metrics = metrics["tools"]["rag_search"]
        assert tool_metrics["total_calls"] == 2
        assert tool_metrics["success_rate"] == 0.5
        assert "ValueError" in tool_metrics["error_types"]

    @pytest.mark.asyncio 
    async def test_health_status(self, monitor):
        """Test health status assessment."""
        health = await monitor.get_health_status()
        
        assert "status" in health
        assert "timestamp" in health
        assert "issues" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_high_error_rate_alert(self, monitor):
        """Test alert generation for high error rates."""
        # Generate many failed tool calls
        for i in range(20):
            await monitor.track_tool_call(
                f"conn-{i}", "rag_search", 0.1, success=False
            )
        
        health = await monitor.get_health_status()
        
        # Should trigger high error rate alert
        error_issues = [
            issue for issue in health["issues"] 
            if issue["type"] == "high_error_rate"
        ]
        assert len(error_issues) > 0
        assert health["status"] != "healthy"


class TestMCPIntegration:
    """Integration tests for MCP components."""

    @pytest.fixture
    async def mcp_setup(self):
        """Set up complete MCP system for integration testing."""
        # Create registry and register adapter
        registry = ProtocolVersionRegistry()
        
        # Create services
        rag_service = RAGDomainService(
            vector_search_adapter=MockVectorSearchAdapter(),
            document_storage_adapter=MockDocumentStorageAdapter(),
            summarization_adapter=MockSummarizationAdapter()
        )
        
        from app.mcp.adapters.mock_adapters import (
            MockTextExtractionAdapter,
            MockVectorIndexAdapter
        )
        
        document_service = DocumentProcessingService(
            document_storage_adapter=MockDocumentStorageAdapter(),
            text_extraction_adapter=MockTextExtractionAdapter(),
            vector_index_adapter=MockVectorIndexAdapter()
        )
        
        # Create and register adapter
        adapter = MCPv1Adapter(rag_service, document_service)
        registry.register_adapter(adapter)
        
        # Create negotiator
        negotiator = MCPProtocolNegotiator(registry)
        
        # Create monitor
        monitor = MCPMonitor()
        
        # Create server
        server = MCPServer(registry, negotiator, monitor)
        
        return {
            "server": server,
            "registry": registry,
            "negotiator": negotiator,
            "monitor": monitor,
            "rag_service": rag_service,
            "document_service": document_service
        }

    @pytest.mark.asyncio
    async def test_end_to_end_search_flow(self, mcp_setup):
        """Test complete search workflow through MCP."""
        setup = await mcp_setup
        adapter = setup["registry"].get_adapter("1.0")
        
        # Simulate tool call
        result = await adapter.handle_tool_call("rag_search", {
            "query": "test query",
            "limit": 3
        })
        
        assert "results" in result
        assert len(result["results"]) <= 3
        assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_document_upload_and_search_flow(self, mcp_setup):
        """Test document upload followed by search."""
        setup = await mcp_setup
        adapter = setup["registry"].get_adapter("1.0")
        
        # Upload document
        import base64
        content = b"This is test document content for searching"
        
        upload_result = await adapter.handle_tool_call("document_upload", {
            "filename": "test.txt",
            "content": base64.b64encode(content).decode()
        })
        
        assert "document_id" in upload_result
        document_id = upload_result["document_id"]
        
        # Search for content
        search_result = await adapter.handle_tool_call("rag_search", {
            "query": "test document",
            "limit": 5
        })
        
        assert "results" in search_result
        # Mock adapters should return results


@pytest.mark.asyncio
async def test_protocol_fallback_behavior():
    """Test REST API fallback when MCP is unavailable."""
    # This would test the REST API endpoints
    # when MCP WebSocket connection fails
    pass


def test_configuration_loading():
    """Test MCP configuration loading and validation."""
    from app.core.config import Settings
    
    # Test default MCP settings
    settings = Settings(
        secret_key="test",
        jwt_secret_key="test", 
        database_url="postgresql://test",
        redis_url="redis://test",
        qdrant_url="http://test",
        s3_endpoint="http://test",
        s3_access_key="test",
        s3_secret_key="test"
    )
    
    assert settings.mcp_protocol_version == "1.0"
    assert settings.mcp_max_connections == 100
    assert settings.mcp_enable_websocket is True