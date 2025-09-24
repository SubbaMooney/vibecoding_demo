"""
Configuration management for MCP RAG Server
Supports environment-based configuration with validation
"""

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseSettings, validator, Field
from pydantic.networks import PostgresDsn, RedisDsn


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Basic app settings
    app_name: str = "MCP RAG Server"
    version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # API settings
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Security settings
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Database settings
    database_url: PostgresDsn = Field(..., env="DATABASE_URL")
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis settings
    redis_url: RedisDsn = Field(..., env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    cache_ttl: int = 3600
    session_ttl: int = 86400
    
    # Vector database settings
    qdrant_url: str = Field(..., env="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    vector_collection_name: str = "documents"
    vector_size: int = 384
    vector_distance_metric: str = "Cosine"
    
    # Object storage settings
    s3_endpoint: str = Field(..., env="S3_ENDPOINT")
    s3_access_key: str = Field(..., env="S3_ACCESS_KEY")
    s3_secret_key: str = Field(..., env="S3_SECRET_KEY")
    s3_bucket_name: str = "mcp-rag-documents"
    s3_region: str = "us-east-1"
    
    # MCP Protocol settings
    mcp_protocol_version: str = Field(default="1.0", env="MCP_PROTOCOL_VERSION")
    mcp_server_port: int = 8001
    mcp_timeout_seconds: int = 30
    mcp_retry_attempts: int = 3
    
    # Document processing settings
    max_document_size_mb: int = 50
    supported_file_types: List[str] = ["pdf", "docx", "md", "txt"]
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunks_per_document: int = 1000
    
    # Search settings
    default_search_limit: int = 20
    max_search_limit: int = 100
    similarity_threshold: float = 0.7
    search_timeout_seconds: int = 30
    
    # ML/AI settings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL"
    )
    embedding_device: str = "cpu"  # or "cuda" if GPU available
    model_cache_dir: str = "./models"
    
    # Rate limiting settings
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 100
    upload_rate_limit_per_minute: int = 10
    
    # Monitoring and logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = True
    metrics_port: int = 9090
    jaeger_endpoint: Optional[str] = Field(default=None, env="JAEGER_ENDPOINT")
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # Sync settings (CRDT)
    sync_port: int = 8003
    sync_batch_size: int = 100
    sync_interval_seconds: int = 30
    conflict_resolution_strategy: str = "last_write_wins"
    
    # Accessibility settings
    accessibility_port: int = 8004
    enable_voice_synthesis: bool = True
    enable_voice_recognition: bool = True
    default_voice_speed: float = 1.0
    
    # Privacy and compliance settings
    data_retention_days: int = 365
    enable_analytics: bool = True
    require_explicit_consent: bool = True
    anonymize_logs: bool = True
    gdpr_compliance: bool = True
    
    # Feature flags
    enable_personalization: bool = True
    enable_federated_learning: bool = True
    enable_offline_mode: bool = True
    enable_mobile_optimizations: bool = True
    
    # Performance settings
    worker_processes: int = 4
    worker_connections: int = 1000
    keepalive_timeout: int = 65
    client_max_body_size: str = "50m"
    
    # CORS settings
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    @validator("cors_origins", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("supported_file_types", pre=True)
    def parse_file_types(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        allowed_envs = ["development", "testing", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of {allowed_envs}")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v
    
    @validator("vector_distance_metric")
    def validate_distance_metric(cls, v: str) -> str:
        allowed_metrics = ["Cosine", "Euclidean", "Dot"]
        if v not in allowed_metrics:
            raise ValueError(f"Distance metric must be one of {allowed_metrics}")
        return v
    
    @validator("conflict_resolution_strategy")
    def validate_conflict_resolution(cls, v: str) -> str:
        allowed_strategies = ["last_write_wins", "first_write_wins", "manual"]
        if v not in allowed_strategies:
            raise ValueError(f"Conflict resolution must be one of {allowed_strategies}")
        return v
    
    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for non-async contexts"""
        return str(self.database_url).replace("postgresql+asyncpg", "postgresql")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"
    
    @property
    def redis_config(self) -> Dict[str, Any]:
        """Redis connection configuration"""
        config = {"url": str(self.redis_url)}
        if self.redis_password:
            config["password"] = self.redis_password
        return config
    
    @property
    def s3_config(self) -> Dict[str, Any]:
        """S3 client configuration"""
        return {
            "endpoint_url": self.s3_endpoint,
            "aws_access_key_id": self.s3_access_key,
            "aws_secret_access_key": self.s3_secret_key,
            "region_name": self.s3_region,
        }
    
    @property
    def qdrant_config(self) -> Dict[str, Any]:
        """Qdrant client configuration"""
        config = {"url": self.qdrant_url}
        if self.qdrant_api_key:
            config["api_key"] = self.qdrant_api_key
        return config
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()


# Environment-specific configurations
class DevelopmentSettings(Settings):
    """Development environment settings"""
    debug: bool = True
    database_echo: bool = True
    log_level: str = "DEBUG"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]


class ProductionSettings(Settings):
    """Production environment settings"""
    debug: bool = False
    database_echo: bool = False
    log_level: str = "INFO"
    anonymize_logs: bool = True
    require_explicit_consent: bool = True


class TestingSettings(Settings):
    """Testing environment settings"""
    debug: bool = True
    database_echo: bool = False
    log_level: str = "WARNING"
    # Use in-memory databases for testing
    database_url: str = "sqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/1"


def get_settings_for_environment(env: str) -> Settings:
    """Get settings for specific environment"""
    settings_map = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "testing": TestingSettings,
    }
    
    settings_class = settings_map.get(env, Settings)
    return settings_class()