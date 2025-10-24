-- Add repositories table for tracking downloaded repositories

CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    language TEXT,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    quality_score INTEGER DEFAULT 0,
    local_path TEXT,
    download_status TEXT DEFAULT 'pending',
    downloaded_at TIMESTAMP,
    code_lines INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_repos_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS idx_repos_language ON repositories(language);
CREATE INDEX IF NOT EXISTS idx_repos_stars ON repositories(stars DESC);
CREATE INDEX IF NOT EXISTS idx_repos_quality ON repositories(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_repos_status ON repositories(download_status);

-- Add trigger for updated_at
CREATE TRIGGER update_repositories_updated_at BEFORE UPDATE ON repositories
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE repositories IS 'Tracks downloaded GitHub repositories';
COMMENT ON COLUMN repositories.quality_score IS 'Quality score (0-100) based on stars, forks, and code quality';
COMMENT ON COLUMN repositories.download_status IS 'Status: pending, downloading, downloaded, failed';
