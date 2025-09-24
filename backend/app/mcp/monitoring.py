"""
MCP Protocol Monitoring and Metrics

This module provides comprehensive monitoring, metrics collection,
and health checks for the MCP protocol implementation.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from asyncio import Lock

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    """Metrics for a single MCP connection."""
    connection_id: str
    connected_at: datetime
    protocol_version: str
    client_info: Dict[str, Any]
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)
    avg_response_time: float = 0.0
    tool_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class ToolMetrics:
    """Metrics for MCP tool calls."""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class ProtocolMetrics:
    """Overall protocol metrics."""
    protocol_version: str
    total_connections: int = 0
    active_connections: int = 0
    total_messages: int = 0
    total_errors: int = 0
    avg_connection_duration: float = 0.0
    handshake_failures: int = 0
    negotiation_failures: int = 0


class MCPMonitor:
    """
    MCP Protocol Monitor
    
    Collects and manages metrics for MCP protocol operations,
    providing real-time monitoring and health assessment.
    """

    def __init__(self, retention_hours: int = 24):
        """
        Initialize the MCP monitor.
        
        Args:
            retention_hours: How long to keep detailed metrics
        """
        self._retention_hours = retention_hours
        self._lock = Lock()
        
        # Connection tracking
        self._connections: Dict[str, ConnectionMetrics] = {}
        self._connection_history: deque = deque(maxlen=10000)
        
        # Tool metrics
        self._tool_metrics: Dict[str, ToolMetrics] = {}
        
        # Protocol metrics by version
        self._protocol_metrics: Dict[str, ProtocolMetrics] = {}
        
        # Health status
        self._health_status = {
            "status": "healthy",
            "last_check": datetime.utcnow(),
            "issues": []
        }
        
        # Alerts and thresholds
        self._alert_thresholds = {
            "max_connections": 100,
            "max_error_rate": 0.1,  # 10% error rate
            "max_response_time": 30.0,  # 30 seconds
            "connection_timeout": 300.0,  # 5 minutes
        }

    async def track_connection_started(
        self, 
        connection_id: str,
        protocol_version: str,
        client_info: Dict[str, Any]
    ) -> None:
        """Track when a new connection is established."""
        async with self._lock:
            metrics = ConnectionMetrics(
                connection_id=connection_id,
                connected_at=datetime.utcnow(),
                protocol_version=protocol_version,
                client_info=client_info
            )
            
            self._connections[connection_id] = metrics
            
            # Update protocol metrics
            if protocol_version not in self._protocol_metrics:
                self._protocol_metrics[protocol_version] = ProtocolMetrics(protocol_version)
            
            protocol_metrics = self._protocol_metrics[protocol_version]
            protocol_metrics.total_connections += 1
            protocol_metrics.active_connections += 1
            
            logger.info(f"Connection started: {connection_id} (v{protocol_version})")

    async def track_connection_ended(self, connection_id: str) -> None:
        """Track when a connection is closed."""
        async with self._lock:
            if connection_id in self._connections:
                metrics = self._connections.pop(connection_id)
                
                # Calculate connection duration
                duration = (datetime.utcnow() - metrics.connected_at).total_seconds()
                
                # Update protocol metrics
                protocol_metrics = self._protocol_metrics.get(metrics.protocol_version)
                if protocol_metrics:
                    protocol_metrics.active_connections = max(0, protocol_metrics.active_connections - 1)
                    
                    # Update average connection duration
                    total_connections = protocol_metrics.total_connections
                    current_avg = protocol_metrics.avg_connection_duration
                    protocol_metrics.avg_connection_duration = (
                        (current_avg * (total_connections - 1) + duration) / total_connections
                    )
                
                # Store in history for analysis
                self._connection_history.append({
                    "connection_id": connection_id,
                    "protocol_version": metrics.protocol_version,
                    "duration": duration,
                    "message_count": metrics.message_count,
                    "errors": metrics.errors,
                    "ended_at": datetime.utcnow()
                })
                
                logger.info(f"Connection ended: {connection_id} (duration: {duration:.2f}s)")

    async def track_message(
        self, 
        connection_id: str,
        message_type: str,
        size_bytes: int,
        is_outbound: bool = False
    ) -> None:
        """Track a message sent or received."""
        async with self._lock:
            if connection_id in self._connections:
                metrics = self._connections[connection_id]
                metrics.message_count += 1
                metrics.last_activity = datetime.utcnow()
                
                if is_outbound:
                    metrics.bytes_sent += size_bytes
                else:
                    metrics.bytes_received += size_bytes
                
                # Update protocol metrics
                protocol_metrics = self._protocol_metrics.get(metrics.protocol_version)
                if protocol_metrics:
                    protocol_metrics.total_messages += 1

    async def track_tool_call(
        self,
        connection_id: str,
        tool_name: str,
        execution_time: float,
        success: bool,
        error_type: Optional[str] = None
    ) -> None:
        """Track a tool call execution."""
        async with self._lock:
            # Update connection metrics
            if connection_id in self._connections:
                self._connections[connection_id].tool_calls[tool_name] += 1
                if not success:
                    self._connections[connection_id].errors += 1
            
            # Update tool metrics
            if tool_name not in self._tool_metrics:
                self._tool_metrics[tool_name] = ToolMetrics(tool_name)
            
            tool_metrics = self._tool_metrics[tool_name]
            tool_metrics.total_calls += 1
            
            if success:
                tool_metrics.successful_calls += 1
            else:
                tool_metrics.failed_calls += 1
                if error_type:
                    tool_metrics.error_types[error_type] += 1
            
            # Update execution time statistics
            tool_metrics.recent_response_times.append(execution_time)
            tool_metrics.min_execution_time = min(tool_metrics.min_execution_time, execution_time)
            tool_metrics.max_execution_time = max(tool_metrics.max_execution_time, execution_time)
            
            # Recalculate average execution time
            if tool_metrics.recent_response_times:
                tool_metrics.avg_execution_time = sum(tool_metrics.recent_response_times) / len(tool_metrics.recent_response_times)

    async def track_handshake_failure(self, protocol_version: str, reason: str) -> None:
        """Track a failed handshake attempt."""
        async with self._lock:
            if protocol_version not in self._protocol_metrics:
                self._protocol_metrics[protocol_version] = ProtocolMetrics(protocol_version)
            
            self._protocol_metrics[protocol_version].handshake_failures += 1
            logger.warning(f"Handshake failure (v{protocol_version}): {reason}")

    async def track_negotiation_failure(self, client_versions: List[str], reason: str) -> None:
        """Track a failed protocol negotiation."""
        async with self._lock:
            # Track against all supported versions
            for version in self._protocol_metrics:
                self._protocol_metrics[version].negotiation_failures += 1
            
            logger.warning(f"Negotiation failure with client versions {client_versions}: {reason}")

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status of the MCP protocol implementation.
        
        Returns:
            Health status with overall status and detailed metrics
        """
        async with self._lock:
            now = datetime.utcnow()
            issues = []
            
            # Check connection limits
            total_active = sum(
                metrics.active_connections 
                for metrics in self._protocol_metrics.values()
            )
            
            if total_active > self._alert_thresholds["max_connections"]:
                issues.append({
                    "type": "high_connection_count",
                    "severity": "warning",
                    "message": f"High connection count: {total_active}",
                    "threshold": self._alert_thresholds["max_connections"]
                })
            
            # Check error rates
            for tool_name, tool_metrics in self._tool_metrics.items():
                if tool_metrics.total_calls > 0:
                    error_rate = tool_metrics.failed_calls / tool_metrics.total_calls
                    if error_rate > self._alert_thresholds["max_error_rate"]:
                        issues.append({
                            "type": "high_error_rate",
                            "severity": "critical",
                            "message": f"High error rate for {tool_name}: {error_rate:.2%}",
                            "threshold": self._alert_thresholds["max_error_rate"]
                        })
            
            # Check response times
            for tool_name, tool_metrics in self._tool_metrics.items():
                if tool_metrics.avg_execution_time > self._alert_thresholds["max_response_time"]:
                    issues.append({
                        "type": "slow_response",
                        "severity": "warning",
                        "message": f"Slow response time for {tool_name}: {tool_metrics.avg_execution_time:.2f}s",
                        "threshold": self._alert_thresholds["max_response_time"]
                    })
            
            # Check for stale connections
            stale_connections = []
            cutoff_time = now - timedelta(seconds=self._alert_thresholds["connection_timeout"])
            
            for conn_id, metrics in self._connections.items():
                if metrics.last_activity < cutoff_time:
                    stale_connections.append(conn_id)
            
            if stale_connections:
                issues.append({
                    "type": "stale_connections",
                    "severity": "info",
                    "message": f"Stale connections detected: {len(stale_connections)}",
                    "connections": stale_connections
                })
            
            # Determine overall status
            if any(issue["severity"] == "critical" for issue in issues):
                status = "unhealthy"
            elif any(issue["severity"] == "warning" for issue in issues):
                status = "degraded"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "timestamp": now.isoformat(),
                "active_connections": total_active,
                "total_issues": len(issues),
                "issues": issues,
                "uptime_seconds": (now - min(
                    (metrics.connected_at for metrics in self._connections.values()),
                    default=now
                )).total_seconds()
            }

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        async with self._lock:
            # Connection metrics
            active_connections = len(self._connections)
            total_connections = sum(
                metrics.total_connections 
                for metrics in self._protocol_metrics.values()
            )
            
            # Tool metrics summary
            tool_summary = {}
            for tool_name, metrics in self._tool_metrics.items():
                success_rate = (
                    metrics.successful_calls / max(1, metrics.total_calls)
                )
                tool_summary[tool_name] = {
                    "total_calls": metrics.total_calls,
                    "success_rate": success_rate,
                    "avg_execution_time": metrics.avg_execution_time,
                    "error_types": dict(metrics.error_types)
                }
            
            # Protocol metrics summary
            protocol_summary = {}
            for version, metrics in self._protocol_metrics.items():
                protocol_summary[version] = {
                    "total_connections": metrics.total_connections,
                    "active_connections": metrics.active_connections,
                    "total_messages": metrics.total_messages,
                    "handshake_failures": metrics.handshake_failures,
                    "negotiation_failures": metrics.negotiation_failures,
                    "avg_connection_duration": metrics.avg_connection_duration
                }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "connections": {
                    "active": active_connections,
                    "total_since_start": total_connections,
                    "by_protocol": {
                        version: metrics.active_connections
                        for version, metrics in self._protocol_metrics.items()
                    }
                },
                "tools": tool_summary,
                "protocols": protocol_summary,
                "performance": {
                    "avg_message_processing_time": self._calculate_avg_message_time(),
                    "error_rate": self._calculate_overall_error_rate(),
                    "throughput_per_second": self._calculate_throughput()
                }
            }

    def _calculate_avg_message_time(self) -> float:
        """Calculate average message processing time across all tools."""
        if not self._tool_metrics:
            return 0.0
        
        total_time = sum(metrics.avg_execution_time for metrics in self._tool_metrics.values())
        return total_time / len(self._tool_metrics)

    def _calculate_overall_error_rate(self) -> float:
        """Calculate overall error rate across all tools."""
        total_calls = sum(metrics.total_calls for metrics in self._tool_metrics.values())
        total_failures = sum(metrics.failed_calls for metrics in self._tool_metrics.values())
        
        if total_calls == 0:
            return 0.0
        
        return total_failures / total_calls

    def _calculate_throughput(self) -> float:
        """Calculate messages per second throughput."""
        if not self._protocol_metrics:
            return 0.0
        
        total_messages = sum(metrics.total_messages for metrics in self._protocol_metrics.values())
        
        # Calculate time since first connection
        if self._connections:
            earliest_connection = min(
                metrics.connected_at for metrics in self._connections.values()
            )
            elapsed_seconds = (datetime.utcnow() - earliest_connection).total_seconds()
            
            if elapsed_seconds > 0:
                return total_messages / elapsed_seconds
        
        return 0.0

    async def cleanup_old_data(self) -> None:
        """Clean up old monitoring data based on retention policy."""
        async with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=self._retention_hours)
            
            # Clean up connection history
            self._connection_history = deque(
                (entry for entry in self._connection_history 
                 if entry["ended_at"] > cutoff_time),
                maxlen=self._connection_history.maxlen
            )
            
            logger.info(f"Cleaned up monitoring data older than {self._retention_hours} hours")

    def set_alert_threshold(self, threshold_name: str, value: float) -> None:
        """Set an alert threshold value."""
        if threshold_name in self._alert_thresholds:
            self._alert_thresholds[threshold_name] = value
            logger.info(f"Updated alert threshold {threshold_name} to {value}")
        else:
            logger.warning(f"Unknown alert threshold: {threshold_name}")

    async def get_connection_details(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed metrics for a specific connection."""
        async with self._lock:
            if connection_id not in self._connections:
                return None
            
            metrics = self._connections[connection_id]
            duration = (datetime.utcnow() - metrics.connected_at).total_seconds()
            
            return {
                "connection_id": connection_id,
                "protocol_version": metrics.protocol_version,
                "client_info": metrics.client_info,
                "connected_at": metrics.connected_at.isoformat(),
                "duration_seconds": duration,
                "message_count": metrics.message_count,
                "bytes_sent": metrics.bytes_sent,
                "bytes_received": metrics.bytes_received,
                "errors": metrics.errors,
                "last_activity": metrics.last_activity.isoformat(),
                "tool_calls": dict(metrics.tool_calls),
                "avg_response_time": metrics.avg_response_time
            }