"""
Database configuration and connection management
Supports both sync and async operations with SQLAlchemy
"""

from typing import AsyncGenerator, Optional
import structlog
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Database metadata and base model
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Async database engine
async_engine = create_async_engine(
    str(settings.database_url),
    echo=settings.database_echo,
    poolclass=QueuePool,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "server_settings": {
            "application_name": "mcp_rag_server",
            "jit": "off"
        }
    }
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

# Sync database engine (for migrations and admin tasks)
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.database_echo,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Sync session factory
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()


def get_sync_db():
    """
    Context manager for sync database session
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Database session error", error=str(e))
        raise
    finally:
        db.close()


class DatabaseManager:
    """Database connection and health management"""
    
    def __init__(self):
        self._async_engine = async_engine
        self._sync_engine = sync_engine
    
    async def check_connection(self) -> bool:
        """Check if database connection is healthy"""
        try:
            async with self._async_engine.begin() as conn:
                result = await conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    async def close_connections(self):
        """Close all database connections"""
        await self._async_engine.dispose()
        self._sync_engine.dispose()
        logger.info("Database connections closed")
    
    def get_connection_info(self) -> dict:
        """Get database connection information"""
        return {
            "database_url": str(settings.database_url).split("@")[-1],  # Hide credentials
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "engine_echo": settings.database_echo,
        }


# Global database manager instance
db_manager = DatabaseManager()


async def init_database():
    """Initialize database connections and create tables if needed"""
    try:
        # Check connection
        is_connected = await db_manager.check_connection()
        if is_connected:
            logger.info("Database connection established successfully")
        else:
            raise Exception("Failed to establish database connection")
            
        # Create tables (in production, use Alembic migrations instead)
        if not settings.is_production:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created/verified")
                
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise


async def close_database():
    """Close database connections"""
    await db_manager.close_connections()


# Database utilities
class DatabaseUtils:
    """Database utility functions"""
    
    @staticmethod
    async def execute_raw_query(query: str, params: Optional[dict] = None):
        """Execute raw SQL query"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(query, params or {})
            await session.commit()
            return result
    
    @staticmethod
    async def get_table_stats() -> dict:
        """Get database table statistics"""
        stats_query = """
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC;
        """
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(stats_query)
            rows = result.fetchall()
            return [
                {
                    "schema": row.schemaname,
                    "table": row.tablename,
                    "inserts": row.inserts,
                    "updates": row.updates,
                    "deletes": row.deletes,
                    "live_tuples": row.live_tuples,
                    "dead_tuples": row.dead_tuples
                }
                for row in rows
            ]
    
    @staticmethod
    async def get_connection_stats() -> dict:
        """Get database connection statistics"""
        stats_query = """
        SELECT 
            state,
            count(*) as count
        FROM pg_stat_activity
        WHERE datname = current_database()
        GROUP BY state;
        """
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(stats_query)
            rows = result.fetchall()
            return {row.state or "unknown": row.count for row in rows}
    
    @staticmethod
    async def cleanup_expired_data():
        """Clean up expired data based on retention policies"""
        cleanup_queries = [
            # Clean expired search history
            "DELETE FROM search_history WHERE expires_at < NOW()",
            
            # Clean expired sessions
            "DELETE FROM user_sessions WHERE expires_at < NOW()",
            
            # Clean old audit logs (keep for data_retention_days)
            f"DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '{settings.data_retention_days} days'",
            
            # Clean old rate limiting records
            "DELETE FROM rate_limits WHERE window_start < NOW() - INTERVAL '1 hour'",
        ]
        
        total_deleted = 0
        async with AsyncSessionLocal() as session:
            for query in cleanup_queries:
                try:
                    result = await session.execute(query)
                    deleted = result.rowcount
                    total_deleted += deleted
                    logger.info(f"Cleanup query executed", query=query, deleted_rows=deleted)
                except Exception as e:
                    logger.error(f"Cleanup query failed", query=query, error=str(e))
            
            await session.commit()
            
        logger.info("Database cleanup completed", total_deleted_rows=total_deleted)
        return total_deleted


# Export key components
__all__ = [
    "Base",
    "async_engine",
    "sync_engine",
    "AsyncSessionLocal",
    "SyncSessionLocal",
    "get_async_db",
    "get_sync_db",
    "db_manager",
    "init_database",
    "close_database",
    "DatabaseUtils",
]