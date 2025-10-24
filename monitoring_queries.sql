-- CodeLupe Processing Monitoring Queries
-- Use these in Grafana or run directly in PostgreSQL

-- Overall Progress Dashboard
SELECT 
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
    COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs,
    ROUND(COUNT(*) FILTER (WHERE status = 'completed') * 100.0 / COUNT(*), 2) as completion_percentage
FROM processing_jobs;

-- Processing Rate Statistics
SELECT 
    COUNT(*) as total_files,
    SUM(size) as total_bytes,
    ROUND(SUM(size) / 1024.0 / 1024.0, 2) as total_mb,
    AVG(quality_score) as avg_quality_score,
    COUNT(DISTINCT language) as languages_count
FROM processed_files;

-- Language Distribution
SELECT 
    language,
    COUNT(*) as file_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM processed_files), 2) as percentage,
    SUM(size) as total_bytes,
    ROUND(AVG(quality_score), 1) as avg_quality
FROM processed_files
GROUP BY language
ORDER BY file_count DESC;

-- Repository Processing Status
SELECT 
    repo_path,
    status,
    files_found,
    files_processed,
    worker_id,
    started_at,
    completed_at,
    CASE 
        WHEN completed_at IS NOT NULL THEN 
            EXTRACT(EPOCH FROM (completed_at - started_at))/60.0
        WHEN started_at IS NOT NULL THEN 
            EXTRACT(EPOCH FROM (NOW() - started_at))/60.0
        ELSE NULL
    END as processing_time_minutes
FROM processing_jobs
ORDER BY id DESC
LIMIT 20;

-- Failed Jobs Analysis
SELECT 
    repo_path,
    error_msg,
    worker_id,
    started_at,
    updated_at
FROM processing_jobs
WHERE status = 'failed'
ORDER BY updated_at DESC;

-- Worker Performance
SELECT 
    worker_id,
    COUNT(*) as jobs_processed,
    AVG(files_processed) as avg_files_per_job,
    MIN(started_at) as first_job,
    MAX(completed_at) as last_job
FROM processing_jobs
WHERE status = 'completed' AND worker_id IS NOT NULL
GROUP BY worker_id
ORDER BY jobs_processed DESC;

-- Processing Timeline (for charts)
SELECT 
    DATE_TRUNC('hour', processed_at) as hour,
    COUNT(*) as files_processed,
    COUNT(DISTINCT job_id) as jobs_completed,
    SUM(size) as bytes_processed
FROM processed_files
WHERE processed_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Quality Score Distribution
SELECT 
    CASE 
        WHEN quality_score >= 90 THEN 'Excellent (90-100)'
        WHEN quality_score >= 80 THEN 'Good (80-89)'
        WHEN quality_score >= 70 THEN 'Fair (70-79)'
        WHEN quality_score >= 60 THEN 'Poor (60-69)'
        ELSE 'Very Poor (0-59)'
    END as quality_tier,
    COUNT(*) as file_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM processed_files), 2) as percentage
FROM processed_files
GROUP BY quality_tier
ORDER BY 
    CASE 
        WHEN quality_score >= 90 THEN 1
        WHEN quality_score >= 80 THEN 2
        WHEN quality_score >= 70 THEN 3
        WHEN quality_score >= 60 THEN 4
        ELSE 5
    END;

-- Recent Processing Activity
SELECT 
    pf.processed_at,
    pf.language,
    pf.repo_name,
    pf.lines,
    pf.quality_score,
    pj.worker_id
FROM processed_files pf
JOIN processing_jobs pj ON pf.job_id = pj.id
ORDER BY pf.processed_at DESC
LIMIT 50;

-- Repository Size Analysis
SELECT 
    repo_name,
    COUNT(*) as file_count,
    SUM(size) as total_size_bytes,
    ROUND(SUM(size) / 1024.0 / 1024.0, 2) as total_size_mb,
    AVG(lines) as avg_lines_per_file,
    AVG(quality_score) as avg_quality,
    string_agg(DISTINCT language, ', ') as languages
FROM processed_files
GROUP BY repo_name
HAVING COUNT(*) >= 10
ORDER BY file_count DESC
LIMIT 20;

-- Checkpoints and Recovery
SELECT 
    worker_id,
    last_job_id,
    last_processed_count,
    checkpoint_time,
    EXTRACT(EPOCH FROM (NOW() - checkpoint_time))/60.0 as minutes_since_checkpoint
FROM processing_checkpoints
ORDER BY checkpoint_time DESC
LIMIT 10;

-- Real-time Processing Rate (files per minute)
WITH recent_activity AS (
    SELECT 
        DATE_TRUNC('minute', processed_at) as minute,
        COUNT(*) as files_count
    FROM processed_files
    WHERE processed_at >= NOW() - INTERVAL '10 minutes'
    GROUP BY minute
)
SELECT 
    minute,
    files_count,
    AVG(files_count) OVER (ORDER BY minute ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as moving_avg_5min
FROM recent_activity
ORDER BY minute DESC;

-- Storage Usage Estimation
SELECT 
    'Database Size' as metric,
    pg_size_pretty(pg_database_size(current_database())) as size
UNION ALL
SELECT 
    'processed_files table',
    pg_size_pretty(pg_total_relation_size('processed_files'))
UNION ALL
SELECT 
    'processing_jobs table',
    pg_size_pretty(pg_total_relation_size('processing_jobs'));

-- Export ready dataset query (for training)
-- This creates a JSON export suitable for model training
SELECT 
    json_build_object(
        'text', content,
        'meta', json_build_object(
            'language', language,
            'lines', lines,
            'path', relative_path,
            'repo', repo_name,
            'quality_score', quality_score,
            'size', size
        )
    ) as training_sample
FROM processed_files
WHERE quality_score >= 70  -- Only include good quality files
ORDER BY quality_score DESC, size DESC;