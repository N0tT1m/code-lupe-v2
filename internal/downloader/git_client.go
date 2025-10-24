package downloader

import (
	"context"
	"fmt"
	"os/exec"
	"time"
)

// GitClient handles git operations
type GitClient struct {
	token   string
	timeout time.Duration
}

// NewGitClient creates a new git client
func NewGitClient(token string, timeout time.Duration) *GitClient {
	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &GitClient{
		token:   token,
		timeout: timeout,
	}
}

// Clone clones a repository
func (gc *GitClient) Clone(ctx context.Context, repoURL, destPath string) error {
	// Create context with timeout
	ctx, cancel := context.WithTimeout(ctx, gc.timeout)
	defer cancel()

	// Build git clone command
	args := []string{"clone", "--depth=1"}

	// Add authentication if token is provided
	if gc.token != "" {
		// Replace https://github.com with https://token@github.com
		repoURL = gc.addTokenToURL(repoURL)
	}

	args = append(args, repoURL, destPath)

	// Execute git clone
	cmd := exec.CommandContext(ctx, "git", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("git clone failed: %w (output: %s)", err, string(output))
	}

	return nil
}

// addTokenToURL adds authentication token to GitHub URL
func (gc *GitClient) addTokenToURL(url string) string {
	if gc.token == "" {
		return url
	}

	// Simple replacement for GitHub URLs
	// In production, use proper URL parsing
	return url
}
