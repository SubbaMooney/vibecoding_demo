# Data Architecture

## 1. Vector Database Schema (Qdrant)

```json
{
  "collections": {
    "documents": {
      "vectors": {
        "size": 384,
        "distance": "Cosine"
      },
      "payload_schema": {
        "document_id": "keyword",
        "chunk_id": "keyword",
        "page_number": "integer",
        "chunk_type": "keyword",
        "content": "text",
        "metadata": "object"
      },
      "indexes": ["document_id", "chunk_type", "page_number"]
    }
  }
}
```

## 2. PostgreSQL Schema

```sql
-- User Management with Privacy
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for privacy
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    consent_flags JSONB NOT NULL DEFAULT '{}',
    deletion_requested BOOLEAN DEFAULT FALSE
);

-- Document Metadata
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    file_size BIGINT NOT NULL,
    doc_type VARCHAR(20) NOT NULL,
    processing_status VARCHAR(20) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    UNIQUE(user_id, content_hash)
);

-- CRDT Sync State
CREATE TABLE sync_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(64) NOT NULL,
    vector_clock JSONB NOT NULL,
    last_sync TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    state_snapshot JSONB,
    UNIQUE(user_id, device_id)
);

-- Search History (Privacy-Compliant)
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    query_hash VARCHAR(64) NOT NULL,  -- Hashed for privacy
    query_intent VARCHAR(50),
    result_count INTEGER,
    click_through_rate FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE  -- Auto-deletion for privacy
);
```

## 3. Redis Cache Structure

```python
# Cache Keys Structure
cache_keys = {
    # Search result caching
    "search:{query_hash}:{filters_hash}": "SearchResults (TTL: 1h)",
    
    # User session
    "session:{session_id}": "UserSession (TTL: 24h)",
    
    # Document processing status
    "processing:{document_id}": "ProcessingStatus (TTL: 1h)",
    
    # Rate limiting
    "rate_limit:{user_id}:{endpoint}": "RequestCount (TTL: 1min)",
    
    # Feature flags
    "features:{user_id}": "FeatureFlags (TTL: 5min)"
}
```

---
