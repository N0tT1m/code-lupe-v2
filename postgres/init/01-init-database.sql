-- Create the coding repositories database schema

-- Drop tables if they exist (for development)
DROP TABLE IF EXISTS repositories CASCADE;
DROP TABLE IF EXISTS download_logs CASCADE;

-- Create repositories table
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    url VARCHAR(512) NOT NULL,
    clone_url VARCHAR(512) NOT NULL,
    language VARCHAR(100),
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    watchers INTEGER DEFAULT 0,
    size_kb INTEGER DEFAULT 0,
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    crawled_at TIMESTAMP,
    downloaded_at TIMESTAMP,
    download_status VARCHAR(50) DEFAULT 'pending',
    topics TEXT[],
    is_fork BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    is_private BOOLEAN DEFAULT FALSE,
    default_branch VARCHAR(100) DEFAULT 'main',
    owner_login VARCHAR(255),
    owner_type VARCHAR(50),
    license_name VARCHAR(255),
    license_key VARCHAR(100),
    local_path TEXT,
    error_message TEXT,
    quality_score INTEGER DEFAULT 0,
    code_lines INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0
);

-- Create indexes for better query performance
CREATE INDEX idx_repositories_full_name ON repositories(full_name);
CREATE INDEX idx_repositories_language ON repositories(language);
CREATE INDEX idx_repositories_stars ON repositories(stars DESC);
CREATE INDEX idx_repositories_forks ON repositories(forks DESC);
CREATE INDEX idx_repositories_download_status ON repositories(download_status);
CREATE INDEX idx_repositories_quality_score ON repositories(quality_score DESC);
CREATE INDEX idx_repositories_owner_login ON repositories(owner_login);
CREATE INDEX idx_repositories_topics ON repositories USING GIN(topics);
CREATE INDEX idx_repositories_created_at ON repositories(created_at DESC);
CREATE INDEX idx_repositories_crawled_at ON repositories(crawled_at DESC);

-- Create download logs table for tracking download history
CREATE TABLE download_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    download_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    download_completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    download_size_kb INTEGER,
    duration_seconds INTEGER
);

CREATE INDEX idx_download_logs_repository_id ON download_logs(repository_id);
CREATE INDEX idx_download_logs_status ON download_logs(status);
CREATE INDEX idx_download_logs_started_at ON download_logs(download_started_at DESC);

-- Create a view for repository statistics
CREATE VIEW repository_stats AS
SELECT 
    language,
    COUNT(*) as total_repos,
    AVG(stars) as avg_stars,
    AVG(forks) as avg_forks,
    AVG(quality_score) as avg_quality_score,
    SUM(CASE WHEN download_status = 'downloaded' THEN 1 ELSE 0 END) as downloaded_count,
    SUM(CASE WHEN download_status = 'failed' THEN 1 ELSE 0 END) as failed_count,
    SUM(CASE WHEN download_status = 'pending' THEN 1 ELSE 0 END) as pending_count
FROM repositories 
WHERE language IS NOT NULL 
GROUP BY language
ORDER BY total_repos DESC;

-- Create a view for top repositories by quality score
CREATE VIEW top_quality_repos AS
SELECT 
    full_name,
    language,
    stars,
    forks,
    quality_score,
    download_status,
    description
FROM repositories 
WHERE quality_score > 0
ORDER BY quality_score DESC, stars DESC
LIMIT 100;

-- Insert some initial data or configuration if needed
-- This could include default quality thresholds, language mappings, etc.

-- Grant permissions to the coding_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO coding_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO coding_user;
GRANT USAGE ON SCHEMA public TO coding_user;

-- Create a function to update the last_updated timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.last_updated = now(); 
   RETURN NEW;
END;
$$ language 'plpgsql';

-- Add some useful stored procedures
CREATE OR REPLACE FUNCTION get_download_stats()
RETURNS TABLE (
    total_repos INTEGER,
    downloaded INTEGER,
    failed INTEGER,
    pending INTEGER,
    in_progress INTEGER,
    avg_quality_score NUMERIC,
    top_language TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER as total_repos,
        COUNT(CASE WHEN download_status = 'downloaded' THEN 1 END)::INTEGER as downloaded,
        COUNT(CASE WHEN download_status = 'failed' THEN 1 END)::INTEGER as failed,
        COUNT(CASE WHEN download_status = 'pending' THEN 1 END)::INTEGER as pending,
        COUNT(CASE WHEN download_status = 'downloading' THEN 1 END)::INTEGER as in_progress,
        ROUND(AVG(quality_score), 2) as avg_quality_score,
        (SELECT language FROM repositories GROUP BY language ORDER BY COUNT(*) DESC LIMIT 1) as top_language
    FROM repositories;
END;
$$ LANGUAGE plpgsql;

-- Function to get repositories by language with stats
CREATE OR REPLACE FUNCTION get_repos_by_language(lang_filter TEXT DEFAULT NULL)
RETURNS TABLE (
    full_name TEXT,
    stars INTEGER,
    forks INTEGER,
    quality_score INTEGER,
    download_status TEXT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.full_name::TEXT,
        r.stars,
        r.forks,
        r.quality_score,
        r.download_status::TEXT,
        r.description::TEXT
    FROM repositories r
    WHERE (lang_filter IS NULL OR r.language ILIKE '%' || lang_filter || '%')
    ORDER BY r.quality_score DESC, r.stars DESC;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON TABLE repositories IS 'Main table storing GitHub repository information';
COMMENT ON COLUMN repositories.quality_score IS 'Calculated quality score based on various metrics (0-100)';
COMMENT ON COLUMN repositories.download_status IS 'Current download status: pending, downloading, downloaded, failed';
COMMENT ON TABLE download_logs IS 'Audit log of all download attempts';
COMMENT ON VIEW repository_stats IS 'Aggregated statistics by programming language';
COMMENT ON VIEW top_quality_repos IS 'Top 100 repositories by quality score';