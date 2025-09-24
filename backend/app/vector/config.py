"""
Vector database and embedding service configuration.

This module provides configuration settings for Qdrant vector database,
embedding models, and search parameters.
"""

from pydantic import BaseSettings, Field
from typing import Optional, List
import os

class VectorConfig(BaseSettings):
    """Vector search configuration."""
    
    # Qdrant Configuration
    qdrant_host: str = Field(default="localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, env="QDRANT_PORT")
    qdrant_grpc_port: int = Field(default=6334, env="QDRANT_GRPC_PORT")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    qdrant_https: bool = Field(default=False, env="QDRANT_HTTPS")
    
    # Collection Configuration
    default_collection_name: str = Field(default="documents", env="QDRANT_COLLECTION_NAME")
    vector_size: int = Field(default=384, env="VECTOR_SIZE")  # all-MiniLM-L6-v2 dimension
    distance_metric: str = Field(default="Cosine", env="DISTANCE_METRIC")  # Cosine, Dot, Euclid
    
    # Embedding Model Configuration
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2", 
        env="EMBEDDING_MODEL_NAME"
    )
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")  # cpu, cuda
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    max_sequence_length: int = Field(default=512, env="MAX_SEQUENCE_LENGTH")
    
    # Search Configuration
    default_search_limit: int = Field(default=10, env="DEFAULT_SEARCH_LIMIT")
    max_search_limit: int = Field(default=100, env="MAX_SEARCH_LIMIT")
    search_score_threshold: float = Field(default=0.7, env="SEARCH_SCORE_THRESHOLD")
    
    # Chunking Configuration
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")  # characters per chunk
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")  # character overlap
    
    # Performance Configuration
    indexing_batch_size: int = Field(default=100, env="INDEXING_BATCH_SIZE")
    connection_timeout: int = Field(default=30, env="CONNECTION_TIMEOUT")
    request_timeout: int = Field(default=60, env="REQUEST_TIMEOUT")
    
    # Hybrid Search Configuration
    semantic_weight: float = Field(default=0.7, env="SEMANTIC_WEIGHT")
    keyword_weight: float = Field(default=0.3, env="KEYWORD_WEIGHT")
    bm25_k1: float = Field(default=1.2, env="BM25_K1")
    bm25_b: float = Field(default=0.75, env="BM25_B")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global configuration instance
vector_config = VectorConfig()

# Model configurations for different use cases
EMBEDDING_MODELS = {
    "multilingual": {
        "name": "paraphrase-multilingual-MiniLM-L12-v2",
        "dimension": 384,
        "description": "Best for multilingual content"
    },
    "fast": {
        "name": "all-MiniLM-L6-v2", 
        "dimension": 384,
        "description": "Fast and efficient for English content"
    },
    "accurate": {
        "name": "all-mpnet-base-v2",
        "dimension": 768,
        "description": "Most accurate for English content"
    },
    "large": {
        "name": "all-MiniLM-L12-v2",
        "dimension": 384,
        "description": "Balanced performance and accuracy"
    }
}

# Search configurations for different scenarios
SEARCH_CONFIGS = {
    "precise": {
        "score_threshold": 0.8,
        "semantic_weight": 0.9,
        "keyword_weight": 0.1
    },
    "balanced": {
        "score_threshold": 0.7,
        "semantic_weight": 0.7,
        "keyword_weight": 0.3
    },
    "broad": {
        "score_threshold": 0.5,
        "semantic_weight": 0.5,
        "keyword_weight": 0.5
    }
}