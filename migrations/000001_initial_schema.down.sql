-- Rollback initial schema migration

-- Drop triggers
DROP TRIGGER IF EXISTS update_processing_jobs_updated_at ON processing_jobs;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS idx_checkpoints_worker;
DROP INDEX IF EXISTS idx_files_quality;
DROP INDEX IF EXISTS idx_files_language;
DROP INDEX IF EXISTS idx_files_job;
DROP INDEX IF EXISTS idx_files_hash;
DROP INDEX IF EXISTS idx_jobs_worker;
DROP INDEX IF EXISTS idx_jobs_status;

-- Drop tables (in reverse order due to foreign keys)
DROP TABLE IF EXISTS processing_checkpoints;
DROP TABLE IF EXISTS processed_files;
DROP TABLE IF EXISTS processing_jobs;
