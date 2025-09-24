"""
MCP Protocol Version Negotiation

This module handles automatic protocol version detection and
negotiation between the server and MCP clients.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.mcp.core.domain import ProtocolNegotiator
from app.mcp.adapters.base import ProtocolVersionRegistry

logger = logging.getLogger(__name__)


class MCPProtocolNegotiator(ProtocolNegotiator):
    """
    Implementation of MCP protocol version negotiation.
    
    This class handles the negotiation process between server and client
    to determine the best protocol version to use for communication.
    """

    def __init__(self, registry: ProtocolVersionRegistry):
        """
        Initialize the protocol negotiator.
        
        Args:
            registry: Registry containing available protocol adapters
        """
        self._registry = registry
        self._compatibility_matrix = self._build_default_compatibility_matrix()

    async def negotiate_protocol(
        self, client_capabilities: Dict[str, Any]
    ) -> str:
        """
        Negotiate the best protocol version with a client.
        
        The negotiation process follows this priority:
        1. Exact version match (highest priority)
        2. Compatible newer version that client can handle  
        3. Compatible older version with graceful degradation
        4. Fallback to oldest supported version
        
        Args:
            client_capabilities: Client's declared capabilities including
                supported versions, features, and tool requirements
                
        Returns:
            Negotiated protocol version string
            
        Raises:
            ValueError: If no compatible protocol version can be found
        """
        logger.info("Starting protocol negotiation")
        logger.debug(f"Client capabilities: {client_capabilities}")
        
        # Extract client supported versions
        client_versions = self._extract_client_versions(client_capabilities)
        client_features = self._extract_client_features(client_capabilities)
        
        # Get server supported versions
        server_versions = self._registry.get_supported_versions()
        
        logger.info(f"Client versions: {client_versions}")
        logger.info(f"Server versions: {server_versions}")
        
        # Step 1: Look for exact matches (prefer latest)
        exact_matches = set(client_versions) & set(server_versions)
        if exact_matches:
            # Sort by version and pick the latest
            best_match = self._select_latest_version(list(exact_matches))
            logger.info(f"Found exact version match: {best_match}")
            return best_match
        
        # Step 2: Look for compatible versions
        compatible_version = self._find_compatible_version(
            client_versions, server_versions, client_features
        )
        if compatible_version:
            logger.info(f"Found compatible version: {compatible_version}")
            return compatible_version
        
        # Step 3: Fallback to most basic version if available
        basic_version = self._get_fallback_version(server_versions)
        if basic_version and self._can_client_handle_fallback(
            basic_version, client_capabilities
        ):
            logger.warning(f"Using fallback version: {basic_version}")
            return basic_version
        
        # Step 4: No compatible version found
        raise ValueError(
            f"No compatible MCP protocol version found. "
            f"Client supports: {client_versions}, "
            f"Server supports: {server_versions}"
        )

    def get_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """Get the compatibility matrix for protocol versions."""
        return self._compatibility_matrix.copy()

    def add_compatibility_rule(
        self, 
        server_version: str, 
        client_version: str, 
        compatible: bool
    ) -> None:
        """
        Add or update a compatibility rule.
        
        Args:
            server_version: Server protocol version
            client_version: Client protocol version  
            compatible: Whether versions are compatible
        """
        if server_version not in self._compatibility_matrix:
            self._compatibility_matrix[server_version] = {}
        
        self._compatibility_matrix[server_version][client_version] = compatible
        logger.debug(
            f"Updated compatibility: {server_version} <-> {client_version} = {compatible}"
        )

    def _extract_client_versions(
        self, capabilities: Dict[str, Any]
    ) -> List[str]:
        """Extract supported versions from client capabilities."""
        # Standard MCP capability format
        if "protocolVersion" in capabilities:
            return [capabilities["protocolVersion"]]
        
        if "supportedVersions" in capabilities:
            return capabilities["supportedVersions"]
        
        if "versions" in capabilities:
            return capabilities["versions"]
        
        # Legacy format support
        if "version" in capabilities:
            return [capabilities["version"]]
        
        # Default to v1.0 if no version specified
        logger.warning("No version information in client capabilities, defaulting to v1.0")
        return ["1.0"]

    def _extract_client_features(
        self, capabilities: Dict[str, Any]
    ) -> Set[str]:
        """Extract supported features from client capabilities."""
        features = set()
        
        if "features" in capabilities:
            features.update(capabilities["features"])
        
        if "tools" in capabilities:
            features.update(capabilities["tools"])
        
        if "capabilities" in capabilities:
            if isinstance(capabilities["capabilities"], list):
                features.update(capabilities["capabilities"])
            elif isinstance(capabilities["capabilities"], dict):
                features.update(capabilities["capabilities"].keys())
        
        return features

    def _find_compatible_version(
        self,
        client_versions: List[str],
        server_versions: List[str],
        client_features: Set[str]
    ) -> Optional[str]:
        """Find a compatible version using the compatibility matrix."""
        
        # Check each server version against client versions
        for server_version in sorted(server_versions, reverse=True):  # Latest first
            for client_version in client_versions:
                if self._are_versions_compatible(server_version, client_version):
                    # Additional check: can server provide required features?
                    if self._can_provide_features(server_version, client_features):
                        return server_version
        
        return None

    def _are_versions_compatible(
        self, server_version: str, client_version: str
    ) -> bool:
        """Check if two versions are compatible using the matrix."""
        return self._compatibility_matrix.get(server_version, {}).get(
            client_version, False
        )

    def _can_provide_features(
        self, server_version: str, required_features: Set[str]
    ) -> bool:
        """Check if server version can provide required features."""
        adapter = self._registry.get_adapter(server_version)
        if not adapter:
            return False
        
        supported_tools = set(adapter.get_supported_tools())
        
        # If no specific features required, any version works
        if not required_features:
            return True
        
        # Check if we can provide the required tools/features
        return required_features.issubset(supported_tools)

    def _select_latest_version(self, versions: List[str]) -> str:
        """Select the latest version from a list."""
        # Simple lexicographic sort - could be enhanced with semantic versioning
        return sorted(versions, key=self._version_sort_key, reverse=True)[0]

    def _version_sort_key(self, version: str) -> tuple:
        """Create sort key for version string."""
        try:
            # Split version like "1.2.3" into tuple (1, 2, 3)
            parts = version.split(".")
            return tuple(int(part) for part in parts)
        except ValueError:
            # Fallback to string comparison
            return (0, version)

    def _get_fallback_version(self, server_versions: List[str]) -> Optional[str]:
        """Get the fallback version (typically the oldest/most basic)."""
        if not server_versions:
            return None
        
        # Return oldest version as fallback
        return sorted(server_versions, key=self._version_sort_key)[0]

    def _can_client_handle_fallback(
        self, fallback_version: str, client_capabilities: Dict[str, Any]
    ) -> bool:
        """Check if client can handle the fallback version."""
        # Basic heuristic: assume client can handle older versions
        client_versions = self._extract_client_versions(client_capabilities)
        
        for client_version in client_versions:
            try:
                client_tuple = self._version_sort_key(client_version)
                fallback_tuple = self._version_sort_key(fallback_version)
                
                # If client version >= fallback version, it should work
                if client_tuple >= fallback_tuple:
                    return True
            except:
                # If version parsing fails, be conservative
                continue
        
        return False

    def _build_default_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """Build the default compatibility matrix for MCP versions."""
        # This matrix defines which server versions can work with which client versions
        # Format: server_version -> client_version -> compatible
        
        matrix = {
            "1.0": {
                "1.0": True,
                "0.9": True,  # v1.0 server can handle v0.9 clients
            },
            "1.1": {
                "1.1": True,
                "1.0": True,  # v1.1 server can handle v1.0 clients (backwards compatible)
                "0.9": False, # v1.1 server cannot handle very old clients
            },
            "2.0": {
                "2.0": True,
                "1.1": False,  # Major version break
                "1.0": False,
            }
        }
        
        return matrix

    async def get_protocol_info(self, version: str) -> Dict[str, Any]:
        """
        Get detailed information about a protocol version.
        
        Args:
            version: Protocol version to get info for
            
        Returns:
            Dictionary with protocol version information
        """
        adapter = self._registry.get_adapter(version)
        if not adapter:
            raise ValueError(f"Unknown protocol version: {version}")
        
        return {
            "version": version,
            "supported_tools": adapter.get_supported_tools(),
            "compatible_with": [
                client_v for client_v, compat in 
                self._compatibility_matrix.get(version, {}).items()
                if compat
            ],
            "features": {
                "tool_count": len(adapter.get_supported_tools()),
                "backward_compatible": any(
                    self._compatibility_matrix.get(version, {}).values()
                ),
            }
        }

    def validate_client_request(
        self, 
        version: str, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Validate that a client request is valid for the negotiated version.
        
        Args:
            version: Negotiated protocol version
            tool_name: Tool being called
            parameters: Tool parameters
            
        Returns:
            True if request is valid for the version
        """
        adapter = self._registry.get_adapter(version)
        if not adapter:
            return False
        
        # Check if tool is supported
        if tool_name not in adapter.get_supported_tools():
            return False
        
        # Additional validation could be added here
        # e.g., parameter schema validation per version
        
        return True