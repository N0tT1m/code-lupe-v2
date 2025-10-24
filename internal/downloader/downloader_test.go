package downloader

import (
	"testing"
	"time"

	"codelupe/internal/models"
)

func TestNew_ValidConfig(t *testing.T) {
	config := &Config{
		ReposDir:      "/tmp/test-repos",
		MaxConcurrent: 5,
		Timeout:       30 * time.Second,
	}

	downloader, err := New(config)
	if err != nil {
		t.Fatalf("New() error = %v, want nil", err)
	}

	if downloader == nil {
		t.Fatal("New() returned nil downloader")
	}

	if downloader.config.MaxConcurrent != 5 {
		t.Errorf("MaxConcurrent = %d, want 5", downloader.config.MaxConcurrent)
	}
}

func TestNew_InvalidConfig(t *testing.T) {
	tests := []struct {
		name   string
		config *Config
	}{
		{
			name: "missing repos dir",
			config: &Config{
				MaxConcurrent: 5,
				Timeout:       30 * time.Second,
			},
		},
		{
			name: "invalid max concurrent",
			config: &Config{
				ReposDir:      "/tmp/repos",
				MaxConcurrent: 0,
				Timeout:       30 * time.Second,
			},
		},
		{
			name: "invalid timeout",
			config: &Config{
				ReposDir:      "/tmp/repos",
				MaxConcurrent: 5,
				Timeout:       0,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := New(tt.config)
			if err == nil {
				t.Error("New() error = nil, want error")
			}
		})
	}
}

func TestDownloader_GetRepoPath(t *testing.T) {
	config := &Config{
		ReposDir:      "/tmp/repos",
		MaxConcurrent: 5,
		Timeout:       30 * time.Second,
	}

	d, _ := New(config)

	repo := &models.RepoInfo{
		FullName: "rust-lang/rust",
	}

	path := d.getRepoPath(repo)
	expected := "/tmp/repos/rust-lang/rust"

	if path != expected {
		t.Errorf("getRepoPath() = %q, want %q", path, expected)
	}
}

func TestDownloader_Stats(t *testing.T) {
	config := &Config{
		ReposDir:      "/tmp/repos",
		MaxConcurrent: 5,
		Timeout:       30 * time.Second,
	}

	d, _ := New(config)

	// Simulate some stats
	d.stats.mu.Lock()
	d.stats.TotalAttempted = 100
	d.stats.TotalSucceeded = 80
	d.stats.TotalFailed = 15
	d.stats.TotalFiltered = 5
	d.stats.mu.Unlock()

	stats := d.GetStats()

	if stats.TotalAttempted != 100 {
		t.Errorf("TotalAttempted = %d, want 100", stats.TotalAttempted)
	}

	if stats.TotalSucceeded != 80 {
		t.Errorf("TotalSucceeded = %d, want 80", stats.TotalSucceeded)
	}

	successRate := float64(stats.TotalSucceeded) / float64(stats.TotalAttempted)
	if successRate != 0.8 {
		t.Errorf("Success rate = %.2f, want 0.80", successRate)
	}
}

func TestValidateConfig(t *testing.T) {
	tests := []struct {
		name    string
		config  *Config
		wantErr bool
	}{
		{
			name: "valid config",
			config: &Config{
				ReposDir:      "/tmp/repos",
				MaxConcurrent: 5,
				Timeout:       30 * time.Second,
			},
			wantErr: false,
		},
		{
			name: "missing repos dir",
			config: &Config{
				MaxConcurrent: 5,
				Timeout:       30 * time.Second,
			},
			wantErr: true,
		},
		{
			name: "zero max concurrent",
			config: &Config{
				ReposDir:      "/tmp/repos",
				MaxConcurrent: 0,
				Timeout:       30 * time.Second,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateConfig(tt.config)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateConfig() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func BenchmarkDownloader_GetRepoPath(b *testing.B) {
	config := &Config{
		ReposDir:      "/tmp/repos",
		MaxConcurrent: 5,
		Timeout:       30 * time.Second,
	}

	d, _ := New(config)

	repo := &models.RepoInfo{
		FullName: "rust-lang/rust",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		d.getRepoPath(repo)
	}
}
