package secrets

import (
	"fmt"
	"os"
	"strings"
)

// ReadSecret reads a secret from either a file (Docker secret) or environment variable
// It first tries the _FILE suffix (Docker secret), then falls back to the env var itself
func ReadSecret(envVar string) (string, error) {
	// Try Docker secret file first
	fileEnvVar := envVar + "_FILE"
	if secretFile := os.Getenv(fileEnvVar); secretFile != "" {
		content, err := os.ReadFile(secretFile)
		if err != nil {
			return "", fmt.Errorf("failed to read secret file %s: %w", secretFile, err)
		}
		return strings.TrimSpace(string(content)), nil
	}

	// Fall back to direct environment variable
	if value := os.Getenv(envVar); value != "" {
		return value, nil
	}

	return "", fmt.Errorf("secret not found: %s (tried both %s and %s)", envVar, fileEnvVar, envVar)
}

// ReadSecretOrDefault reads a secret with a default fallback value
func ReadSecretOrDefault(envVar, defaultValue string) string {
	value, err := ReadSecret(envVar)
	if err != nil {
		return defaultValue
	}
	return value
}

// MustReadSecret reads a secret and panics if it fails (use for required secrets)
func MustReadSecret(envVar string) string {
	value, err := ReadSecret(envVar)
	if err != nil {
		panic(fmt.Sprintf("required secret not found: %s", envVar))
	}
	return value
}

// DatabaseConfig holds database connection configuration
type DatabaseConfig struct {
	Host     string
	Port     string
	Database string
	User     string
	Password string
}

// LoadDatabaseConfig loads database configuration from secrets/env vars
func LoadDatabaseConfig() (*DatabaseConfig, error) {
	config := &DatabaseConfig{
		Host:     os.Getenv("POSTGRES_HOST"),
		Port:     os.Getenv("POSTGRES_PORT"),
		Database: os.Getenv("POSTGRES_DB"),
	}

	// Set defaults
	if config.Host == "" {
		config.Host = "localhost"
	}
	if config.Port == "" {
		config.Port = "5432"
	}
	if config.Database == "" {
		config.Database = "coding_db"
	}

	// Load user and password from secrets
	user, err := ReadSecret("POSTGRES_USER")
	if err != nil {
		return nil, fmt.Errorf("failed to load database user: %w", err)
	}
	config.User = user

	password, err := ReadSecret("POSTGRES_PASSWORD")
	if err != nil {
		return nil, fmt.Errorf("failed to load database password: %w", err)
	}
	config.Password = password

	return config, nil
}

// ConnectionString builds a PostgreSQL connection string
func (c *DatabaseConfig) ConnectionString() string {
	return fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		c.Host, c.Port, c.User, c.Password, c.Database,
	)
}

// GitHubConfig holds GitHub API configuration
type GitHubConfig struct {
	Token  string
	Tokens []string // Multiple tokens for rotation
}

// LoadGitHubConfig loads GitHub configuration from secrets
func LoadGitHubConfig() (*GitHubConfig, error) {
	token, err := ReadSecret("GITHUB_TOKEN")
	if err != nil {
		return nil, fmt.Errorf("failed to load GitHub token: %w", err)
	}

	config := &GitHubConfig{
		Token: token,
	}

	// Try to load multiple tokens if available
	if tokensStr, err := ReadSecret("GITHUB_TOKENS"); err == nil {
		config.Tokens = strings.Split(tokensStr, ",")
		for i := range config.Tokens {
			config.Tokens[i] = strings.TrimSpace(config.Tokens[i])
		}
	}

	return config, nil
}
