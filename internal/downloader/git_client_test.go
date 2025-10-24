package downloader

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestNewGitClient(t *testing.T) {
	tests := []struct {
		name    string
		token   string
		timeout time.Duration
	}{
		{
			name:    "with token",
			token:   "test-token",
			timeout: 5 * time.Minute,
		},
		{
			name:    "without token",
			token:   "",
			timeout: 5 * time.Minute,
		},
		{
			name:    "custom timeout",
			token:   "token",
			timeout: 10 * time.Minute,
		},
		{
			name:    "zero timeout defaults to 5min",
			token:   "token",
			timeout: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			client := NewGitClient(tt.token, tt.timeout)

			if client == nil {
				t.Fatal("NewGitClient() returned nil")
			}

			if client.token != tt.token {
				t.Errorf("token = %q, want %q", client.token, tt.token)
			}

			expectedTimeout := tt.timeout
			if tt.timeout == 0 {
				expectedTimeout = 5 * time.Minute
			}

			if client.timeout != expectedTimeout {
				t.Errorf("timeout = %v, want %v", client.timeout, expectedTimeout)
			}
		})
	}
}

func TestGitClient_AddTokenToURL(t *testing.T) {
	tests := []struct {
		name     string
		client   *GitClient
		url      string
		expected string
	}{
		{
			name:     "no token",
			client:   &GitClient{token: ""},
			url:      "https://github.com/user/repo",
			expected: "https://github.com/user/repo",
		},
		{
			name:     "with token (not implemented yet)",
			client:   &GitClient{token: "ghp_test123"},
			url:      "https://github.com/user/repo",
			expected: "https://github.com/user/repo", // Currently returns unchanged
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tt.client.addTokenToURL(tt.url)
			if result != tt.expected {
				t.Errorf("addTokenToURL() = %q, want %q", result, tt.expected)
			}
		})
	}
}

func TestGitClient_Clone_InvalidURL(t *testing.T) {
	client := NewGitClient("", 1*time.Second)
	ctx := context.Background()

	err := client.Clone(ctx, "not-a-valid-url", "/tmp/test-repo")
	if err == nil {
		t.Error("Clone() with invalid URL should return error")
	}

	if !strings.Contains(err.Error(), "git clone failed") {
		t.Errorf("error should mention 'git clone failed', got: %v", err)
	}
}

func TestGitClient_Clone_ContextCancellation(t *testing.T) {
	client := NewGitClient("", 10*time.Minute)

	// Create a context that's already cancelled
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := client.Clone(ctx, "https://github.com/user/repo", "/tmp/test-repo")
	if err == nil {
		t.Error("Clone() with cancelled context should return error")
	}
}

func TestGitClient_Clone_Timeout(t *testing.T) {
	// This test uses a very short timeout to trigger timeout behavior
	client := NewGitClient("", 1*time.Nanosecond)
	ctx := context.Background()

	// Use a real repo URL but it should timeout immediately
	err := client.Clone(ctx, "https://github.com/torvalds/linux", "/tmp/test-linux")
	if err == nil {
		t.Error("Clone() should timeout and return error")
	}
}

func BenchmarkGitClient_AddTokenToURL(b *testing.B) {
	client := &GitClient{token: "test-token"}
	url := "https://github.com/user/repo"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		client.addTokenToURL(url)
	}
}
