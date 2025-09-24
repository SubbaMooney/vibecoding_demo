"""
MCP Protocol Server Implementation

This module implements the MCP server that integrates with FastAPI
and handles WebSocket connections for real-time MCP protocol communication.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.websockets import WebSocketState

from app.mcp.core.domain import ProtocolAdapter
from app.mcp.adapters.base import ProtocolVersionRegistry
from app.mcp.negotiation import MCPProtocolNegotiator
from app.mcp.monitoring import MCPMonitor

logger = logging.getLogger(__name__)


class MCPConnection:
    """
    Represents an active MCP client connection.
    
    Each connection maintains its own protocol state, negotiated version,
    and message handling context.
    """

    def __init__(
        self, 
        connection_id: str, 
        websocket: WebSocket,
        negotiated_version: Optional[str] = None
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.negotiated_version = negotiated_version
        self.connected_at = datetime.utcnow()
        self.message_count = 0
        self.client_info: Dict[str, Any] = {}
        self.is_authenticated = False

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to the connected client."""
        if self.websocket.client_state != WebSocketState.CONNECTED:
            raise RuntimeError("WebSocket is not connected")
        
        await self.websocket.send_text(json.dumps(message))
        logger.debug(f"Sent message to {self.connection_id}: {message.get('type', 'unknown')}")

    async def receive_message(self) -> Dict[str, Any]:
        """Receive a message from the connected client."""
        if self.websocket.client_state != WebSocketState.CONNECTED:
            raise RuntimeError("WebSocket is not connected")
        
        raw_message = await self.websocket.receive_text()
        self.message_count += 1
        
        try:
            message = json.loads(raw_message)
            logger.debug(f"Received message from {self.connection_id}: {message.get('type', 'unknown')}")
            return message
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {self.connection_id}: {str(e)}")
            raise ValueError(f"Invalid JSON message: {str(e)}")


class MCPServer:
    """
    Main MCP Protocol Server.
    
    This server handles WebSocket connections, protocol negotiation,
    message routing, and maintains active connections.
    """

    def __init__(
        self,
        registry: ProtocolVersionRegistry,
        negotiator: MCPProtocolNegotiator,
        monitor: Optional[MCPMonitor] = None,
        max_connections: int = 100
    ):
        """
        Initialize the MCP server.
        
        Args:
            registry: Protocol version registry with adapters
            negotiator: Protocol version negotiator
            max_connections: Maximum concurrent connections allowed
        """
        self._registry = registry
        self._negotiator = negotiator
        self._monitor = monitor or MCPMonitor()
        self._max_connections = max_connections
        
        # Active connections
        self._connections: Dict[str, MCPConnection] = {}
        self._connections_lock = asyncio.Lock()
        
        # Server statistics
        self._total_connections = 0
        self._total_messages = 0
        self._start_time = datetime.utcnow()

    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Handle a new WebSocket connection for MCP protocol.
        
        This method manages the entire connection lifecycle:
        1. Accept the connection
        2. Perform protocol negotiation
        3. Handle messages until disconnection
        4. Clean up connection state
        """
        connection_id = str(uuid4())
        logger.info(f"New MCP connection: {connection_id}")
        
        # Check connection limit
        if len(self._connections) >= self._max_connections:
            logger.warning(f"Connection limit reached, rejecting {connection_id}")
            await websocket.close(code=1013, reason="Server overloaded")
            return
        
        await websocket.accept()
        connection = MCPConnection(connection_id, websocket)
        
        try:
            async with self._connections_lock:
                self._connections[connection_id] = connection
                self._total_connections += 1
            
            # Perform protocol negotiation
            await self._perform_handshake(connection)
            
            # Track successful connection
            await self._monitor.track_connection_started(
                connection.connection_id,
                connection.negotiated_version,
                connection.client_info
            )
            
            # Handle messages until disconnection
            await self._message_loop(connection)
            
        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error handling connection {connection_id}: {str(e)}")
            try:
                await connection.send_message({
                    "type": "error",
                    "error": {
                        "code": "SERVER_ERROR",
                        "message": "Internal server error",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })
            except:
                pass
        finally:
            # Track connection ended
            await self._monitor.track_connection_ended(connection_id)
            
            # Clean up connection
            async with self._connections_lock:
                self._connections.pop(connection_id, None)
            
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
            except:
                pass
            
            logger.info(f"Connection cleanup complete: {connection_id}")

    async def _perform_handshake(self, connection: MCPConnection) -> None:
        """
        Perform MCP protocol handshake and version negotiation.
        
        The handshake process:
        1. Wait for client hello with capabilities
        2. Negotiate protocol version
        3. Send server hello with selected version
        4. Confirm protocol is ready
        """
        logger.debug(f"Starting handshake for {connection.connection_id}")
        
        # Wait for client hello
        message = await connection.receive_message()
        if message.get("type") != "hello":
            raise ValueError("Expected 'hello' message from client")
        
        client_capabilities = message.get("capabilities", {})
        connection.client_info = message.get("client_info", {})
        
        logger.info(f"Client hello from {connection.connection_id}: {connection.client_info}")
        
        # Negotiate protocol version
        try:
            negotiated_version = await self._negotiator.negotiate_protocol(
                client_capabilities
            )
            connection.negotiated_version = negotiated_version
            
            logger.info(f"Negotiated protocol v{negotiated_version} for {connection.connection_id}")
            
        except ValueError as e:
            await self._monitor.track_negotiation_failure(
                self._negotiator._extract_client_versions(client_capabilities),
                str(e)
            )
            await connection.send_message({
                "type": "error",
                "error": {
                    "code": "PROTOCOL_NEGOTIATION_FAILED",
                    "message": str(e),
                    "supported_versions": self._registry.get_supported_versions()
                }
            })
            raise
        
        # Get protocol adapter
        adapter = self._registry.get_adapter(negotiated_version)
        if not adapter:
            raise RuntimeError(f"No adapter found for version {negotiated_version}")
        
        # Send server hello
        await connection.send_message({
            "type": "hello",
            "protocol_version": negotiated_version,
            "server_info": {
                "name": "MCP RAG Server",
                "version": "1.0.0",
                "description": "RAG server with MCP protocol support"
            },
            "capabilities": {
                "tools": adapter.get_supported_tools(),
                "features": ["async_tools", "error_handling", "progress_tracking"],
                "max_message_size": 10 * 1024 * 1024,  # 10MB
            }
        })
        
        # Wait for confirmation
        confirm_message = await connection.receive_message()
        if confirm_message.get("type") != "ready":
            logger.warning(f"Unexpected message after handshake: {confirm_message.get('type')}")
        
        logger.info(f"Handshake complete for {connection.connection_id}")

    async def _message_loop(self, connection: MCPConnection) -> None:
        """
        Main message handling loop for an established connection.
        
        Continuously processes messages from the client until
        the connection is closed or an error occurs.
        """
        adapter = self._registry.get_adapter(connection.negotiated_version)
        if not adapter:
            raise RuntimeError("No adapter available for connection")
        
        logger.debug(f"Starting message loop for {connection.connection_id}")
        
        while True:
            try:
                # Receive message from client
                message = await connection.receive_message()
                self._total_messages += 1
                
                # Track message
                message_size = len(str(message))
                await self._monitor.track_message(
                    connection.connection_id,
                    message.get("type", "unknown"),
                    message_size,
                    is_outbound=False
                )
                
                # Route message based on type
                response = await self._handle_message(connection, adapter, message)
                
                # Send response if generated
                if response:
                    await connection.send_message(response)
                    
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.error(f"Error processing message from {connection.connection_id}: {str(e)}")
                
                # Send error response
                try:
                    await connection.send_message({
                        "type": "error",
                        "request_id": message.get("id"),
                        "error": {
                            "code": "MESSAGE_PROCESSING_ERROR",
                            "message": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                except:
                    # If we can't send error, connection is probably broken
                    break

    async def _handle_message(
        self,
        connection: MCPConnection,
        adapter: ProtocolAdapter,
        message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a single message from the client.
        
        Routes messages to appropriate handlers based on message type
        and generates appropriate responses.
        """
        message_type = message.get("type")
        message_id = message.get("id")
        
        logger.debug(f"Handling {message_type} message from {connection.connection_id}")
        
        try:
            if message_type == "tool_call":
                return await self._handle_tool_call(adapter, message)
            elif message_type == "ping":
                return {"type": "pong", "id": message_id}
            elif message_type == "get_capabilities":
                return await self._handle_get_capabilities(adapter, message)
            elif message_type == "get_protocol_info":
                return await self._handle_get_protocol_info(connection, message)
            else:
                return {
                    "type": "error",
                    "id": message_id,
                    "error": {
                        "code": "UNKNOWN_MESSAGE_TYPE",
                        "message": f"Unknown message type: {message_type}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in message handler: {str(e)}")
            return {
                "type": "error",
                "id": message_id,
                "error": {
                    "code": "HANDLER_ERROR",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    async def _handle_tool_call(
        self,
        adapter: ProtocolAdapter,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a tool call message."""
        tool_name = message.get("tool")
        parameters = message.get("parameters", {})
        message_id = message.get("id")
        
        if not tool_name:
            raise ValueError("Missing 'tool' field in tool_call message")
        
        # Validate tool is supported
        if tool_name not in adapter.get_supported_tools():
            raise ValueError(f"Unsupported tool: {tool_name}")
        
        # Execute tool call
        start_time = datetime.utcnow()
        try:
            result = await adapter.handle_tool_call(tool_name, parameters)
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            # Track successful tool call
            await self._monitor.track_tool_call(
                # Need connection_id, will extract from context
                "unknown",  # TODO: Pass connection_id to this method
                tool_name,
                execution_time,
                success=True
            )
            
            return {
                "type": "tool_response",
                "id": message_id,
                "tool": tool_name,
                "result": result,
                "execution_time_ms": execution_time * 1000,
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            logger.error(f"Tool call error for {tool_name}: {str(e)}")
            
            # Track failed tool call
            await self._monitor.track_tool_call(
                "unknown",  # TODO: Pass connection_id to this method
                tool_name,
                execution_time,
                success=False,
                error_type=type(e).__name__
            )
            
            return {
                "type": "tool_error", 
                "id": message_id,
                "tool": tool_name,
                "error": {
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "timestamp": end_time.isoformat()
                }
            }

    async def _handle_get_capabilities(
        self,
        adapter: ProtocolAdapter,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a get_capabilities message."""
        return {
            "type": "capabilities",
            "id": message.get("id"),
            "capabilities": {
                "protocol_version": adapter.get_supported_version(),
                "tools": adapter.get_supported_tools(),
                "features": ["async_tools", "error_handling", "progress_tracking"],
                "limits": {
                    "max_message_size": 10 * 1024 * 1024,
                    "max_tool_calls_per_minute": 100,
                    "max_concurrent_calls": 10
                }
            }
        }

    async def _handle_get_protocol_info(
        self,
        connection: MCPConnection,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a get_protocol_info message."""
        if not connection.negotiated_version:
            raise ValueError("No protocol version negotiated")
        
        protocol_info = await self._negotiator.get_protocol_info(
            connection.negotiated_version
        )
        
        return {
            "type": "protocol_info",
            "id": message.get("id"),
            "info": protocol_info
        }

    async def get_server_stats(self) -> Dict[str, Any]:
        """Get current server statistics."""
        uptime = datetime.utcnow() - self._start_time
        
        async with self._connections_lock:
            active_connections = len(self._connections)
            connections_by_version = {}
            
            for conn in self._connections.values():
                version = conn.negotiated_version or "unknown"
                connections_by_version[version] = connections_by_version.get(version, 0) + 1
        
        return {
            "server_info": {
                "name": "MCP RAG Server",
                "version": "1.0.0",
                "uptime_seconds": uptime.total_seconds(),
                "started_at": self._start_time.isoformat()
            },
            "connections": {
                "active": active_connections,
                "total_since_start": self._total_connections,
                "max_allowed": self._max_connections,
                "by_version": connections_by_version
            },
            "messages": {
                "total_processed": self._total_messages,
                "average_per_connection": (
                    self._total_messages / max(1, self._total_connections)
                )
            },
            "protocols": {
                "supported_versions": self._registry.get_supported_versions(),
                "compatibility_matrix": self._negotiator.get_compatibility_matrix()
            }
        }

    async def broadcast_message(
        self, 
        message: Dict[str, Any], 
        version_filter: Optional[str] = None
    ) -> int:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Message to broadcast
            version_filter: Optional protocol version filter
            
        Returns:
            Number of clients that received the message
        """
        async with self._connections_lock:
            connections = list(self._connections.values())
        
        sent_count = 0
        
        for connection in connections:
            try:
                # Apply version filter if specified
                if version_filter and connection.negotiated_version != version_filter:
                    continue
                
                await connection.send_message(message)
                sent_count += 1
                
            except Exception as e:
                logger.error(f"Error broadcasting to {connection.connection_id}: {str(e)}")
        
        logger.info(f"Broadcast message to {sent_count} clients")
        return sent_count