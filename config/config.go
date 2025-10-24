package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

// Config represents the application configuration
type Config struct {
	GitHub       GitHubConfig      `json:"github"`
	Storage      StorageConfig     `json:"storage"`
	Performance  PerformanceConfig `json:"performance"`
	Quality      QualityConfig     `json:"quality_filters"`
	Languages    []string          `json:"target_languages"`
	Technologies []string          `json:"target_technologies"`
	Database     DatabaseConfig    `json:"database"`
	Processing   ProcessingConfig  `json:"processing"`
}

// GitHubConfig holds GitHub-related configuration
type GitHubConfig struct {
	Tokens               []string      `json:"tokens"`
	MaxRequestsPerSecond int           `json:"max_requests_per_second"`
	Timeout              time.Duration `json:"timeout_seconds"`
}

// StorageConfig holds storage-related configuration
type StorageConfig struct {
	PrimaryPath  string `json:"primary_path"`
	BackupPath   string `json:"backup_path"`
	MaxPrimaryGB int    `json:"max_primary_gb"`
	MaxBackupGB  int    `json:"max_backup_gb"`
}

// PerformanceConfig holds performance tuning parameters
type PerformanceConfig struct {
	WorkersPerToken      int `json:"workers_per_token"`
	ReposPerHourPerToken int `json:"repos_per_hour_per_token"`
	MaxRequestsPerSecond int `json:"max_requests_per_second"`
	ConcurrentClones     int `json:"concurrent_clones"`
}

// QualityConfig holds quality filtering parameters
type QualityConfig struct {
	MinStars              int `json:"min_stars"`
	MinQualityScore       int `json:"min_quality_score"`
	CloneQualityThreshold int `json:"clone_quality_threshold"`
	MaxRepoSizeKB         int `json:"max_repo_size_kb"`
	MinRecentDays         int `json:"min_recent_days"`
}

// DatabaseConfig holds database connection parameters
type DatabaseConfig struct {
	Host              string `json:"host"`
	Port              int    `json:"port"`
	Database          string `json:"database"`
	User              string `json:"user"`
	Password          string `json:"password"`
	MaxConnections    int    `json:"max_connections"`
	MinConnections    int    `json:"min_connections"`
	ConnectionTimeout int    `json:"connection_timeout_seconds"`
}

// ProcessingConfig holds file processing parameters
type ProcessingConfig struct {
	WorkerCount int   `json:"worker_count"`
	BatchSize   int   `json:"batch_size"`
	MinFileSize int64 `json:"min_file_size"`
	MaxFileSize int64 `json:"max_file_size"`
}

// LoadConfig loads configuration from file and environment variables
func LoadConfig(filepath string) (*Config, error) {
	// Read config file
	data, err := os.ReadFile(filepath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var config Config
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	// Override with environment variables
	config.applyEnvironmentOverrides()

	// Validate configuration
	if err := config.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &config, nil
}

// applyEnvironmentOverrides applies environment variable overrides
func (c *Config) applyEnvironmentOverrides() {
	// GitHub tokens from environment
	if token := os.Getenv("GITHUB_TOKEN"); token != "" {
		c.GitHub.Tokens = []string{token}
	}
	if tokens := os.Getenv("GITHUB_TOKENS"); tokens != "" {
		// Parse comma-separated tokens
		c.GitHub.Tokens = parseCommaSeparated(tokens)
	}

	// Database configuration from environment
	if host := os.Getenv("POSTGRES_HOST"); host != "" {
		c.Database.Host = host
	}
	if port := os.Getenv("POSTGRES_PORT"); port != "" {
		if p, err := parseInt(port); err == nil {
			c.Database.Port = p
		}
	}
	if user := os.Getenv("POSTGRES_USER"); user != "" {
		c.Database.User = user
	}
	if password := os.Getenv("POSTGRES_PASSWORD"); password != "" {
		c.Database.Password = password
	}
	if dbname := os.Getenv("POSTGRES_DB"); dbname != "" {
		c.Database.Database = dbname
	}

	// Storage paths from environment
	if reposDir := os.Getenv("REPOS_DIR"); reposDir != "" {
		c.Storage.PrimaryPath = reposDir
	}
}

// Validate validates the configuration
func (c *Config) Validate() error {
	// Validate GitHub config
	if len(c.GitHub.Tokens) == 0 {
		return fmt.Errorf("at least one GitHub token is required")
	}

	// Validate storage paths
	if c.Storage.PrimaryPath == "" {
		return fmt.Errorf("primary storage path is required")
	}

	// Validate performance config
	if c.Performance.ConcurrentClones < 1 {
		return fmt.Errorf("concurrent_clones must be >= 1")
	}

	// Validate quality config
	if c.Quality.MinStars < 0 {
		return fmt.Errorf("min_stars must be >= 0")
	}

	// Validate database config
	if c.Database.Host == "" {
		c.Database.Host = "localhost"
	}
	if c.Database.Port == 0 {
		c.Database.Port = 5432
	}
	if c.Database.MaxConnections == 0 {
		c.Database.MaxConnections = 10
	}
	if c.Database.MinConnections == 0 {
		c.Database.MinConnections = 1
	}

	// Validate processing config
	if c.Processing.WorkerCount == 0 {
		c.Processing.WorkerCount = 4
	}
	if c.Processing.BatchSize == 0 {
		c.Processing.BatchSize = 50
	}
	if c.Processing.MinFileSize == 0 {
		c.Processing.MinFileSize = 100
	}
	if c.Processing.MaxFileSize == 0 {
		c.Processing.MaxFileSize = 1024 * 1024 // 1MB
	}

	return nil
}

// GetDatabaseURL returns the PostgreSQL connection string
func (c *Config) GetDatabaseURL() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=disable",
		c.Database.User,
		c.Database.Password,
		c.Database.Host,
		c.Database.Port,
		c.Database.Database,
	)
}

// Helper functions
func parseCommaSeparated(s string) []string {
	var result []string
	for _, item := range strings.Split(s, ",") {
		if trimmed := strings.TrimSpace(item); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

func parseInt(s string) (int, error) {
	var i int
	_, err := fmt.Sscanf(s, "%d", &i)
	return i, err
}
