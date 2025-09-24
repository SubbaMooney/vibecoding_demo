"""
Qdrant vector database client wrapper.

This module provides a high-level interface for interacting with Qdrant,
including collection management, vector operations, and health checks.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.http.models import (
        Distance, VectorParams, CreateCollection, PointStruct,
        Filter, FieldCondition, SearchRequest, UpdateResult
    )
except ImportError:
    raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

from backend.app.vector.config import vector_config

logger = logging.getLogger(__name__)

class QdrantVectorClient:
    """
    High-level Qdrant client for vector operations.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize Qdrant client with configuration."""
        self._config = config or {}
        self._client: Optional[QdrantClient] = None
        self._collections: Dict[str, Dict] = {}
        
    async def connect(self) -> bool:
        """
        Establish connection to Qdrant server.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create client with configuration
            self._client = QdrantClient(
                host=vector_config.qdrant_host,
                port=vector_config.qdrant_port,
                grpc_port=vector_config.qdrant_grpc_port,
                https=vector_config.qdrant_https,
                api_key=vector_config.qdrant_api_key,
                timeout=vector_config.connection_timeout
            )
            
            # Test connection
            health = await self.health_check()
            if health["status"] == "healthy":
                logger.info(f"Connected to Qdrant at {vector_config.qdrant_host}:{vector_config.qdrant_port}")
                return True
            else:
                logger.error("Qdrant health check failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close Qdrant connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Qdrant server health.
        
        Returns:
            Dict with health status and metrics
        """
        if not self._client:
            return {"status": "disconnected", "error": "No client connection"}
        
        try:
            # Get cluster info
            cluster_info = self._client.get_cluster_info()
            
            # Get collections info
            collections = self._client.get_collections()
            
            return {
                "status": "healthy",
                "cluster_info": cluster_info,
                "collections_count": len(collections.collections),
                "collections": [c.name for c in collections.collections]
            }
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def ensure_collection(self, collection_name: str, vector_size: int, 
                              distance: str = "Cosine") -> bool:
        """
        Ensure collection exists, create if not.
        
        Args:
            collection_name: Name of the collection
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Dot, Euclid)
            
        Returns:
            bool: True if collection ready
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            # Check if collection exists
            collections = self._client.get_collections()
            existing_collections = [c.name for c in collections.collections]
            
            if collection_name in existing_collections:
                # Verify collection configuration
                collection_info = self._client.get_collection(collection_name)
                stored_size = collection_info.config.params.vectors.size
                
                if stored_size != vector_size:
                    logger.warning(
                        f"Collection {collection_name} exists but has different vector size "
                        f"({stored_size} vs {vector_size})"
                    )
                    return False
                
                logger.info(f"Collection {collection_name} already exists")
                return True
            
            # Create collection
            distance_map = {
                "Cosine": Distance.COSINE,
                "Dot": Distance.DOT,
                "Euclid": Distance.EUCLID
            }
            
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance, Distance.COSINE)
                )
            )
            
            logger.info(f"Created collection {collection_name} with size {vector_size}")
            
            # Store collection info
            self._collections[collection_name] = {
                "vector_size": vector_size,
                "distance": distance
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure collection {collection_name}: {str(e)}")
            return False
    
    async def upsert_points(self, collection_name: str, points: List[Dict[str, Any]]) -> bool:
        """
        Insert or update points in collection.
        
        Args:
            collection_name: Target collection
            points: List of points with id, vector, and payload
            
        Returns:
            bool: True if operation successful
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            # Convert to PointStruct objects
            point_structs = []
            for point in points:
                point_struct = PointStruct(
                    id=point["id"],
                    vector=point["vector"],
                    payload=point.get("payload", {})
                )
                point_structs.append(point_struct)
            
            # Upsert points
            result = self._client.upsert(
                collection_name=collection_name,
                points=point_structs,
                wait=True
            )
            
            logger.info(f"Upserted {len(points)} points to {collection_name}")
            return result.status == "completed"
            
        except Exception as e:
            logger.error(f"Failed to upsert points to {collection_name}: {str(e)}")
            return False
    
    async def search(self, collection_name: str, query_vector: List[float],
                    limit: int = 10, score_threshold: Optional[float] = None,
                    filter_conditions: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            collection_name: Target collection
            query_vector: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Payload filtering conditions
            
        Returns:
            List of search results with id, score, and payload
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            # Prepare filter
            search_filter = None
            if filter_conditions:
                conditions = []
                for field, value in filter_conditions.items():
                    if isinstance(value, list):
                        # Multiple values - use "must" condition
                        for v in value:
                            conditions.append(
                                FieldCondition(key=field, match=models.MatchValue(value=v))
                            )
                    else:
                        conditions.append(
                            FieldCondition(key=field, match=models.MatchValue(value=value))
                        )
                
                if conditions:
                    search_filter = Filter(must=conditions)
            
            # Perform search
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload or {}
                })
            
            logger.debug(f"Search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {str(e)}")
            return []
    
    async def delete_points(self, collection_name: str, point_ids: List[Union[str, int]]) -> bool:
        """
        Delete points from collection.
        
        Args:
            collection_name: Target collection
            point_ids: List of point IDs to delete
            
        Returns:
            bool: True if operation successful
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            result = self._client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=point_ids),
                wait=True
            )
            
            logger.info(f"Deleted {len(point_ids)} points from {collection_name}")
            return result.status == "completed"
            
        except Exception as e:
            logger.error(f"Failed to delete points from {collection_name}: {str(e)}")
            return False
    
    async def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection information and statistics.
        
        Args:
            collection_name: Target collection
            
        Returns:
            Collection information or None if not found
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            collection_info = self._client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value
                },
                "status": collection_info.status
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection info for {collection_name}: {str(e)}")
            return None
    
    async def scroll_points(self, collection_name: str, limit: int = 100,
                          offset: Optional[str] = None,
                          with_payload: bool = True) -> Dict[str, Any]:
        """
        Scroll through points in collection.
        
        Args:
            collection_name: Target collection
            limit: Number of points to return
            offset: Pagination offset
            with_payload: Include payload in results
            
        Returns:
            Dict with points and next_page_offset
        """
        if not self._client:
            raise RuntimeError("Client not connected")
        
        try:
            result = self._client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_payload=with_payload,
                with_vectors=False
            )
            
            points = []
            for point in result[0]:  # result is (points, next_page_offset)
                points.append({
                    "id": point.id,
                    "payload": point.payload if with_payload else {}
                })
            
            return {
                "points": points,
                "next_page_offset": result[1]
            }
            
        except Exception as e:
            logger.error(f"Failed to scroll points in {collection_name}: {str(e)}")
            return {"points": [], "next_page_offset": None}

# Global client instance
qdrant_client = QdrantVectorClient()