-- Rollback initial schema

-- Drop triggers
DROP TRIGGER IF EXISTS update_training_state_updated_at ON training_state;
DROP TRIGGER IF EXISTS update_repositories_updated_at ON repositories;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS get_repos_by_language(VARCHAR);
DROP FUNCTION IF EXISTS get_download_stats();

-- Drop tables (in reverse order of creation due to foreign keys)
DROP TABLE IF EXISTS training_state;
DROP TABLE IF EXISTS processing_checkpoints;
DROP TABLE IF EXISTS processing_jobs;
DROP TABLE IF EXISTS processed_files;
DROP TABLE IF EXISTS repositories;

-- Drop extension
DROP EXTENSION IF EXISTS "uuid-ossp";
