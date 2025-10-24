-- Initial schema for CodeLupe
-- This migration creates the base tables for the system

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL UNIQUE,
    clone_url TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    language VARCHAR(100),
    description TEXT,
    topics TEXT[],
    size_kb INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_push TIMESTAMP,
    quality_score INTEGER DEFAULT 0,
    download_status VARCHAR(50) DEFAULT 'pending',
    download_path TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt TIMESTAMP
);

-- Create indexes for repositories
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS idx_repositories_language ON repositories(language);
CREATE INDEX IF NOT EXISTS idx_repositories_quality_score ON repositories(quality_score);
CREATE INDEX IF NOT EXISTS idx_repositories_download_status ON repositories(download_status);
CREATE INDEX IF NOT EXISTS idx_repositories_stars ON repositories(stars);

-- Processed files table
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language VARCHAR(100),
    content TEXT,
    content_hash VARCHAR(64),
    quality_score INTEGER DEFAULT 0,
    lines_of_code INTEGER DEFAULT 0,
    complexity_score FLOAT DEFAULT 0.0,
    processed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(repository_id, file_path)
);

-- Create indexes for processed_files
CREATE INDEX IF NOT EXISTS idx_processed_files_repository_id ON processed_files(repository_id);
CREATE INDEX IF NOT EXISTS idx_processed_files_language ON processed_files(language);
CREATE INDEX IF NOT EXISTS idx_processed_files_quality_score ON processed_files(quality_score);
CREATE INDEX IF NOT EXISTS idx_processed_files_content_hash ON processed_files(content_hash);

-- Processing jobs table
CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    job_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    total_repositories INTEGER DEFAULT 0,
    processed_repositories INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for processing_jobs
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_job_id ON processing_jobs(job_id);

-- Processing checkpoints table
CREATE TABLE IF NOT EXISTS processing_checkpoints (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    checkpoint_type VARCHAR(50) NOT NULL,
    checkpoint_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, repository_id, checkpoint_type)
);

-- Create index for processing_checkpoints
CREATE INDEX IF NOT EXISTS idx_processing_checkpoints_job_id ON processing_checkpoints(job_id);

-- Training state table
CREATE TABLE IF NOT EXISTS training_state (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    last_trained_id INTEGER DEFAULT 0,
    total_training_runs INTEGER DEFAULT 0,
    last_trained_at TIMESTAMP,
    training_metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_name)
);

-- Download statistics function
CREATE OR REPLACE FUNCTION get_download_stats()
RETURNS TABLE (
    total_repos BIGINT,
    downloaded BIGINT,
    pending BIGINT,
    failed BIGINT,
    avg_quality_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_repos,
        COUNT(*) FILTER (WHERE download_status = 'completed')::BIGINT as downloaded,
        COUNT(*) FILTER (WHERE download_status = 'pending')::BIGINT as pending,
        COUNT(*) FILTER (WHERE download_status = 'failed')::BIGINT as failed,
        AVG(quality_score) as avg_quality_score
    FROM repositories;
END;
$$ LANGUAGE plpgsql;

-- Repos by language function
CREATE OR REPLACE FUNCTION get_repos_by_language(lang VARCHAR)
RETURNS TABLE (
    id INTEGER,
    full_name VARCHAR,
    stars INTEGER,
    quality_score INTEGER,
    download_status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT r.id, r.full_name, r.stars, r.quality_score, r.download_status
    FROM repositories r
    WHERE r.language = lang
    ORDER BY r.stars DESC;
END;
$$ LANGUAGE plpgsql;

-- Update timestamps trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to repositories
CREATE TRIGGER update_repositories_updated_at
    BEFORE UPDATE ON repositories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to training_state
CREATE TRIGGER update_training_state_updated_at
    BEFORE UPDATE ON training_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE repositories IS 'Stores GitHub repository metadata and download status';
COMMENT ON TABLE processed_files IS 'Stores processed code files extracted from repositories';
COMMENT ON TABLE processing_jobs IS 'Tracks batch processing jobs';
COMMENT ON TABLE processing_checkpoints IS 'Stores checkpoints for resumable processing';
COMMENT ON TABLE training_state IS 'Stores AI model training state and metrics';
