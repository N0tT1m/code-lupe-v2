-- Create tables for CodeLupe processing pipeline

-- Jobs table for tracking repository processing
CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    repo_path VARCHAR(1000) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    files_found INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_msg TEXT,
    worker_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processed files table for storing code content and metadata
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES processing_jobs(id),
    file_path VARCHAR(2000) NOT NULL,
    relative_path VARCHAR(1000) NOT NULL,
    content TEXT NOT NULL,
    language VARCHAR(50) NOT NULL,
    lines INTEGER NOT NULL,
    size BIGINT NOT NULL,
    hash VARCHAR(128) NOT NULL UNIQUE,
    repo_name TEXT NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    quality_score INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_repo_path ON processing_jobs(repo_path);
CREATE INDEX IF NOT EXISTS idx_processed_files_job_id ON processed_files(job_id);
CREATE INDEX IF NOT EXISTS idx_processed_files_language ON processed_files(language);
CREATE INDEX IF NOT EXISTS idx_processed_files_quality_score ON processed_files(quality_score);
CREATE INDEX IF NOT EXISTS idx_processed_files_repo_name ON processed_files(repo_name);
CREATE INDEX IF NOT EXISTS idx_processed_files_hash ON processed_files(hash);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO coding_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO coding_user;