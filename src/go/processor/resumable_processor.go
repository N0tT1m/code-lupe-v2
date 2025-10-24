package main

import (
	"context"
	"crypto/md5"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	_ "github.com/lib/pq"
)

// ProcessingJob represents a resumable processing job
type ProcessingJob struct {
	ID             int        `json:"id"`
	RepoPath       string     `json:"repo_path"`
	Status         string     `json:"status"` // pending, processing, completed, failed
	FilesFound     int        `json:"files_found"`
	FilesProcessed int        `json:"files_processed"`
	StartedAt      *time.Time `json:"started_at"`
	CompletedAt    *time.Time `json:"completed_at"`
	ErrorMsg       string     `json:"error_msg"`
	WorkerID       string     `json:"worker_id"`
}

// ProcessedFile represents a processed code file with full metadata
type ProcessedFile struct {
	ID           int       `json:"id"`
	JobID        int       `json:"job_id"`
	FilePath     string    `json:"file_path"`
	RelativePath string    `json:"relative_path"`
	Content      string    `json:"content"`
	Language     string    `json:"language"`
	Lines        int       `json:"lines"`
	Size         int64     `json:"size"`
	Hash         string    `json:"hash"`
	RepoName     string    `json:"repo_name"`
	ProcessedAt  time.Time `json:"processed_at"`
	QualityScore int       `json:"quality_score"`
}

// ResumableProcessor handles resumable repository processing with PostgreSQL tracking
type ResumableProcessor struct {
	db          *sql.DB
	reposDir    string
	workerCount int
	workerID    string
	batchSize   int
	stats       *ProcessorStats

	// Processing state
	currentJobID int64
	processed    map[string]bool
	mu           sync.RWMutex
}

type ProcessorStats struct {
	JobsCompleted  int64
	FilesProcessed int64
	BytesProcessed int64
	ErrorCount     int64
	StartTime      time.Time
	LastCheckpoint time.Time
}

// NewResumableProcessor creates a new resumable processor
func NewResumableProcessor(dbURL, reposDir string) (*ResumableProcessor, error) {
	// Connect to PostgreSQL with retry logic
	log.Printf("Connecting to PostgreSQL: %s", dbURL)

	var db *sql.DB
	var err error

	// Retry connection with exponential backoff
	for i := 0; i < 10; i++ {
		db, err = sql.Open("postgres", dbURL)
		if err == nil {
			err = db.Ping()
			if err == nil {
				log.Printf("Successfully connected to PostgreSQL")
				break
			}
		}

		waitTime := time.Duration(1<<uint(i)) * time.Second
		if waitTime > 30*time.Second {
			waitTime = 30 * time.Second
		}
		log.Printf("PostgreSQL not ready (attempt %d/10), waiting %v: %v", i+1, waitTime, err)
		time.Sleep(waitTime)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to connect to database after retries: %w", err)
	}

	// Optimize for Ryzen 9 3900X
	workerCount := runtime.GOMAXPROCS(0) * 2 // 48 workers for balanced CPU/IO
	workerID := fmt.Sprintf("worker_%d_%d", os.Getpid(), time.Now().Unix())

	processor := &ResumableProcessor{
		db:          db,
		reposDir:    reposDir,
		workerCount: workerCount,
		workerID:    workerID,
		batchSize:   1000,
		processed:   make(map[string]bool),
		stats: &ProcessorStats{
			StartTime: time.Now(),
		},
	}

	// Initialize database schema
	if err := processor.initializeSchema(); err != nil {
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	fmt.Printf("🚀 Resumable Processor initialized\n")
	fmt.Printf("💻 Worker ID: %s\n", workerID)
	fmt.Printf("🔥 Using %d worker threads\n", workerCount)

	return processor, nil
}

// initializeSchema creates necessary database tables
func (p *ResumableProcessor) initializeSchema() error {
	schema := `
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
	CREATE INDEX IF NOT EXISTS idx_checkpoints_worker ON processing_checkpoints(worker_id);
	`

	_, err := p.db.Exec(schema)
	return err
}

// loadCheckpoint loads the last processing checkpoint
func (p *ResumableProcessor) loadCheckpoint() error {
	var lastJobID sql.NullInt64
	var lastProcessedCount int64

	err := p.db.QueryRow(`
		SELECT last_job_id, last_processed_count 
		FROM processing_checkpoints 
		WHERE worker_id = $1 
		ORDER BY checkpoint_time DESC 
		LIMIT 1
	`, p.workerID).Scan(&lastJobID, &lastProcessedCount)

	if err != nil && err != sql.ErrNoRows {
		return err
	}

	if lastJobID.Valid {
		p.currentJobID = lastJobID.Int64
		p.stats.FilesProcessed = lastProcessedCount
		fmt.Printf("📍 Resuming from job ID %d, %d files processed\n",
			p.currentJobID, lastProcessedCount)
	} else {
		fmt.Printf("🆕 Starting fresh processing\n")
	}

	// Load already processed files to avoid duplicates
	return p.loadProcessedFiles()
}

// loadProcessedFiles loads list of already processed files
func (p *ResumableProcessor) loadProcessedFiles() error {
	rows, err := p.db.Query(`
		SELECT DISTINCT hash FROM processed_files
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		var hash string
		if err := rows.Scan(&hash); err != nil {
			continue
		}
		p.processed[hash] = true
		count++
	}

	fmt.Printf("📋 Loaded %d already processed files\n", count)
	return nil
}

// saveCheckpoint saves current processing state
func (p *ResumableProcessor) saveCheckpoint() error {
	_, err := p.db.Exec(`
		INSERT INTO processing_checkpoints (worker_id, last_job_id, last_processed_count)
		VALUES ($1, $2, $3)
	`, p.workerID, p.currentJobID, p.stats.FilesProcessed)

	p.stats.LastCheckpoint = time.Now()
	return err
}

// discoverRepositories finds all repositories and creates jobs
func (p *ResumableProcessor) discoverRepositories() error {
	fmt.Printf("🔍 Discovering repositories in %s...\n", p.reposDir)

	entries, err := os.ReadDir(p.reposDir)
	if err != nil {
		return err
	}

	var repos []string
	for _, entry := range entries {
		if entry.IsDir() && !strings.HasPrefix(entry.Name(), ".") {
			repoPath := filepath.Join(p.reposDir, entry.Name())
			if p.isValidRepository(repoPath) {
				repos = append(repos, repoPath)
			}
		}
	}

	fmt.Printf("📁 Found %d repositories\n", len(repos))

	// Create jobs for new repositories
	for _, repoPath := range repos {
		_, err := p.db.Exec(`
			INSERT INTO processing_jobs (repo_path, status)
			VALUES ($1, 'pending')
			ON CONFLICT (repo_path) DO NOTHING
		`, repoPath)
		if err != nil {
			log.Printf("⚠️ Failed to create job for %s: %v", repoPath, err)
		}
	}

	return nil
}

// isValidRepository checks if directory is a valid repository
func (p *ResumableProcessor) isValidRepository(repoPath string) bool {
	// Quick git check
	if _, err := os.Stat(filepath.Join(repoPath, ".git")); err == nil {
		return true
	}

	// Check for code files
	codeFiles := 0
	filepath.WalkDir(repoPath, func(path string, d os.DirEntry, err error) error {
		if err != nil || codeFiles >= 5 {
			return filepath.SkipDir
		}

		if d.IsDir() {
			if strings.HasPrefix(d.Name(), ".") ||
				d.Name() == "node_modules" ||
				d.Name() == "__pycache__" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(d.Name()))
		if p.isCodeFile(ext) {
			codeFiles++
		}

		return nil
	})

	return codeFiles >= 3
}

// isCodeFile checks if file extension indicates a code file
func (p *ResumableProcessor) isCodeFile(ext string) bool {
	codeExts := map[string]bool{
		".py": true, ".js": true, ".ts": true, ".jsx": true, ".tsx": true,
		".java": true, ".cpp": true, ".c": true, ".h": true, ".cs": true,
		".php": true, ".rb": true, ".go": true, ".rs": true, ".swift": true,
		".kt": true, ".scala": true, ".sh": true, ".sql": true, ".r": true,
	}
	return codeExts[ext]
}

// getLanguage returns language for file extension
func (p *ResumableProcessor) getLanguage(ext string) string {
	langMap := map[string]string{
		".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
		".jsx": "JavaScript", ".tsx": "TypeScript", ".java": "Java",
		".cpp": "C++", ".c": "C", ".h": "C/C++", ".cs": "C#",
		".php": "PHP", ".rb": "Ruby", ".go": "Go", ".rs": "Rust",
		".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala",
		".sh": "Shell", ".sql": "SQL", ".r": "R",
	}
	if lang, exists := langMap[ext]; exists {
		return lang
	}
	return "Unknown"
}

// getPendingJobs gets jobs that need processing
func (p *ResumableProcessor) getPendingJobs() ([]ProcessingJob, error) {
	rows, err := p.db.Query(`
		SELECT id, repo_path, status, files_found, files_processed
		FROM processing_jobs
		WHERE status IN ('pending', 'failed')
		AND (worker_id IS NULL OR worker_id = $1)
		ORDER BY id
	`, p.workerID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []ProcessingJob
	for rows.Next() {
		var job ProcessingJob
		err := rows.Scan(&job.ID, &job.RepoPath, &job.Status,
			&job.FilesFound, &job.FilesProcessed)
		if err != nil {
			continue
		}
		jobs = append(jobs, job)
	}

	return jobs, nil
}

// claimJob atomically claims a job for processing
func (p *ResumableProcessor) claimJob(jobID int) error {
	result, err := p.db.Exec(`
		UPDATE processing_jobs 
		SET status = 'processing', 
		    worker_id = $1, 
		    started_at = NOW(),
		    updated_at = NOW()
		WHERE id = $2 AND status IN ('pending', 'failed')
	`, p.workerID, jobID)
	if err != nil {
		return err
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}

	if rowsAffected == 0 {
		return fmt.Errorf("job %d already claimed", jobID)
	}

	return nil
}

// processJob processes a single repository job
func (p *ResumableProcessor) processJob(job ProcessingJob) error {
	fmt.Printf("🔄 Processing job %d: %s\n", job.ID, filepath.Base(job.RepoPath))

	// Claim the job
	if err := p.claimJob(job.ID); err != nil {
		return fmt.Errorf("failed to claim job: %w", err)
	}

	p.currentJobID = int64(job.ID)

	// Process repository files
	files, err := p.processRepositoryFiles(job.RepoPath, job.ID)
	if err != nil {
		// Mark job as failed
		p.db.Exec(`
			UPDATE processing_jobs 
			SET status = 'failed', error_msg = $1, updated_at = NOW()
			WHERE id = $2
		`, err.Error(), job.ID)
		return err
	}

	// Mark job as completed
	_, err = p.db.Exec(`
		UPDATE processing_jobs 
		SET status = 'completed', 
		    files_found = $1,
		    files_processed = $2,
		    completed_at = NOW(),
		    updated_at = NOW()
		WHERE id = $3
	`, len(files), len(files), job.ID)

	if err == nil {
		atomic.AddInt64(&p.stats.JobsCompleted, 1)
		fmt.Printf("✅ Completed job %d: %d files processed\n", job.ID, len(files))
	}

	return err
}

// processRepositoryFiles processes all files in a repository
func (p *ResumableProcessor) processRepositoryFiles(repoPath string, jobID int) ([]ProcessedFile, error) {
	var files []ProcessedFile
	var mu sync.Mutex

	// Find all code files
	var filePaths []string
	err := filepath.WalkDir(repoPath, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}

		if d.IsDir() {
			// Skip certain directories
			if strings.HasPrefix(d.Name(), ".") ||
				d.Name() == "node_modules" ||
				d.Name() == "__pycache__" ||
				d.Name() == "target" ||
				d.Name() == "build" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(d.Name()))
		if p.isCodeFile(ext) {
			filePaths = append(filePaths, path)
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	if len(filePaths) == 0 {
		return files, nil
	}

	// Process files in parallel
	fileChan := make(chan string, len(filePaths))
	var wg sync.WaitGroup

	// Start workers
	for i := 0; i < p.workerCount; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for filePath := range fileChan {
				if processedFile := p.processFile(filePath, repoPath, jobID); processedFile != nil {
					mu.Lock()
					files = append(files, *processedFile)
					mu.Unlock()
				}
			}
		}()
	}

	// Send files to workers
	go func() {
		defer close(fileChan)
		for _, filePath := range filePaths {
			fileChan <- filePath
		}
	}()

	wg.Wait()

	// Batch insert files to database
	if len(files) > 0 {
		err = p.batchInsertFiles(files)
		if err != nil {
			return nil, fmt.Errorf("failed to insert files: %w", err)
		}
	}

	return files, nil
}

// processFile processes a single file
func (p *ResumableProcessor) processFile(filePath, repoPath string, jobID int) *ProcessedFile {
	// Read file
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil
	}

	// Basic validation
	if len(content) < 100 || len(content) > 1024*1024 {
		return nil
	}

	text := string(content)
	if len(strings.TrimSpace(text)) == 0 {
		return nil
	}

	// Calculate hash for deduplication
	hasher := md5.New()
	hasher.Write(content)
	hash := fmt.Sprintf("%x", hasher.Sum(nil))

	// Check if already processed
	p.mu.RLock()
	if p.processed[hash] {
		p.mu.RUnlock()
		return nil
	}
	p.mu.RUnlock()

	// Mark as processed
	p.mu.Lock()
	p.processed[hash] = true
	p.mu.Unlock()

	// Get file metadata
	ext := strings.ToLower(filepath.Ext(filePath))
	language := p.getLanguage(ext)
	lines := strings.Count(text, "\n") + 1

	// Calculate relative path
	relPath, _ := filepath.Rel(repoPath, filePath)
	repoName := filepath.Base(repoPath)

	atomic.AddInt64(&p.stats.FilesProcessed, 1)
	atomic.AddInt64(&p.stats.BytesProcessed, int64(len(content)))

	return &ProcessedFile{
		JobID:        jobID,
		FilePath:     filePath,
		RelativePath: relPath,
		Content:      text,
		Language:     language,
		Lines:        lines,
		Size:         int64(len(content)),
		Hash:         hash,
		RepoName:     repoName,
		ProcessedAt:  time.Now(),
		QualityScore: p.calculateQualityScore(text, language),
	}
}

// calculateQualityScore calculates a basic quality score for the file
func (p *ResumableProcessor) calculateQualityScore(content, language string) int {
	score := 50 // Base score

	lines := strings.Count(content, "\n") + 1

	// Line count scoring
	if lines >= 10 && lines <= 500 {
		score += 20
	} else if lines > 500 && lines <= 1000 {
		score += 10
	}

	// Comment detection
	commentRatio := 0.0
	switch language {
	case "Python":
		comments := strings.Count(content, "#")
		commentRatio = float64(comments) / float64(lines)
	case "JavaScript", "TypeScript", "Java", "C++", "C", "Go", "Rust":
		comments := strings.Count(content, "//") + strings.Count(content, "/*")
		commentRatio = float64(comments) / float64(lines)
	}

	if commentRatio > 0.1 && commentRatio < 0.5 {
		score += 15
	}

	// Function detection
	switch language {
	case "Python":
		if strings.Contains(content, "def ") {
			score += 10
		}
	case "JavaScript", "TypeScript":
		if strings.Contains(content, "function ") || strings.Contains(content, "=>") {
			score += 10
		}
	case "Go":
		if strings.Contains(content, "func ") {
			score += 10
		}
	case "Java", "C++", "C#":
		if strings.Contains(content, "public ") || strings.Contains(content, "private ") {
			score += 10
		}
	}

	// Ensure score is between 0-100
	if score > 100 {
		score = 100
	}
	if score < 0 {
		score = 0
	}

	return score
}

// batchInsertFiles inserts files in batches for performance
func (p *ResumableProcessor) batchInsertFiles(files []ProcessedFile) error {
	if len(files) == 0 {
		return nil
	}

	// Use smaller batches to avoid memory issues and transaction conflicts
	batchSize := 100
	totalFiles := len(files)
	var successCount, errorCount int

	for i := 0; i < totalFiles; i += batchSize {
		end := i + batchSize
		if end > totalFiles {
			end = totalFiles
		}

		batch := files[i:end]
		if err := p.insertFileBatch(batch); err != nil {
			log.Printf("⚠️ Batch insert failed for files %d-%d: %v", i, end-1, err)
			errorCount += len(batch)
		} else {
			successCount += len(batch)
		}
	}

	log.Printf("📊 Batch insert completed: %d success, %d errors", successCount, errorCount)

	// Return error only if all batches failed
	if errorCount == totalFiles {
		return fmt.Errorf("failed to insert any files")
	}

	return nil
}

// insertFileBatch inserts a small batch of files with proper error handling
func (p *ResumableProcessor) insertFileBatch(batch []ProcessedFile) error {
	tx, err := p.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		if r := recover(); r != nil {
			tx.Rollback()
			panic(r)
		}
	}()

	stmt, err := tx.Prepare(`
		INSERT INTO processed_files 
		(job_id, file_path, relative_path, content, language, lines, size, hash, repo_name, quality_score)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (hash) DO NOTHING
	`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	for _, file := range batch {
		_, err := stmt.Exec(
			file.JobID, file.FilePath, file.RelativePath, file.Content,
			file.Language, file.Lines, file.Size, file.Hash,
			file.RepoName, file.QualityScore,
		)
		if err != nil {
			tx.Rollback()
			return fmt.Errorf("failed to insert file %s: %w", file.RelativePath, err)
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// printProgress prints current processing statistics
func (p *ResumableProcessor) printProgress() {
	elapsed := time.Since(p.stats.StartTime)

	var completedJobs, totalJobs, totalFiles int64
	p.db.QueryRow("SELECT COUNT(*) FROM processing_jobs WHERE status = 'completed'").Scan(&completedJobs)
	p.db.QueryRow("SELECT COUNT(*) FROM processing_jobs").Scan(&totalJobs)
	p.db.QueryRow("SELECT COUNT(*) FROM processed_files").Scan(&totalFiles)

	rate := float64(p.stats.FilesProcessed) / elapsed.Seconds()
	mbProcessed := float64(p.stats.BytesProcessed) / (1024 * 1024)

	fmt.Printf("\n📊 PROGRESS REPORT\n")
	fmt.Printf("⏱️  Elapsed: %v\n", elapsed.Truncate(time.Second))
	fmt.Printf("📁 Jobs: %d/%d completed\n", completedJobs, totalJobs)
	fmt.Printf("📄 Files: %d processed (%.1f MB)\n", totalFiles, mbProcessed)
	fmt.Printf("🚀 Rate: %.0f files/sec\n", rate)
	fmt.Printf("💾 Last checkpoint: %v ago\n", time.Since(p.stats.LastCheckpoint).Truncate(time.Second))
}

// Run starts the resumable processing pipeline
func (p *ResumableProcessor) Run(ctx context.Context) error {
	fmt.Printf("🚀 Starting resumable processing pipeline\n")

	// Load checkpoint
	if err := p.loadCheckpoint(); err != nil {
		return fmt.Errorf("failed to load checkpoint: %w", err)
	}

	// Discover repositories
	if err := p.discoverRepositories(); err != nil {
		return fmt.Errorf("failed to discover repositories: %w", err)
	}

	// Start progress reporter
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				p.printProgress()
				p.saveCheckpoint()
			case <-ctx.Done():
				return
			}
		}
	}()

	// Main processing loop
	for {
		select {
		case <-ctx.Done():
			fmt.Printf("🛑 Processing stopped by context\n")
			return ctx.Err()
		default:
		}

		// Get pending jobs
		jobs, err := p.getPendingJobs()
		if err != nil {
			return fmt.Errorf("failed to get pending jobs: %w", err)
		}

		if len(jobs) == 0 {
			fmt.Printf("🎉 All jobs completed!\n")
			break
		}

		// Process jobs
		for _, job := range jobs {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			if err := p.processJob(job); err != nil {
				log.Printf("❌ Failed to process job %d: %v", job.ID, err)
			}

			// Save checkpoint periodically
			if time.Since(p.stats.LastCheckpoint) > 5*time.Minute {
				p.saveCheckpoint()
			}
		}
	}

	// Final checkpoint
	p.saveCheckpoint()
	p.printProgress()

	fmt.Printf("🏆 Processing pipeline completed successfully!\n")
	return nil
}

func main() {
	// Database connection from environment
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"
	}

	reposDir := os.Getenv("REPOS_DIR")
	if reposDir == "" {
		reposDir = "/app/repos"
	}

	fmt.Printf("🚀 RESUMABLE REPOSITORY PROCESSOR\n")
	fmt.Printf("💾 Database: %s\n", strings.Split(dbURL, "@")[1])
	fmt.Printf("📁 Repos: %s\n", reposDir)

	// Create processor
	processor, err := NewResumableProcessor(dbURL, reposDir)
	if err != nil {
		log.Fatalf("❌ Failed to create processor: %v", err)
	}
	defer processor.db.Close()

	// Create context with graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle graceful shutdown
	// signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	// go func() {
	// 	<-c
	// 	fmt.Printf("\n🛑 Shutdown signal received\n")
	// 	cancel()
	// }()

	// Run processor
	if err := processor.Run(ctx); err != nil && err != context.Canceled {
		log.Fatalf("❌ Processing failed: %v", err)
	}
}
