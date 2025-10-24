package main

import (
	"testing"
	"time"
)

func TestCleanLanguageString(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "Simple language",
			input:    "Rust",
			expected: "Rust",
		},
		{
			name:     "Language with percentage",
			input:    "Rust 80%",
			expected: "Rust",
		},
		{
			name:     "Multi-language with percentages",
			input:    "Rust 80% Python 15% Shell 5%",
			expected: "Rust",
		},
		{
			name:     "Language with newline",
			input:    "Go\nUpdated 2 days ago",
			expected: "Go",
		},
		{
			name:     "Language with trailing spaces",
			input:    "JavaScript   ",
			expected: "JavaScript",
		},
		{
			name:     "Empty string",
			input:    "",
			expected: "",
		},
		{
			name:     "Language with decimal percentage",
			input:    "TypeScript 95.5%",
			expected: "TypeScript",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := cleanLanguageString(tt.input)
			if result != tt.expected {
				t.Errorf("cleanLanguageString(%q) = %q; want %q", tt.input, result, tt.expected)
			}
		})
	}
}

func TestParseNumber(t *testing.T) {
	tests := []struct {
		name      string
		input     string
		expected  int
		expectErr bool
	}{
		{
			name:      "Simple number",
			input:     "123",
			expected:  123,
			expectErr: false,
		},
		{
			name:      "Number with comma",
			input:     "1,234",
			expected:  1234,
			expectErr: false,
		},
		{
			name:      "Number with k suffix",
			input:     "5k",
			expected:  5000,
			expectErr: false,
		},
		{
			name:      "Decimal with k suffix",
			input:     "2.5k",
			expected:  2500,
			expectErr: false,
		},
		{
			name:      "Number with m suffix",
			input:     "1.2m",
			expected:  1200000,
			expectErr: false,
		},
		{
			name:      "Empty string",
			input:     "",
			expected:  0,
			expectErr: true,
		},
		{
			name:      "Large number with commas",
			input:     "123,456,789",
			expected:  123456789,
			expectErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := parseNumber(tt.input)
			if tt.expectErr {
				if err == nil {
					t.Errorf("parseNumber(%q) expected error but got nil", tt.input)
				}
				return
			}
			if err != nil {
				t.Errorf("parseNumber(%q) unexpected error: %v", tt.input, err)
				return
			}
			if result != tt.expected {
				t.Errorf("parseNumber(%q) = %d; want %d", tt.input, result, tt.expected)
			}
		})
	}
}

func TestRepository(t *testing.T) {
	t.Run("Repository creation", func(t *testing.T) {
		now := time.Now()
		repo := &Repository{
			Name:        "test-repo",
			FullName:    "user/test-repo",
			Description: "A test repository",
			URL:         "https://github.com/user/test-repo",
			Language:    "Go",
			Stars:       100,
			Forks:       25,
			Topics:      []string{"golang", "testing"},
			CrawledAt:   now,
		}

		if repo.Name != "test-repo" {
			t.Errorf("Expected Name to be 'test-repo', got %s", repo.Name)
		}
		if repo.Stars != 100 {
			t.Errorf("Expected Stars to be 100, got %d", repo.Stars)
		}
		if len(repo.Topics) != 2 {
			t.Errorf("Expected 2 topics, got %d", len(repo.Topics))
		}
	})
}

func TestCrawlerStats(t *testing.T) {
	t.Run("CrawlerStats initialization", func(t *testing.T) {
		stats := &CrawlerStats{
			startTime:    time.Now(),
			lastReported: time.Now(),
		}

		stats.mu.Lock()
		stats.totalIndexed = 10
		stats.totalErrors = 2
		stats.termsProcessed = 5
		stats.pagesProcessed = 15
		stats.mu.Unlock()

		stats.mu.RLock()
		defer stats.mu.RUnlock()

		if stats.totalIndexed != 10 {
			t.Errorf("Expected totalIndexed to be 10, got %d", stats.totalIndexed)
		}
		if stats.totalErrors != 2 {
			t.Errorf("Expected totalErrors to be 2, got %d", stats.totalErrors)
		}
	})
}

func BenchmarkCleanLanguageString(b *testing.B) {
	testString := "Rust 80% Python 15% Shell 5%"
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		cleanLanguageString(testString)
	}
}

func BenchmarkParseNumber(b *testing.B) {
	testString := "1,234,567"
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		parseNumber(testString)
	}
}
