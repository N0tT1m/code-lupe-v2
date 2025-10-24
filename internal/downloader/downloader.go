package downloader

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"codelupe/internal/models"
	"codelupe/internal/quality"
	"codelupe/pkg/circuitbreaker"
)

// Downloader manages repository downloads
type Downloader struct {
	config         *Config
	qualityFilter  *quality.Filter
	gitClient      *GitClient
	storage        *Storage
	circuitBreaker *circuitbreaker.CircuitBreaker
	mu             sync.Mutex
	stats          *Stats
}

// Config holds downloader configuration
type Config struct {
	ReposDir           string
	MaxConcurrent      int
	Timeout            time.Duration
	RetryAttempts      int
	GitHubToken        string
	ElasticsearchURL   string
	PostgresConnString string
}

// Stats holds download statistics
type Stats struct {
	mu                sync.RWMutex
	TotalAttempted    int64
	TotalSucceeded    int64
	TotalFailed       int64
	TotalFiltered     int64
	AvgDownloadTimeMs float64
}

// New creates a new downloader instance
func New(config *Config) (*Downloader, error) {
	if err := validateConfig(config); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}

	// Initialize quality filter
	qualityFilter := quality.NewFilter()

	// Initialize git client
	gitClient := NewGitClient(config.GitHubToken, config.Timeout)

	// Initialize storage
	storage, err := NewStorage(config.PostgresConnString, config.ElasticsearchURL)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize storage: %w", err)
	}

	// Initialize circuit breaker
	cb := circuitbreaker.New(circuitbreaker.Config{
		MaxFailures: 5,
		Timeout:     30 * time.Second,
		OnStateChange: func(from, to circuitbreaker.State) {
			log.Printf("Downloader circuit breaker: %s -> %s", from, to)
		},
	})

	return &Downloader{
		config:         config,
		qualityFilter:  qualityFilter,
		gitClient:      gitClient,
		storage:        storage,
		circuitBreaker: cb,
		stats:          &Stats{},
	}, nil
}

// DownloadRepository downloads a single repository
func (d *Downloader) DownloadRepository(ctx context.Context, repo *models.RepoInfo) error {
	// Increment attempted count
	d.stats.mu.Lock()
	d.stats.TotalAttempted++
	d.stats.mu.Unlock()

	// Quality filtering
	result := d.qualityFilter.Evaluate(repo)
	if !result.Passed {
		d.stats.mu.Lock()
		d.stats.TotalFiltered++
		d.stats.mu.Unlock()
		return fmt.Errorf("filtered: %s", result.Reason)
	}

	// Download with circuit breaker protection
	start := time.Now()
	err := d.circuitBreaker.ExecuteContext(ctx, func(ctx context.Context) error {
		return d.gitClient.Clone(ctx, repo.URL, d.getRepoPath(repo))
	})

	duration := time.Since(start)

	if err != nil {
		d.stats.mu.Lock()
		d.stats.TotalFailed++
		d.stats.mu.Unlock()
		return fmt.Errorf("download failed: %w", err)
	}

	// Update statistics
	d.stats.mu.Lock()
	d.stats.TotalSucceeded++
	d.stats.AvgDownloadTimeMs = (d.stats.AvgDownloadTimeMs*float64(d.stats.TotalSucceeded-1) + float64(duration.Milliseconds())) / float64(d.stats.TotalSucceeded)
	d.stats.mu.Unlock()

	// Save to storage
	repo.LocalPath = d.getRepoPath(repo)
	repo.DownloadedAt = time.Now()
	if err := d.storage.SaveRepository(repo); err != nil {
		log.Printf("Failed to save repository metadata: %v", err)
	}

	return nil
}

// DownloadBatch downloads multiple repositories concurrently
func (d *Downloader) DownloadBatch(ctx context.Context, repos []*models.RepoInfo) error {
	semaphore := make(chan struct{}, d.config.MaxConcurrent)
	var wg sync.WaitGroup
	errors := make(chan error, len(repos))

	for _, repo := range repos {
		wg.Add(1)
		go func(r *models.RepoInfo) {
			defer wg.Done()

			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			if err := d.DownloadRepository(ctx, r); err != nil {
				errors <- fmt.Errorf("failed to download %s: %w", r.FullName, err)
			}
		}(repo)
	}

	wg.Wait()
	close(errors)

	// Collect errors
	var errs []error
	for err := range errors {
		errs = append(errs, err)
	}

	if len(errs) > 0 {
		return fmt.Errorf("%d downloads failed", len(errs))
	}

	return nil
}

// GetStats returns current download statistics
func (d *Downloader) GetStats() Stats {
	d.stats.mu.RLock()
	defer d.stats.mu.RUnlock()

	return Stats{
		TotalAttempted:    d.stats.TotalAttempted,
		TotalSucceeded:    d.stats.TotalSucceeded,
		TotalFailed:       d.stats.TotalFailed,
		TotalFiltered:     d.stats.TotalFiltered,
		AvgDownloadTimeMs: d.stats.AvgDownloadTimeMs,
	}
}

// Close closes all connections
func (d *Downloader) Close() error {
	return d.storage.Close()
}

// getRepoPath returns the local path for a repository
func (d *Downloader) getRepoPath(repo *models.RepoInfo) string {
	return fmt.Sprintf("%s/%s", d.config.ReposDir, repo.FullName)
}

// validateConfig validates downloader configuration
func validateConfig(config *Config) error {
	if config.ReposDir == "" {
		return fmt.Errorf("ReposDir is required")
	}
	if config.MaxConcurrent <= 0 {
		return fmt.Errorf("MaxConcurrent must be positive")
	}
	if config.Timeout <= 0 {
		return fmt.Errorf("Timeout must be positive")
	}
	return nil
}
