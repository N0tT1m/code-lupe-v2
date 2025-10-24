package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/elastic/go-elasticsearch/v8"
	"github.com/elastic/go-elasticsearch/v8/esapi"
	"github.com/joho/godotenv"
	"github.com/lib/pq"
	"golang.org/x/time/rate"

	_ "github.com/lib/pq"
)

type RepoDownloader struct {
	esClient      *elasticsearch.Client
	db            *sql.DB
	rateLimiter   *rate.Limiter
	downloadDir   string
	maxConcurrent int
	downloaded    map[string]bool
	processing    map[string]bool
	failed        map[string]error
	mu            sync.RWMutex
	stats         DownloadStats
	qualityFilter *QualityFilter
	httpClient    *http.Client
	githubToken   string
}

type DownloadStats struct {
	Total      int
	Downloaded int
	Failed     int
	Skipped    int
	Filtered   int
	mu         sync.RWMutex
}

type RepoInfo struct {
	FullName    string    `json:"full_name"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	URL         string    `json:"url"`
	Stars       int       `json:"stars"`
	Forks       int       `json:"forks"`
	Language    string    `json:"language"`
	Topics      []string  `json:"topics"`
	LastUpdated time.Time `json:"last_updated"`
	CrawledAt   time.Time `json:"crawled_at"`
}

type Repository struct {
	ID             string
	FullName       string
	Name           string
	Description    string
	URL            string
	CloneURL       string
	Language       string
	Stars          int
	Forks          int
	Watchers       int
	SizeKB         int
	LastUpdated    *time.Time
	CreatedAt      time.Time
	CrawledAt      time.Time
	DownloadedAt   *time.Time
	DownloadStatus string
	Topics         []string
	IsFork         bool
	IsArchived     bool
	IsPrivate      bool
	DefaultBranch  string
	OwnerLogin     string
	OwnerType      string
	LicenseName    string
	LicenseKey     string
	LocalPath      string
	ErrorMessage   string
	QualityScore   int
	CodeLines      int
	FileCount      int
}

type GitHubRepo struct {
	Language string `json:"language"`
}

type QualityFilter struct {
	minStars          int
	minForks          int
	minCodeLines      int
	maxBinaryPercent  float64
	requiredLanguages []string
	excludePatterns   []string
	includePatterns   []string
}

func NewQualityFilter() *QualityFilter {
	return &QualityFilter{
		minStars:          10,
		minForks:          3,
		minCodeLines:      100,
		maxBinaryPercent:  0.5,
		requiredLanguages: []string{"Rust", "Go", "Python", "TypeScript", "JavaScript", "Dart", "Java", "C", "C++"},
		excludePatterns: []string{
			"tutorial", "example", "demo", "test", "homework", "assignment",
			"practice", "exercise", "learning", "study", "course", "lesson",
			"template", "boilerplate", "starter", "hello-world", "getting-started",
			"playground", "sandbox", "experiment", "toy", "simple", "basic",
			"beginner", "introduction", "intro", "guide", "walkthrough",
			"duplicate", "fork", "copy", "mirror", "clone", "backup",
		},
		includePatterns: []string{
			"framework", "library", "tool", "utility", "cli", "api", "server",
			"client", "sdk", "driver", "connector", "plugin", "extension",
			"application", "app", "service", "microservice", "platform",
			"system", "engine", "compiler", "interpreter", "parser",
			"generator", "builder", "analyzer", "validator", "optimizer",
			"database", "orm", "migration", "query", "model", "schema",
			"authentication", "authorization", "security", "encryption",
			"monitoring", "logging", "testing", "deployment", "docker",
			"kubernetes", "terraform", "ansible", "ci-cd", "pipeline",
		},
	}
}

func NewRepoDownloader(downloadDir string, maxConcurrent int) (*RepoDownloader, error) {
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found: %v", err)
	}

	// Get Elasticsearch URL from environment with retry logic
	esURL := os.Getenv("ELASTICSEARCH_URL")
	if esURL == "" {
		esURL = "http://elasticsearch:9200"
	}

	log.Printf("Connecting to Elasticsearch at: %s", esURL)

	var esClient *elasticsearch.Client
	var err error

	// Retry connection with exponential backoff
	for i := 0; i < 10; i++ {
		esClient, err = elasticsearch.NewClient(elasticsearch.Config{
			Addresses:     []string{esURL},
			RetryOnStatus: []int{502, 503, 504, 429},
			MaxRetries:    5,
		})
		if err == nil {
			// Test the connection
			_, err = esClient.Info()
			if err == nil {
				log.Printf("Successfully connected to Elasticsearch")
				break
			}
		}

		waitTime := time.Duration(1<<uint(i)) * time.Second
		if waitTime > 30*time.Second {
			waitTime = 30 * time.Second
		}
		log.Printf("Elasticsearch not ready (attempt %d/10), waiting %v: %v", i+1, waitTime, err)
		time.Sleep(waitTime)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to create Elasticsearch client after retries: %w", err)
	}

	db, err := connectPostgreSQL()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to PostgreSQL: %w", err)
	}

	if err := os.MkdirAll(downloadDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create download directory: %w", err)
	}

	// Verify we can actually write to the directory
	testFile := filepath.Join(downloadDir, ".test_write")
	if err := os.WriteFile(testFile, []byte("test"), 0644); err != nil {
		return nil, fmt.Errorf("cannot write to download directory %s: %w", downloadDir, err)
	}
	os.Remove(testFile) // Clean up test file

	log.Printf("Successfully verified write access to: %s", downloadDir)

	return &RepoDownloader{
		esClient:      esClient,
		db:            db,
		rateLimiter:   rate.NewLimiter(rate.Every(500*time.Millisecond), 1),
		downloadDir:   downloadDir,
		maxConcurrent: maxConcurrent,
		downloaded:    make(map[string]bool),
		processing:    make(map[string]bool),
		failed:        make(map[string]error),
		qualityFilter: NewQualityFilter(),
		httpClient:    &http.Client{Timeout: 30 * time.Second},
		githubToken:   getEnv("GITHUB_TOKEN", ""),
	}, nil
}

func connectPostgreSQL() (*sql.DB, error) {
	host := getEnv("POSTGRES_HOST", "localhost")
	port := getEnv("POSTGRES_PORT", "5432")
	user := getEnv("POSTGRES_USER", "coding_user")
	password := getEnv("POSTGRES_PASSWORD", "coding_pass")
	dbname := getEnv("POSTGRES_DB", "coding_db")

	psqlInfo := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)

	log.Printf("Connecting to PostgreSQL at %s:%s", host, port)

	var db *sql.DB
	var err error

	// Retry connection with exponential backoff
	for i := 0; i < 10; i++ {
		db, err = sql.Open("postgres", psqlInfo)
		if err == nil {
			err = db.Ping()
			if err == nil {
				log.Println("Successfully connected to PostgreSQL database")
				return db, nil
			}
		}

		waitTime := time.Duration(1<<uint(i)) * time.Second
		if waitTime > 30*time.Second {
			waitTime = 30 * time.Second
		}
		log.Printf("PostgreSQL not ready (attempt %d/10), waiting %v: %v", i+1, waitTime, err)
		time.Sleep(waitTime)
	}

	return nil, fmt.Errorf("failed to connect to PostgreSQL after retries: %w", err)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func (qf *QualityFilter) evaluateRepo(repo *RepoInfo) (bool, int, string) {
	score := 10 // Base score for all repos
	reasons := []string{}

	if repo.Stars < qf.minStars {
		reasons = append(reasons, fmt.Sprintf("too few stars (%d < %d)", repo.Stars, qf.minStars))
		return false, score, strings.Join(reasons, "; ")
	}
	score += 10

	if repo.Forks < qf.minForks {
		reasons = append(reasons, fmt.Sprintf("too few forks (%d < %d)", repo.Forks, qf.minForks))
		return false, score, strings.Join(reasons, "; ")
	}
	score += 5

	hasRequiredLanguage := false
	for _, lang := range qf.requiredLanguages {
		if strings.EqualFold(repo.Language, lang) {
			hasRequiredLanguage = true
			score += 15
			break
		}
	}

	if !hasRequiredLanguage {
		reasons = append(reasons, fmt.Sprintf("language '%s' not in required list", repo.Language))
		return false, score, strings.Join(reasons, "; ")
	}

	repoNameLower := strings.ToLower(repo.Name)
	descLower := strings.ToLower(repo.Description)
	fullNameLower := strings.ToLower(repo.FullName)

	for _, pattern := range qf.excludePatterns {
		if strings.Contains(repoNameLower, pattern) ||
			strings.Contains(descLower, pattern) ||
			strings.Contains(fullNameLower, pattern) {
			reasons = append(reasons, fmt.Sprintf("contains excluded pattern: %s", pattern))
			return false, score, strings.Join(reasons, "; ")
		}
	}

	hasIncludePattern := false
	for _, pattern := range qf.includePatterns {
		if strings.Contains(repoNameLower, pattern) ||
			strings.Contains(descLower, pattern) ||
			strings.Contains(fullNameLower, pattern) {
			hasIncludePattern = true
			score += 10
			break
		}
	}

	for _, topic := range repo.Topics {
		topicLower := strings.ToLower(topic)
		for _, pattern := range qf.includePatterns {
			if strings.Contains(topicLower, pattern) {
				hasIncludePattern = true
				score += 5
				break
			}
		}
	}

	if repo.Stars > 100 {
		score += 20
	} else if repo.Stars > 50 {
		score += 10
	}

	if repo.Forks > 20 {
		score += 15
	} else if repo.Forks > 10 {
		score += 8
	}

	if hasIncludePattern {
		score += 15
	}

	return score >= 50, score, "passed quality check"
}

func (rd *RepoDownloader) getAllRepos() ([]*RepoInfo, error) {
	const batchSize = 5000
	var allRepos []*RepoInfo
	from := 0

	for {
		query := fmt.Sprintf(`{
			"query": {
				"match_all": {}
			},
			"_source": ["full_name", "name", "description", "url", "stars", "forks", "language", "topics", "last_updated", "crawled_at"],
			"size": %d,
			"from": %d
		}`, batchSize, from)

		req := esapi.SearchRequest{
			Index: []string{"github-coding-repos"},
			Body:  strings.NewReader(query),
		}

		res, err := req.Do(context.Background(), rd.esClient)
		if err != nil {
			return nil, err
		}
		defer res.Body.Close()

		if res.IsError() {
			return nil, fmt.Errorf("elasticsearch error: %s", res.Status())
		}

		var result struct {
			Hits struct {
				Total struct {
					Value int `json:"value"`
				} `json:"total"`
				Hits []struct {
					Source RepoInfo `json:"_source"`
				} `json:"hits"`
			} `json:"hits"`
		}

		if err := json.NewDecoder(res.Body).Decode(&result); err != nil {
			return nil, err
		}

		// Add repos from this batch
		for _, hit := range result.Hits.Hits {
			// IMPORTANT: Make a copy to avoid all pointers pointing to the same loop variable
			repoCopy := hit.Source
			// Debug: log first few repos to see what data we're getting
			if len(allRepos) < 3 {
				log.Printf("Debug repo %d: FullName=%s, Language='%s', Stars=%d",
					len(allRepos), repoCopy.FullName, repoCopy.Language, repoCopy.Stars)
			}
			allRepos = append(allRepos, &repoCopy)
		}

		currentBatchSize := len(result.Hits.Hits)
		log.Printf("Fetched batch %d-%d (%d repos) - Total so far: %d",
			from, from+currentBatchSize-1, currentBatchSize, len(allRepos))

		// If we got fewer results than requested, we've reached the end
		if currentBatchSize < batchSize {
			break
		}

		from += batchSize
	}

	rd.stats.mu.Lock()
	rd.stats.Total = len(allRepos)
	rd.stats.mu.Unlock()

	log.Printf("Found %d repositories to download", len(allRepos))
	return allRepos, nil
}

func (rd *RepoDownloader) fetchGitHubLanguage(fullName string) (string, error) {
	if rd.githubToken == "" {
		return "", nil // No token, skip API call
	}

	url := fmt.Sprintf("https://api.github.com/repos/%s", fullName)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return "", err
	}

	req.Header.Set("Authorization", "token "+rd.githubToken)
	req.Header.Set("Accept", "application/vnd.github.v3+json")
	req.Header.Set("User-Agent", "CodeLupe-Downloader/1.0")

	resp, err := rd.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", fmt.Errorf("GitHub API returned status %d", resp.StatusCode)
	}

	var githubRepo GitHubRepo
	if err := json.NewDecoder(resp.Body).Decode(&githubRepo); err != nil {
		return "", err
	}

	return githubRepo.Language, nil
}

func (rd *RepoDownloader) downloadRepo(repo *RepoInfo) error {
	// Try to fetch language info from GitHub API if missing
	if repo.Language == "" {
		if lang, err := rd.fetchGitHubLanguage(repo.FullName); err == nil && lang != "" {
			repo.Language = lang
			log.Printf("Updated language for %s: %s", repo.FullName, lang)
		}
	}

	passed, score, reason := rd.qualityFilter.evaluateRepo(repo)

	if !passed {
		rd.stats.mu.Lock()
		rd.stats.Filtered++
		rd.stats.mu.Unlock()
		log.Printf("Filtered out %s (score: %d): %s", repo.FullName, score, reason)
		return nil // Don't hit rate limiter for filtered repos
	}

	// Only apply rate limiter for repos we're actually downloading
	if err := rd.rateLimiter.Wait(context.Background()); err != nil {
		return fmt.Errorf("rate limiter error: %w", err)
	}

	repoRecord, err := rd.upsertRepository(repo, score)
	if err != nil {
		log.Printf("Failed to upsert repository %s: %v", repo.FullName, err)
	}

	return rd.performDownload(repo, repoRecord)
}

func (rd *RepoDownloader) performDownload(repo *RepoInfo, repoRecord *Repository) error {
	repoPath := filepath.Join(rd.downloadDir, repo.FullName)

	// Check if repo exists AND has content (not just an empty directory)
	if rd.isValidRepo(repoPath) {
		rd.stats.mu.Lock()
		rd.stats.Skipped++
		rd.stats.mu.Unlock()
		log.Printf("Skipping %s (already exists)", repo.FullName)

		if repoRecord != nil && repoRecord.DownloadStatus != "downloaded" {
			rd.updateDownloadStatus(repoRecord.ID, "downloaded", repoPath, "")
		}
		return nil
	}

	parentDir := filepath.Dir(repoPath)
	if err := os.MkdirAll(parentDir, 0755); err != nil {
		return fmt.Errorf("failed to create parent directory: %w", err)
	}

	cloneURL := strings.Replace(repo.URL, "https://github.com/", "https://github.com/", 1) + ".git"

	// Use authentication if available
	if rd.githubToken != "" {
		cloneURL = strings.Replace(repo.URL, "https://", fmt.Sprintf("https://token:%s@", rd.githubToken), 1) + ".git"
	}

	log.Printf("Cloning %s (★%d, %s, Score: %d)", repo.FullName, repo.Stars, repo.Language, repoRecord.QualityScore)

	if repoRecord != nil {
		rd.updateDownloadStatus(repoRecord.ID, "downloading", "", "")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	cmd := exec.CommandContext(ctx, "git", "clone", "--depth", "1", cloneURL, repoPath)
	cmd.Env = append(os.Environ(),
		"GIT_TERMINAL_PROMPT=0",
		"GIT_ASKPASS=echo",
	)

	var stderr bytes.Buffer
	cmd.Stdout = nil
	cmd.Stderr = &stderr

	log.Printf("Starting clone of %s...", repo.FullName)
	startTime := time.Now()

	// Start heartbeat goroutine to log progress
	done := make(chan bool)
	go func() {
		ticker := time.NewTicker(15 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				elapsed := time.Since(startTime)
				log.Printf("Still cloning %s... (%v elapsed)", repo.FullName, elapsed)
			}
		}
	}()

	err := cmd.Run()
	close(done) // Stop heartbeat

	if err != nil {
		elapsed := time.Since(startTime)
		log.Printf("Clone failed for %s after %v", repo.FullName, elapsed)
		errorMsg := ""
		if ctx.Err() == context.DeadlineExceeded {
			errorMsg = fmt.Sprintf("clone timeout for %s", repo.FullName)
		} else {
			stderrStr := stderr.String()
			if stderrStr != "" {
				errorMsg = fmt.Sprintf("git clone failed for %s: %v, stderr: %s", repo.FullName, err, stderrStr)
			} else {
				errorMsg = fmt.Sprintf("git clone failed for %s: %v", repo.FullName, err)
			}
		}

		// Clean up any partial download
		os.RemoveAll(repoPath)

		if repoRecord != nil {
			rd.updateDownloadStatus(repoRecord.ID, "failed", "", errorMsg)
		}

		return fmt.Errorf(errorMsg)
	}

	elapsed := time.Since(startTime)
	log.Printf("Clone completed for %s in %v", repo.FullName, elapsed)

	// Verify the clone actually succeeded and has content
	if !rd.isValidRepo(repoPath) {
		errorMsg := fmt.Sprintf("git clone appeared to succeed but repo validation failed for %s", repo.FullName)
		os.RemoveAll(repoPath) // Clean up invalid repo

		if repoRecord != nil {
			rd.updateDownloadStatus(repoRecord.ID, "failed", "", errorMsg)
		}

		return fmt.Errorf(errorMsg)
	}

	rd.collectRepoMetadata(repoPath, repoRecord)

	if repoRecord != nil {
		rd.updateDownloadStatus(repoRecord.ID, "downloaded", repoPath, "")
	}

	rd.stats.mu.Lock()
	rd.stats.Downloaded++
	rd.stats.mu.Unlock()

	log.Printf("✓ Downloaded %s (Lines: %d, Files: %d)", repo.FullName, repoRecord.CodeLines, repoRecord.FileCount)
	return nil
}

func (rd *RepoDownloader) downloadWorker(repos <-chan *RepoInfo, wg *sync.WaitGroup) {
	defer wg.Done()
	defer func() {
		if r := recover(); r != nil {
			log.Printf("❌ Worker panic recovered: %v", r)
		}
	}()

	for repo := range repos {
		log.Printf("Worker picked up repo: %s", repo.FullName)

		func() {
			defer func() {
				if r := recover(); r != nil {
					log.Printf("❌ Panic while processing %s: %v", repo.FullName, r)
					rd.stats.mu.Lock()
					rd.stats.Failed++
					rd.stats.mu.Unlock()

					// Remove from processing map
					rd.mu.Lock()
					delete(rd.processing, repo.FullName)
					rd.mu.Unlock()
				}
			}()

			// Check if already downloaded or currently being processed
			rd.mu.Lock()
			if rd.downloaded[repo.FullName] {
				rd.mu.Unlock()
				log.Printf("Skipping %s (already in downloaded map)", repo.FullName)
				return
			}
			if rd.processing[repo.FullName] {
				rd.mu.Unlock()
				log.Printf("Skipping %s (already being processed)", repo.FullName)
				return // Another worker is already processing this repo
			}
			// Mark as processing
			rd.processing[repo.FullName] = true
			rd.mu.Unlock()

			log.Printf("Processing: %s", repo.FullName)

			// Ensure we always remove from processing map when done
			defer func() {
				rd.mu.Lock()
				delete(rd.processing, repo.FullName)
				rd.mu.Unlock()
			}()

			if err := rd.downloadRepo(repo); err != nil {
				rd.mu.Lock()
				rd.failed[repo.FullName] = err
				rd.mu.Unlock()

				rd.stats.mu.Lock()
				rd.stats.Failed++
				rd.stats.mu.Unlock()

				log.Printf("✗ Failed to download %s: %v", repo.FullName, err)
			} else {
				rd.mu.Lock()
				rd.downloaded[repo.FullName] = true
				rd.mu.Unlock()
			}
		}()
	}

	log.Println("Worker finished - channel closed")
}

func (rd *RepoDownloader) printStats() {
	rd.stats.mu.RLock()
	defer rd.stats.mu.RUnlock()

	log.Printf("Progress: %d/%d downloaded, %d failed, %d skipped, %d filtered",
		rd.stats.Downloaded, rd.stats.Total, rd.stats.Failed, rd.stats.Skipped, rd.stats.Filtered)
}

func (rd *RepoDownloader) downloadAll() error {
	repos, err := rd.getAllRepos()
	if err != nil {
		return fmt.Errorf("failed to get repositories: %w", err)
	}

	repoChan := make(chan *RepoInfo, 1000)
	var wg sync.WaitGroup

	for i := 0; i < rd.maxConcurrent; i++ {
		wg.Add(1)
		go rd.downloadWorker(repoChan, &wg)
	}

	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for range ticker.C {
			rd.printStats()
		}
	}()

	// Send repos to channel in a separate goroutine to avoid blocking
	go func() {
		log.Printf("Sending %d repos to worker queue...", len(repos))
		for i, repo := range repos {
			repoChan <- repo
			if i > 0 && i%1000 == 0 {
				log.Printf("Queued %d/%d repos...", i, len(repos))
			}
		}
		log.Printf("All %d repos queued, closing channel", len(repos))
		close(repoChan)
	}()

	wg.Wait()

	rd.printStats()

	if len(rd.failed) > 0 {
		log.Printf("Failed downloads:")
		rd.mu.RLock()
		for repo, err := range rd.failed {
			log.Printf("  %s: %v", repo, err)
		}
		rd.mu.RUnlock()
	}

	return nil
}

func (rd *RepoDownloader) downloadAllContinuous(checkInterval time.Duration) error {
	log.Printf("Starting continuous download mode (checking every %v)", checkInterval)

	for {
		log.Println("========================================")
		log.Printf("Starting new download cycle at %s", time.Now().Format(time.RFC3339))

		if err := rd.downloadAll(); err != nil {
			log.Printf("⚠️  Download cycle failed: %v", err)
		} else {
			log.Println("✓ Download cycle completed successfully")
		}

		log.Printf("Waiting %v before next cycle...", checkInterval)
		time.Sleep(checkInterval)
	}
}

func (rd *RepoDownloader) retryFailed() error {
	rd.mu.RLock()
	failedRepos := make([]string, 0, len(rd.failed))
	for repo := range rd.failed {
		failedRepos = append(failedRepos, repo)
	}
	rd.mu.RUnlock()

	if len(failedRepos) == 0 {
		log.Println("No failed downloads to retry")
		return nil
	}

	log.Printf("Retrying %d failed downloads", len(failedRepos))

	query := fmt.Sprintf(`{
		"query": {
			"terms": {
				"full_name": [%s]
			}
		},
		"_source": ["full_name", "name", "description", "url", "stars", "forks", "language", "topics", "last_updated", "crawled_at"]
	}`, `"`+strings.Join(failedRepos, `", "`)+`"`)

	req := esapi.SearchRequest{
		Index: []string{"github-coding-repos"},
		Body:  strings.NewReader(query),
	}

	res, err := req.Do(context.Background(), rd.esClient)
	if err != nil {
		return err
	}
	defer res.Body.Close()

	var result struct {
		Hits struct {
			Hits []struct {
				Source RepoInfo `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&result); err != nil {
		return err
	}

	rd.mu.Lock()
	rd.failed = make(map[string]error)
	rd.mu.Unlock()

	repoChan := make(chan *RepoInfo, 10)
	var wg sync.WaitGroup

	wg.Add(1)
	go rd.downloadWorker(repoChan, &wg)

	for _, hit := range result.Hits.Hits {
		repoChan <- &hit.Source
	}
	close(repoChan)

	wg.Wait()
	return nil
}

func main() {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("❌ FATAL PANIC in main: %v", r)
			os.Exit(1)
		}
	}()

	if len(os.Args) < 2 {
		log.Fatal("Usage: go run downloader.go download|continuous|retry [download_directory] [max_concurrent]")
	}

	command := os.Args[1]
	downloadDir := getEnv("REPOS_DIR", "/app/repos")
	maxConcurrent := 3

	if len(os.Args) > 2 {
		downloadDir = os.Args[2]
	}
	if len(os.Args) > 3 {
		if n, err := fmt.Sscanf(os.Args[3], "%d", &maxConcurrent); n != 1 || err != nil {
			log.Fatal("Invalid max_concurrent value")
		}
	}

	downloader, err := NewRepoDownloader(downloadDir, maxConcurrent)
	if err != nil {
		log.Fatal("Failed to create downloader:", err)
	}
	defer downloader.Close()

	log.Printf("Starting repo downloader - Dir: %s, Max Concurrent: %d", downloadDir, maxConcurrent)

	// Test write access
	testFile := filepath.Join(downloadDir, ".write_test")
	if err := os.WriteFile(testFile, []byte("test"), 0644); err != nil {
		log.Fatalf("❌ Cannot write to directory %s: %v", downloadDir, err)
	}
	os.Remove(testFile)
	log.Printf("Successfully verified write access to: %s", downloadDir)

	switch command {
	case "download":
		if err := downloader.downloadAll(); err != nil {
			log.Printf("❌ Download failed: %v", err)
			os.Exit(1)
		}
		log.Println("Download process completed")
	case "continuous":
		// Run continuously, checking for new repos every hour
		checkInterval := 1 * time.Hour
		if err := downloader.downloadAllContinuous(checkInterval); err != nil {
			log.Printf("❌ Continuous download failed: %v", err)
			os.Exit(1)
		}
	case "retry":
		if err := downloader.retryFailed(); err != nil {
			log.Printf("❌ Retry failed: %v", err)
			os.Exit(1)
		}
		log.Println("Retry process completed")
	default:
		log.Fatal("Invalid command. Use 'download', 'continuous', or 'retry'")
	}
}

func (rd *RepoDownloader) upsertRepository(repo *RepoInfo, qualityScore int) (*Repository, error) {
	var repoRecord Repository

	parts := strings.Split(repo.FullName, "/")
	if len(parts) != 2 {
		return nil, fmt.Errorf("invalid repository full name: %s", repo.FullName)
	}

	ownerLogin := parts[0]
	repoName := parts[1]
	cloneURL := repo.URL + ".git"

	// Use PostgreSQL UPSERT (INSERT ... ON CONFLICT) to handle duplicates
	upsertQuery := `
		INSERT INTO repositories (
			full_name, name, description, url, clone_url, language, stars, forks,
			last_updated, crawled_at, download_status, topics, owner_login, quality_score
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		ON CONFLICT (full_name) DO UPDATE SET
			description = EXCLUDED.description,
			stars = EXCLUDED.stars,
			forks = EXCLUDED.forks,
			language = EXCLUDED.language,
			last_updated = EXCLUDED.last_updated,
			topics = EXCLUDED.topics,
			quality_score = EXCLUDED.quality_score
		RETURNING id, full_name, download_status, quality_score, created_at`

	topicsArray := pq.Array(repo.Topics)
	err := rd.db.QueryRow(upsertQuery,
		repo.FullName, repoName, repo.Description, repo.URL, cloneURL,
		repo.Language, repo.Stars, repo.Forks, repo.LastUpdated, repo.CrawledAt,
		"pending", topicsArray, ownerLogin, qualityScore,
	).Scan(&repoRecord.ID, &repoRecord.FullName, &repoRecord.DownloadStatus, &repoRecord.QualityScore, &repoRecord.CreatedAt)

	if err != nil {
		return nil, fmt.Errorf("failed to upsert repository: %w", err)
	}

	log.Printf("Upserted repository: %s (Quality Score: %d)", repo.FullName, qualityScore)
	return &repoRecord, nil
}

func (rd *RepoDownloader) updateDownloadStatus(repoID, status, localPath, errorMessage string) {
	var query string
	var args []interface{}

	if status == "downloaded" {
		query = `UPDATE repositories SET download_status = $1, downloaded_at = $2, local_path = $3 WHERE id = $4`
		args = []interface{}{status, time.Now(), localPath, repoID}
	} else if status == "failed" {
		query = `UPDATE repositories SET download_status = $1, error_message = $2 WHERE id = $3`
		args = []interface{}{status, errorMessage, repoID}
	} else {
		query = `UPDATE repositories SET download_status = $1 WHERE id = $2`
		args = []interface{}{status, repoID}
	}

	_, err := rd.db.Exec(query, args...)
	if err != nil {
		log.Printf("Failed to update download status for %s: %v", repoID, err)
	}
}

func (rd *RepoDownloader) collectRepoMetadata(repoPath string, repoRecord *Repository) {
	if repoRecord == nil {
		return
	}

	if sizeKB, err := rd.getDirectorySize(repoPath); err == nil {
		rd.updateRepoSize(repoRecord.ID, sizeKB)
		repoRecord.SizeKB = sizeKB
	}

	if branch, err := rd.getDefaultBranch(repoPath); err == nil {
		rd.updateDefaultBranch(repoRecord.ID, branch)
		repoRecord.DefaultBranch = branch
	}

	if codeLines, fileCount, err := rd.analyzeCodeContent(repoPath); err == nil {
		rd.updateCodeMetrics(repoRecord.ID, codeLines, fileCount)
		repoRecord.CodeLines = codeLines
		repoRecord.FileCount = fileCount
	}
}

func (rd *RepoDownloader) getDirectorySize(path string) (int, error) {
	cmd := exec.Command("du", "-sk", path)
	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}

	fields := strings.Fields(string(output))
	if len(fields) < 1 {
		return 0, fmt.Errorf("unexpected du output")
	}

	return strconv.Atoi(fields[0])
}

func (rd *RepoDownloader) getDefaultBranch(repoPath string) (string, error) {
	cmd := exec.Command("git", "-C", repoPath, "rev-parse", "--abbrev-ref", "HEAD")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(string(output)), nil
}

func (rd *RepoDownloader) analyzeCodeContent(repoPath string) (int, int, error) {
	codeExtensions := map[string]bool{
		".rs": true, ".go": true, ".py": true, ".ts": true, ".js": true,
		".dart": true, ".sql": true, ".java": true, ".cpp": true, ".c": true,
		".cs": true, ".php": true, ".rb": true, ".swift": true, ".kt": true,
		".scala": true, ".clj": true, ".hs": true, ".ml": true, ".elm": true,
		".vue": true, ".jsx": true, ".tsx": true, ".html": true, ".css": true,
		".scss": true, ".sass": true, ".less": true, ".yaml": true, ".yml": true,
		".json": true, ".xml": true, ".toml": true, ".ini": true, ".cfg": true,
	}

	totalLines := 0
	fileCount := 0

	err := filepath.Walk(repoPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			dirName := strings.ToLower(info.Name())
			if dirName == ".git" || dirName == "node_modules" || dirName == "target" ||
				dirName == "build" || dirName == "dist" || dirName == "vendor" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(info.Name()))
		if !codeExtensions[ext] {
			return nil
		}

		if lines, err := rd.countLines(path); err == nil {
			totalLines += lines
			fileCount++
		}

		return nil
	})

	return totalLines, fileCount, err
}

func (rd *RepoDownloader) countLines(filename string) (int, error) {
	cmd := exec.Command("wc", "-l", filename)
	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}

	fields := strings.Fields(string(output))
	if len(fields) < 1 {
		return 0, fmt.Errorf("unexpected wc output")
	}

	return strconv.Atoi(fields[0])
}

func (rd *RepoDownloader) updateRepoSize(repoID string, sizeKB int) {
	query := `UPDATE repositories SET size_kb = $1 WHERE id = $2`
	_, err := rd.db.Exec(query, sizeKB, repoID)
	if err != nil {
		log.Printf("Failed to update repository size: %v", err)
	}
}

func (rd *RepoDownloader) updateDefaultBranch(repoID, branch string) {
	query := `UPDATE repositories SET default_branch = $1 WHERE id = $2`
	_, err := rd.db.Exec(query, branch, repoID)
	if err != nil {
		log.Printf("Failed to update default branch: %v", err)
	}
}

func (rd *RepoDownloader) updateCodeMetrics(repoID string, codeLines, fileCount int) {
	query := `UPDATE repositories SET code_lines = $1, file_count = $2 WHERE id = $3`
	_, err := rd.db.Exec(query, codeLines, fileCount, repoID)
	if err != nil {
		log.Printf("Failed to update code metrics: %v", err)
	}
}

func (rd *RepoDownloader) isValidRepo(repoPath string) bool {
	// Check if directory exists
	if _, err := os.Stat(repoPath); os.IsNotExist(err) {
		return false
	}

	// Check if .git directory exists (indicates a valid git repo)
	gitPath := filepath.Join(repoPath, ".git")
	if _, err := os.Stat(gitPath); os.IsNotExist(err) {
		return false
	}

	// Check if directory has files (not empty)
	entries, err := os.ReadDir(repoPath)
	if err != nil || len(entries) <= 1 { // Only .git directory
		return false
	}

	return true
}

func (rd *RepoDownloader) Close() error {
	if rd.db != nil {
		return rd.db.Close()
	}
	return nil
}
