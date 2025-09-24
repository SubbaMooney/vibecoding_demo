"""
Main FastAPI Application for MCP RAG Server

This module creates the FastAPI application instance and integrates
all components including MCP protocol server, REST API, and service dependencies.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.mcp.server import MCPServer
from app.mcp.adapters.base import ProtocolVersionRegistry
from app.mcp.adapters.mcp_v1 import MCPv1Adapter
from app.mcp.negotiation import MCPProtocolNegotiator
from app.mcp.core.service import RAGDomainService, DocumentProcessingService
from app.api.routes import api_router, set_services
from app.documents.api import router as documents_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global application state
app_state = {
    "mcp_server": None,
    "rag_service": None, 
    "document_service": None,
    "registry": None,
    "negotiator": None
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    
    Handles startup and shutdown of services, connections, and resources.
    """
    logger.info("Starting MCP RAG Server...")
    
    try:
        # Initialize configuration
        settings = get_settings()
        logger.info(f"Loaded configuration for environment: {settings.environment}")
        
        # Initialize protocol version registry
        registry = ProtocolVersionRegistry()
        
        # TODO: Initialize concrete adapter implementations
        # For now, we'll create placeholder services that will be implemented
        # in the next phases of development
        
        # Create mock adapters for development
        from app.mcp.adapters.mock_adapters import (
            MockVectorSearchAdapter,
            MockDocumentStorageAdapter,
            MockSummarizationAdapter,
            MockTextExtractionAdapter,
            MockVectorIndexAdapter
        )
        
        # Initialize services with mock adapters
        rag_service = RAGDomainService(
            vector_search_adapter=MockVectorSearchAdapter(),
            document_storage_adapter=MockDocumentStorageAdapter(),
            summarization_adapter=MockSummarizationAdapter()
        )
        
        document_service = DocumentProcessingService(
            document_storage_adapter=MockDocumentStorageAdapter(),
            text_extraction_adapter=MockTextExtractionAdapter(),
            vector_index_adapter=MockVectorIndexAdapter()
        )
        
        # Register MCP v1.0 adapter
        mcp_v1_adapter = MCPv1Adapter(rag_service, document_service)
        registry.register_adapter(mcp_v1_adapter)
        
        # Set up compatibility matrix
        registry.set_compatibility("1.0", "1.0", True)
        registry.set_compatibility("1.0", "0.9", True)
        
        # Initialize protocol negotiator
        negotiator = MCPProtocolNegotiator(registry)
        
        # Initialize MCP monitor
        from app.mcp.monitoring import MCPMonitor
        monitor = MCPMonitor(retention_hours=24)
        
        # Initialize MCP server
        mcp_server = MCPServer(
            registry=registry,
            negotiator=negotiator,
            monitor=monitor,
            max_connections=settings.mcp_max_connections if hasattr(settings, 'mcp_max_connections') else 100
        )
        
        # Store in app state
        app_state["mcp_server"] = mcp_server
        app_state["rag_service"] = rag_service
        app_state["document_service"] = document_service
        app_state["registry"] = registry
        app_state["negotiator"] = negotiator
        
        # Initialize REST API services
        set_services(rag_service, document_service)
        
        logger.info("MCP RAG Server startup complete")
        
        yield  # Server is running
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down MCP RAG Server...")
        
        # TODO: Add cleanup for database connections, background tasks, etc.
        
        logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="MCP RAG Server",
    description="A comprehensive semantic search and document management system with Model Context Protocol support",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    """Root endpoint with basic server information."""
    return {
        "name": "MCP RAG Server",
        "version": "1.0.0",
        "description": "Semantic search and document management with MCP protocol support",
        "endpoints": {
            "docs": "/docs",
            "api": "/api/v1",
            "mcp_websocket": "/mcp/ws",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Checks the status of all major system components.
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": "2024-09-24T22:00:00Z",
            "version": "1.0.0",
            "components": {}
        }
        
        # Check MCP server
        if app_state["mcp_server"]:
            mcp_stats = await app_state["mcp_server"].get_server_stats()
            health_status["components"]["mcp_server"] = {
                "status": "healthy",
                "active_connections": mcp_stats["connections"]["active"],
                "total_connections": mcp_stats["connections"]["total_since_start"],
                "supported_versions": mcp_stats["protocols"]["supported_versions"]
            }
        else:
            health_status["components"]["mcp_server"] = {"status": "not_initialized"}
        
        # Check services
        health_status["components"]["rag_service"] = {
            "status": "healthy" if app_state["rag_service"] else "not_initialized"
        }
        
        health_status["components"]["document_service"] = {
            "status": "healthy" if app_state["document_service"] else "not_initialized"
        }
        
        # TODO: Add checks for database, Redis, Qdrant, etc.
        
        # Determine overall status
        component_statuses = [
            comp["status"] for comp in health_status["components"].values()
        ]
        
        if all(status == "healthy" for status in component_statuses):
            health_status["status"] = "healthy"
        elif any(status == "healthy" for status in component_statuses):
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-09-24T22:00:00Z"
            }
        )


@app.websocket("/mcp/ws")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for MCP protocol connections.
    
    This endpoint handles the MCP protocol WebSocket connections,
    performing handshake, protocol negotiation, and message routing.
    """
    mcp_server = app_state["mcp_server"]
    
    if not mcp_server:
        logger.error("MCP server not initialized")
        await websocket.close(code=1013, reason="Server not ready")
        return
    
    # Handle the connection through the MCP server
    await mcp_server.handle_connection(websocket)


@app.get("/mcp/status")
async def mcp_status():
    """
    Get current MCP server status and statistics.
    
    Provides detailed information about active connections,
    protocol versions, and server performance.
    """
    mcp_server = app_state["mcp_server"]
    
    if not mcp_server:
        return JSONResponse(
            status_code=503,
            content={"error": "MCP server not initialized"}
        )
    
    try:
        stats = await mcp_server.get_server_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting MCP status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/mcp/broadcast")
async def broadcast_message(
    message: dict,
    version_filter: str = None
):
    """
    Broadcast a message to all connected MCP clients.
    
    This is useful for server-initiated notifications or updates.
    """
    mcp_server = app_state["mcp_server"]
    
    if not mcp_server:
        return JSONResponse(
            status_code=503,
            content={"error": "MCP server not initialized"}
        )
    
    try:
        sent_count = await mcp_server.broadcast_message(message, version_filter)
        return {
            "success": True,
            "clients_notified": sent_count,
            "message_type": message.get("type", "unknown")
        }
    except Exception as e:
        logger.error(f"Error broadcasting message: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "timestamp": "2024-09-24T22:00:00Z"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )