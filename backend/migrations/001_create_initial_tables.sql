-- Migration: Create initial database schema
-- Description: Privacy-compliant user management, document storage, and CRDT sync support
-- Author: MCP RAG Team
-- Date: 2024-01-01

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Users table with privacy-by-design
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 hash for privacy
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    consent_flags JSONB NOT NULL DEFAULT '{}',
    deletion_requested BOOLEAN DEFAULT FALSE,
    deletion_scheduled_at TIMESTAMP WITH TIME ZONE NULL,
    last_login_at TIMESTAMP WITH TIME ZONE NULL
);

-- Indexes for users table
CREATE INDEX idx_users_email_hash ON users(email_hash);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_deletion_requested ON users(deletion_requested) WHERE deletion_requested = TRUE;

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256 of content
    file_size BIGINT NOT NULL,
    doc_type VARCHAR(20) NOT NULL CHECK (doc_type IN ('pdf', 'docx', 'md', 'txt')),
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'deleted')),
    storage_path TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    parent_document_id UUID NULL REFERENCES documents(id) ON DELETE SET NULL
);

-- Indexes for documents table
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);
CREATE INDEX idx_documents_doc_type ON documents(doc_type);
CREATE INDEX idx_documents_processing_status ON documents(processing_status);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE UNIQUE INDEX idx_documents_user_content_unique ON documents(user_id, content_hash);
CREATE INDEX idx_documents_metadata_gin ON documents USING gin(metadata);

-- Document chunks table
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    chunk_type VARCHAR(20) NOT NULL DEFAULT 'text'
        CHECK (chunk_type IN ('text', 'code', 'table', 'list', 'header')),
    page_number INTEGER NULL,
    position_start INTEGER NULL,
    position_end INTEGER NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding_vector_id VARCHAR(64) NULL, -- Reference to Qdrant
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for document_chunks table
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_chunk_type ON document_chunks(chunk_type);
CREATE INDEX idx_chunks_page_number ON document_chunks(page_number);
CREATE UNIQUE INDEX idx_chunks_document_index ON document_chunks(document_id, chunk_index);
CREATE INDEX idx_chunks_content_hash ON document_chunks(content_hash);
CREATE INDEX idx_chunks_metadata_gin ON document_chunks USING gin(metadata);

-- Full-text search index for chunks
CREATE INDEX idx_chunks_content_fulltext ON document_chunks 
    USING gin(to_tsvector('english', content));

-- CRDT sync state table
CREATE TABLE sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(64) NOT NULL,
    vector_clock JSONB NOT NULL DEFAULT '{}',
    last_sync TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    state_snapshot JSONB NULL,
    sync_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for sync_state table
CREATE UNIQUE INDEX idx_sync_state_user_device ON sync_state(user_id, device_id);
CREATE INDEX idx_sync_state_last_sync ON sync_state(last_sync);
CREATE INDEX idx_sync_state_vector_clock_gin ON sync_state USING gin(vector_clock);

-- Search history table (privacy-compliant with auto-expiration)
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query_hash VARCHAR(64) NOT NULL, -- Hashed for privacy
    query_intent VARCHAR(50) NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    click_through_rate FLOAT NULL,
    search_type VARCHAR(20) NOT NULL DEFAULT 'hybrid'
        CHECK (search_type IN ('semantic', 'keyword', 'hybrid')),
    filters_applied JSONB NULL,
    performance_metrics JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() + INTERVAL '90 days')
);

-- Indexes for search_history table
CREATE INDEX idx_search_history_user_id ON search_history(user_id);
CREATE INDEX idx_search_history_created_at ON search_history(created_at);
CREATE INDEX idx_search_history_expires_at ON search_history(expires_at);
CREATE INDEX idx_search_history_query_hash ON search_history(query_hash);

-- User preferences table
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,
    is_synced BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for user_preferences table
CREATE UNIQUE INDEX idx_user_preferences_user_key ON user_preferences(user_id, preference_key);
CREATE INDEX idx_user_preferences_is_synced ON user_preferences(is_synced);

-- Processing jobs table for async operations
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL, -- Usually document_id
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    parameters JSONB NOT NULL DEFAULT '{}',
    result JSONB NULL,
    error_message TEXT NULL,
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    started_at TIMESTAMP WITH TIME ZONE NULL,
    completed_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for processing_jobs table
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX idx_processing_jobs_job_type ON processing_jobs(job_type);
CREATE INDEX idx_processing_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX idx_processing_jobs_entity_id ON processing_jobs(entity_id);
CREATE INDEX idx_processing_jobs_priority ON processing_jobs(priority DESC);
CREATE INDEX idx_processing_jobs_created_at ON processing_jobs(created_at);

-- API keys table for external integrations
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL UNIQUE, -- Hashed API key
    name VARCHAR(100) NOT NULL,
    permissions JSONB NOT NULL DEFAULT '[]',
    rate_limit_per_minute INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE NULL,
    expires_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for api_keys table
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at);

-- Audit log table for security and compliance
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NULL,
    entity_id UUID NULL,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address INET NULL,
    user_agent TEXT NULL,
    request_id VARCHAR(100) NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for audit_logs table
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_entity_type_id ON audit_logs(entity_type, entity_id);

-- Rate limiting table
CREATE TABLE rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identifier VARCHAR(255) NOT NULL, -- IP, user_id, or API key
    endpoint VARCHAR(100) NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for rate_limits table
CREATE UNIQUE INDEX idx_rate_limits_identifier_endpoint ON rate_limits(identifier, endpoint, window_start);
CREATE INDEX idx_rate_limits_window_start ON rate_limits(window_start);

-- Views for common queries
CREATE VIEW active_documents AS
SELECT 
    d.*,
    u.email_hash,
    COUNT(dc.id) as chunk_count
FROM documents d
JOIN users u ON d.user_id = u.id
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processing_status = 'completed'
  AND u.deletion_requested = FALSE
GROUP BY d.id, u.email_hash;

-- Trigger function to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_chunks_updated_at BEFORE UPDATE ON document_chunks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sync_state_updated_at BEFORE UPDATE ON sync_state 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_jobs_updated_at BEFORE UPDATE ON processing_jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean up expired search history
CREATE OR REPLACE FUNCTION cleanup_expired_search_history()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_history 
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function for GDPR-compliant user deletion
CREATE OR REPLACE FUNCTION delete_user_data(target_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    success BOOLEAN := TRUE;
BEGIN
    -- This function handles cascading deletion while maintaining referential integrity
    BEGIN
        -- Delete user documents and related data
        DELETE FROM processing_jobs WHERE user_id = target_user_id;
        DELETE FROM search_history WHERE user_id = target_user_id;
        DELETE FROM user_preferences WHERE user_id = target_user_id;
        DELETE FROM sync_state WHERE user_id = target_user_id;
        DELETE FROM api_keys WHERE user_id = target_user_id;
        DELETE FROM documents WHERE user_id = target_user_id; -- Cascades to chunks
        
        -- Anonymize audit logs (keep for security, remove PII)
        UPDATE audit_logs 
        SET user_id = NULL, 
            details = jsonb_build_object('anonymized', true)
        WHERE user_id = target_user_id;
        
        -- Finally delete the user
        DELETE FROM users WHERE id = target_user_id;
        
    EXCEPTION WHEN OTHERS THEN
        success := FALSE;
        RAISE NOTICE 'Error deleting user data: %', SQLERRM;
    END;
    
    RETURN success;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for performance optimization
CREATE INDEX CONCURRENTLY idx_documents_user_status 
    ON documents(user_id, processing_status) 
    WHERE processing_status IN ('completed', 'failed');

CREATE INDEX CONCURRENTLY idx_chunks_document_page 
    ON document_chunks(document_id, page_number) 
    WHERE page_number IS NOT NULL;

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts with privacy-by-design (email hashed)';
COMMENT ON TABLE documents IS 'Document metadata and processing status';
COMMENT ON TABLE document_chunks IS 'Text chunks from processed documents';
COMMENT ON TABLE sync_state IS 'CRDT sync state for multi-device support';
COMMENT ON TABLE search_history IS 'Search analytics with auto-expiration for privacy';
COMMENT ON TABLE processing_jobs IS 'Async job queue for document processing';
COMMENT ON TABLE audit_logs IS 'Security and compliance audit trail';

COMMENT ON COLUMN users.email_hash IS 'SHA-256 hash of email for privacy compliance';
COMMENT ON COLUMN documents.content_hash IS 'SHA-256 hash for deduplication';
COMMENT ON COLUMN sync_state.vector_clock IS 'CRDT vector clock for conflict resolution';
COMMENT ON COLUMN search_history.expires_at IS 'Auto-expiration for GDPR compliance';

-- Insert initial system user for background processes
INSERT INTO users (id, email_hash, consent_flags) 
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system',
    '{"system_user": true}'
) ON CONFLICT DO NOTHING;