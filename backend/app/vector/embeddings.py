"""
Embedding service using Sentence-transformers.

This module provides text embedding functionality with support for
multiple models, batch processing, and caching.
"""

import asyncio
import hashlib
import logging
import pickle
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading

try:
    from sentence_transformers import SentenceTransformer
    import torch
except ImportError:
    raise ImportError(
        "sentence-transformers is required. Install with: "
        "pip install sentence-transformers torch"
    )

from backend.app.vector.config import vector_config, EMBEDDING_MODELS
from backend.app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating text embeddings using Sentence-transformers.
    """
    
    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            model_name: Sentence-transformer model name
            device: Device to run model on (cpu, cuda)
        """
        self.model_name = model_name or vector_config.embedding_model_name
        self.device = device or vector_config.embedding_device
        self.model: Optional[SentenceTransformer] = None
        self.model_dimension: Optional[int] = None
        
        # Thread pool for CPU-bound operations
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._model_lock = threading.Lock()
        
        # Cache settings
        self._cache_enabled = True
        self._cache_ttl = 3600  # 1 hour
        
    async def initialize(self) -> bool:
        """
        Initialize the embedding model.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                self._executor,
                self._load_model
            )
            
            # Get model dimension
            self.model_dimension = self.model.get_sentence_embedding_dimension()
            
            # Verify device
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but not available, falling back to CPU")
                self.device = "cpu"
            
            logger.info(
                f"Embedding model loaded: {self.model_name} "
                f"(dim={self.model_dimension}, device={self.device})"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {str(e)}")
            return False
    
    def _load_model(self) -> SentenceTransformer:
        """Load model in thread executor."""
        with self._model_lock:
            model = SentenceTransformer(self.model_name, device=self.device)
            return model
    
    async def encode_text(self, text: str, normalize: bool = True) -> Optional[List[float]]:
        """
        Encode single text into embedding vector.
        
        Args:
            text: Input text
            normalize: Whether to normalize the vector
            
        Returns:
            Embedding vector or None if failed
        """
        if not text or not text.strip():
            return None
        
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        try:
            # Check cache first
            if self._cache_enabled:
                cached = await self._get_cached_embedding(text)
                if cached is not None:
                    return cached
            
            # Generate embedding
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self._executor,
                self._encode_single,
                text,
                normalize
            )
            
            # Cache result
            if self._cache_enabled and embedding is not None:
                await self._cache_embedding(text, embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to encode text: {str(e)}")
            return None
    
    def _encode_single(self, text: str, normalize: bool) -> List[float]:
        """Encode text in thread executor."""
        with self._model_lock:
            # Truncate if too long
            if len(text) > vector_config.max_sequence_length:
                text = text[:vector_config.max_sequence_length]
            
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=normalize
            )
            
            return embedding.tolist()
    
    async def encode_batch(self, texts: List[str], normalize: bool = True,
                          batch_size: Optional[int] = None) -> List[Optional[List[float]]]:
        """
        Encode multiple texts into embedding vectors.
        
        Args:
            texts: List of input texts
            normalize: Whether to normalize vectors
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors (None for failed encodings)
        """
        if not texts:
            return []
        
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        batch_size = batch_size or vector_config.embedding_batch_size
        results: List[Optional[List[float]]] = []
        
        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Filter out empty texts but keep track of indices
                valid_texts = []
                valid_indices = []
                
                for j, text in enumerate(batch_texts):
                    if text and text.strip():
                        valid_texts.append(text)
                        valid_indices.append(j)
                
                # Generate embeddings for valid texts
                if valid_texts:
                    loop = asyncio.get_event_loop()
                    batch_embeddings = await loop.run_in_executor(
                        self._executor,
                        self._encode_batch,
                        valid_texts,
                        normalize
                    )
                    
                    # Map results back to original indices
                    batch_results = [None] * len(batch_texts)
                    for k, embedding in enumerate(batch_embeddings):
                        original_idx = valid_indices[k]
                        batch_results[original_idx] = embedding
                    
                    results.extend(batch_results)
                else:
                    # All texts in batch were empty
                    results.extend([None] * len(batch_texts))
                
                # Small delay between batches to prevent overloading
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.01)
            
            logger.info(f"Encoded {len(texts)} texts in batches of {batch_size}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to encode batch: {str(e)}")
            return [None] * len(texts)
    
    def _encode_batch(self, texts: List[str], normalize: bool) -> List[List[float]]:
        """Encode batch in thread executor."""
        with self._model_lock:
            # Truncate long texts
            truncated_texts = []
            for text in texts:
                if len(text) > vector_config.max_sequence_length:
                    text = text[:vector_config.max_sequence_length]
                truncated_texts.append(text)
            
            embeddings = self.model.encode(
                truncated_texts,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                batch_size=len(texts)
            )
            
            return embeddings.tolist()
    
    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Model information dictionary
        """
        return {
            "model_name": self.model_name,
            "model_dimension": self.model_dimension,
            "device": self.device,
            "max_sequence_length": vector_config.max_sequence_length,
            "batch_size": vector_config.embedding_batch_size,
            "available_models": list(EMBEDDING_MODELS.keys()),
            "is_initialized": self.model is not None
        }
    
    async def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        model_key = f"{self.model_name}:{self.model_dimension}"
        return f"embedding:{model_key}:{text_hash}"
    
    async def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache if available."""
        try:
            redis_client = await get_redis_client()
            if not redis_client:
                return None
            
            cache_key = await self._get_cache_key(text)
            cached_data = await redis_client.get(cache_key)
            
            if cached_data:
                embedding = pickle.loads(cached_data)
                logger.debug("Retrieved embedding from cache")
                return embedding
            
            return None
            
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {str(e)}")
            return None
    
    async def _cache_embedding(self, text: str, embedding: List[float]):
        """Cache embedding result."""
        try:
            redis_client = await get_redis_client()
            if not redis_client:
                return
            
            cache_key = await self._get_cache_key(text)
            cached_data = pickle.dumps(embedding)
            
            await redis_client.setex(
                cache_key,
                self._cache_ttl,
                cached_data
            )
            
            logger.debug("Cached embedding result")
            
        except Exception as e:
            logger.debug(f"Cache storage failed: {str(e)}")
    
    async def cleanup(self):
        """Cleanup resources."""
        if self._executor:
            self._executor.shutdown(wait=True)
        
        # Clear model from memory
        self.model = None
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

class MultiModelEmbeddingService:
    """
    Service that manages multiple embedding models for different use cases.
    """
    
    def __init__(self):
        self._services: Dict[str, EmbeddingService] = {}
        self._default_model = "fast"
    
    async def initialize_model(self, model_key: str) -> bool:
        """
        Initialize a specific embedding model.
        
        Args:
            model_key: Key from EMBEDDING_MODELS configuration
            
        Returns:
            bool: True if initialization successful
        """
        if model_key not in EMBEDDING_MODELS:
            logger.error(f"Unknown model key: {model_key}")
            return False
        
        if model_key in self._services:
            logger.info(f"Model {model_key} already initialized")
            return True
        
        try:
            model_config = EMBEDDING_MODELS[model_key]
            service = EmbeddingService(
                model_name=model_config["name"],
                device=vector_config.embedding_device
            )
            
            success = await service.initialize()
            if success:
                self._services[model_key] = service
                logger.info(f"Initialized embedding model: {model_key}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize model {model_key}: {str(e)}")
            return False
    
    async def get_service(self, model_key: Optional[str] = None) -> Optional[EmbeddingService]:
        """
        Get embedding service for a specific model.
        
        Args:
            model_key: Model key or None for default
            
        Returns:
            EmbeddingService instance or None
        """
        model_key = model_key or self._default_model
        
        if model_key not in self._services:
            success = await self.initialize_model(model_key)
            if not success:
                return None
        
        return self._services.get(model_key)
    
    async def encode_text(self, text: str, model_key: Optional[str] = None) -> Optional[List[float]]:
        """Encode text using specified model."""
        service = await self.get_service(model_key)
        if service:
            return await service.encode_text(text)
        return None
    
    async def encode_batch(self, texts: List[str], model_key: Optional[str] = None) -> List[Optional[List[float]]]:
        """Encode batch using specified model."""
        service = await self.get_service(model_key)
        if service:
            return await service.encode_batch(texts)
        return [None] * len(texts)
    
    async def get_all_model_info(self) -> Dict[str, Any]:
        """Get information about all initialized models."""
        info = {
            "initialized_models": list(self._services.keys()),
            "available_models": EMBEDDING_MODELS,
            "default_model": self._default_model
        }
        
        for key, service in self._services.items():
            info[f"model_{key}"] = await service.get_model_info()
        
        return info
    
    async def cleanup(self):
        """Cleanup all services."""
        for service in self._services.values():
            await service.cleanup()
        self._services.clear()

# Global embedding service instances
embedding_service = EmbeddingService()
multi_model_service = MultiModelEmbeddingService()