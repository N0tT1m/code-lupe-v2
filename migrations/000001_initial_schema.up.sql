-- Initial schema migration
-- Creates all core tables for CodeLupe processing pipeline

-- Processing jobs table
CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    repo_path TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    files_found INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_msg TEXT,
    worker_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Processed files table
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES processing_jobs(id),
    file_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT NOT NULL,
    lines INTEGER NOT NULL,
    size BIGINT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    repo_name TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    quality_score INTEGER DEFAULT 0
);

-- Processing checkpoints for resumability
CREATE TABLE IF NOT EXISTS processing_checkpoints (
    id SERIAL PRIMARY KEY,
    worker_id TEXT NOT NULL,
    last_job_id INTEGER,
    last_processed_count BIGINT,
    checkpoint_time TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_worker ON processing_jobs(worker_id);
CREATE INDEX IF NOT EXISTS idx_files_hash ON processed_files(hash);
CREATE INDEX IF NOT EXISTS idx_files_job ON processed_files(job_id);
CREATE INDEX IF NOT EXISTS idx_files_language ON processed_files(language);
CREATE INDEX IF NOT EXISTS idx_files_quality ON processed_files(quality_score);
CREATE INDEX IF NOT EXISTS idx_checkpoints_worker ON processing_checkpoints(worker_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger to processing_jobs
CREATE TRIGGER update_processing_jobs_updated_at BEFORE UPDATE ON processing_jobs
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE processing_jobs IS 'Tracks repository processing jobs with resumability';
COMMENT ON TABLE processed_files IS 'Stores processed code files with quality metrics';
COMMENT ON TABLE processing_checkpoints IS 'Stores checkpoints for resumable processing';
