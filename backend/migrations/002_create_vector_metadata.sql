-- Migration: Create vector database metadata and Qdrant integration tables
-- Description: Support tables for Qdrant vector operations and metadata tracking
-- Author: MCP RAG Team
-- Date: 2024-01-01

-- Vector collections metadata
CREATE TABLE vector_collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    vector_size INTEGER NOT NULL,
    distance_metric VARCHAR(20) NOT NULL DEFAULT 'Cosine'
        CHECK (distance_metric IN ('Cosine', 'Euclidean', 'Dot')),
    qdrant_collection_name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for vector_collections
CREATE INDEX idx_vector_collections_name ON vector_collections(name);
CREATE INDEX idx_vector_collections_is_active ON vector_collections(is_active);

-- Vector embeddings metadata (tracks what's in Qdrant)
CREATE TABLE vector_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID NOT NULL REFERENCES vector_collections(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    qdrant_point_id VARCHAR(100) NOT NULL,
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    embedding_version INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for vector_embeddings
CREATE UNIQUE INDEX idx_vector_embeddings_chunk_collection 
    ON vector_embeddings(chunk_id, collection_id);
CREATE INDEX idx_vector_embeddings_collection_id ON vector_embeddings(collection_id);
CREATE INDEX idx_vector_embeddings_qdrant_point_id ON vector_embeddings(qdrant_point_id);
CREATE INDEX idx_vector_embeddings_model ON vector_embeddings(embedding_model);

-- Search sessions for analytics and caching
CREATE TABLE search_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) NOT NULL,
    search_type VARCHAR(20) NOT NULL DEFAULT 'hybrid',
    filters JSONB NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    result_count INTEGER NOT NULL DEFAULT 0,
    response_time_ms INTEGER NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for search_sessions
CREATE INDEX idx_search_sessions_user_id ON search_sessions(user_id);
CREATE INDEX idx_search_sessions_session_id ON search_sessions(session_id);
CREATE INDEX idx_search_sessions_query_hash ON search_sessions(query_hash);
CREATE INDEX idx_search_sessions_created_at ON search_sessions(created_at);

-- Search results for caching and analytics
CREATE TABLE search_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES search_sessions(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    rank_position INTEGER NOT NULL,
    relevance_score FLOAT NOT NULL,
    search_score_details JSONB NULL,
    clicked BOOLEAN DEFAULT FALSE,
    clicked_at TIMESTAMP WITH TIME ZONE NULL
);

-- Indexes for search_results
CREATE INDEX idx_search_results_session_id ON search_results(session_id);
CREATE INDEX idx_search_results_chunk_id ON search_results(chunk_id);
CREATE INDEX idx_search_results_rank_position ON search_results(rank_position);
CREATE INDEX idx_search_results_clicked ON search_results(clicked) WHERE clicked = TRUE;

-- MCP protocol versions and compatibility
CREATE TABLE mcp_protocol_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(20) NOT NULL UNIQUE,
    specification_url TEXT NULL,
    is_supported BOOLEAN DEFAULT TRUE,
    deprecated_at TIMESTAMP WITH TIME ZONE NULL,
    tools_schema JSONB NOT NULL DEFAULT '{}',
    compatibility_notes TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for mcp_protocol_versions
CREATE INDEX idx_mcp_protocol_versions_version ON mcp_protocol_versions(version);
CREATE INDEX idx_mcp_protocol_versions_is_supported ON mcp_protocol_versions(is_supported);

-- MCP tool usage analytics
CREATE TABLE mcp_tool_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    tool_name VARCHAR(100) NOT NULL,
    protocol_version VARCHAR(20) NOT NULL,
    parameters JSONB NULL,
    execution_time_ms INTEGER NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT NULL,
    client_info JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for mcp_tool_usage
CREATE INDEX idx_mcp_tool_usage_user_id ON mcp_tool_usage(user_id);
CREATE INDEX idx_mcp_tool_usage_tool_name ON mcp_tool_usage(tool_name);
CREATE INDEX idx_mcp_tool_usage_protocol_version ON mcp_tool_usage(protocol_version);
CREATE INDEX idx_mcp_tool_usage_success ON mcp_tool_usage(success);
CREATE INDEX idx_mcp_tool_usage_created_at ON mcp_tool_usage(created_at);

-- Personalization model metadata
CREATE TABLE personalization_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_type VARCHAR(50) NOT NULL DEFAULT 'federated_learning',
    model_version INTEGER NOT NULL DEFAULT 1,
    model_data JSONB NULL, -- Encrypted model weights
    training_data_hash VARCHAR(64) NULL,
    privacy_budget_used FLOAT DEFAULT 0.0,
    last_trained_at TIMESTAMP WITH TIME ZONE NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for personalization_models
CREATE UNIQUE INDEX idx_personalization_models_user_type 
    ON personalization_models(user_id, model_type) 
    WHERE is_active = TRUE;
CREATE INDEX idx_personalization_models_user_id ON personalization_models(user_id);
CREATE INDEX idx_personalization_models_last_trained ON personalization_models(last_trained_at);

-- Content recommendations cache
CREATE TABLE content_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommendation_type VARCHAR(50) NOT NULL,
    recommended_content_id UUID NOT NULL,
    recommendation_score FLOAT NOT NULL,
    context JSONB NULL,
    is_shown BOOLEAN DEFAULT FALSE,
    is_clicked BOOLEAN DEFAULT FALSE,
    shown_at TIMESTAMP WITH TIME ZONE NULL,
    clicked_at TIMESTAMP WITH TIME ZONE NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for content_recommendations
CREATE INDEX idx_content_recommendations_user_id ON content_recommendations(user_id);
CREATE INDEX idx_content_recommendations_type ON content_recommendations(recommendation_type);
CREATE INDEX idx_content_recommendations_expires_at ON content_recommendations(expires_at);
CREATE INDEX idx_content_recommendations_score ON content_recommendations(recommendation_score DESC);

-- System configuration for dynamic settings
CREATE TABLE system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    description TEXT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    is_user_configurable BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for system_config
CREATE INDEX idx_system_config_key ON system_config(config_key);

-- Performance metrics table for monitoring
CREATE TABLE performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(20) NOT NULL DEFAULT 'gauge'
        CHECK (metric_type IN ('gauge', 'counter', 'histogram')),
    tags JSONB NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance_metrics
CREATE INDEX idx_performance_metrics_name ON performance_metrics(metric_name);
CREATE INDEX idx_performance_metrics_timestamp ON performance_metrics(timestamp);
CREATE INDEX idx_performance_metrics_type ON performance_metrics(metric_type);

-- Feature flags for A/B testing and gradual rollouts
CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flag_name VARCHAR(100) NOT NULL UNIQUE,
    flag_value BOOLEAN NOT NULL DEFAULT FALSE,
    conditions JSONB NULL, -- User conditions for targeting
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage BETWEEN 0 AND 100),
    description TEXT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for feature_flags
CREATE INDEX idx_feature_flags_name ON feature_flags(flag_name);
CREATE INDEX idx_feature_flags_is_active ON feature_flags(is_active);

-- Apply updated_at triggers to new tables
CREATE TRIGGER update_vector_collections_updated_at BEFORE UPDATE ON vector_collections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vector_embeddings_updated_at BEFORE UPDATE ON vector_embeddings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_personalization_models_updated_at BEFORE UPDATE ON personalization_models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views for analytics and monitoring
CREATE VIEW search_analytics AS
SELECT 
    DATE_TRUNC('hour', s.created_at) as hour,
    s.search_type,
    COUNT(*) as search_count,
    AVG(s.response_time_ms) as avg_response_time_ms,
    AVG(s.result_count) as avg_result_count,
    COUNT(DISTINCT s.user_id) as unique_users
FROM search_sessions s
WHERE s.created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', s.created_at), s.search_type
ORDER BY hour DESC;

CREATE VIEW mcp_tool_analytics AS
SELECT 
    tool_name,
    protocol_version,
    DATE_TRUNC('day', created_at) as day,
    COUNT(*) as usage_count,
    AVG(execution_time_ms) as avg_execution_time,
    (COUNT(*) FILTER (WHERE success = TRUE))::FLOAT / COUNT(*) as success_rate
FROM mcp_tool_usage
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY tool_name, protocol_version, DATE_TRUNC('day', created_at)
ORDER BY day DESC, usage_count DESC;

CREATE VIEW user_engagement_metrics AS
SELECT 
    u.id as user_id,
    COUNT(DISTINCT s.id) as search_sessions,
    COUNT(DISTINCT d.id) as uploaded_documents,
    MAX(s.created_at) as last_search_at,
    MAX(d.created_at) as last_upload_at,
    COALESCE(AVG(sr.relevance_score), 0) as avg_search_relevance
FROM users u
LEFT JOIN search_sessions s ON u.id = s.user_id 
    AND s.created_at >= NOW() - INTERVAL '30 days'
LEFT JOIN documents d ON u.id = d.user_id 
    AND d.created_at >= NOW() - INTERVAL '30 days'
LEFT JOIN search_results sr ON s.id = sr.session_id
WHERE u.deletion_requested = FALSE
GROUP BY u.id;

-- Functions for analytics
CREATE OR REPLACE FUNCTION get_search_performance_metrics(
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW() - INTERVAL '1 hour',
    end_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
RETURNS TABLE(
    metric_name TEXT,
    metric_value FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'total_searches'::TEXT,
        COUNT(*)::FLOAT
    FROM search_sessions
    WHERE created_at BETWEEN start_time AND end_time
    
    UNION ALL
    
    SELECT 
        'avg_response_time_ms'::TEXT,
        AVG(response_time_ms)::FLOAT
    FROM search_sessions
    WHERE created_at BETWEEN start_time AND end_time
      AND response_time_ms IS NOT NULL
      
    UNION ALL
    
    SELECT 
        'p95_response_time_ms'::TEXT,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::FLOAT
    FROM search_sessions
    WHERE created_at BETWEEN start_time AND end_time
      AND response_time_ms IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup old analytics data
CREATE OR REPLACE FUNCTION cleanup_old_analytics_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    temp_count INTEGER;
BEGIN
    -- Clean up old search sessions (keep 90 days)
    DELETE FROM search_sessions 
    WHERE created_at < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Clean up old MCP tool usage (keep 30 days)
    DELETE FROM mcp_tool_usage 
    WHERE created_at < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Clean up old performance metrics (keep 7 days)
    DELETE FROM performance_metrics 
    WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Clean up expired recommendations
    DELETE FROM content_recommendations 
    WHERE expires_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Insert initial data
INSERT INTO vector_collections (name, description, vector_size, qdrant_collection_name) VALUES
    ('documents', 'Main document embeddings', 384, 'documents'),
    ('queries', 'Query embeddings for caching', 384, 'queries')
ON CONFLICT (name) DO NOTHING;

INSERT INTO mcp_protocol_versions (version, is_supported, tools_schema) VALUES
    ('1.0', TRUE, '{"rag_search": {"parameters": {"query": "string", "limit": "integer"}}}'),
    ('0.9', FALSE, '{"search": {"parameters": {"query": "string"}}}')
ON CONFLICT (version) DO NOTHING;

INSERT INTO system_config (config_key, config_value, description, is_user_configurable) VALUES
    ('max_document_size_mb', '50', 'Maximum document upload size', FALSE),
    ('default_search_limit', '20', 'Default number of search results', TRUE),
    ('enable_personalization', 'true', 'Enable user personalization features', TRUE),
    ('vector_search_threshold', '0.7', 'Minimum similarity threshold', TRUE),
    ('cache_ttl_minutes', '60', 'Cache time-to-live in minutes', FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE vector_collections IS 'Metadata for Qdrant vector collections';
COMMENT ON TABLE vector_embeddings IS 'Tracks embeddings stored in Qdrant';
COMMENT ON TABLE search_sessions IS 'Search analytics and caching data';
COMMENT ON TABLE mcp_protocol_versions IS 'Supported MCP protocol versions';
COMMENT ON TABLE personalization_models IS 'User personalization model metadata';
COMMENT ON TABLE feature_flags IS 'Feature flags for A/B testing and rollouts';