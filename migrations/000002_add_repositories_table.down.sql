-- Rollback repositories table

DROP TRIGGER IF EXISTS update_repositories_updated_at ON repositories;

DROP INDEX IF EXISTS idx_repos_status;
DROP INDEX IF EXISTS idx_repos_quality;
DROP INDEX IF EXISTS idx_repos_stars;
DROP INDEX IF EXISTS idx_repos_language;
DROP INDEX IF EXISTS idx_repos_full_name;

DROP TABLE IF EXISTS repositories;
