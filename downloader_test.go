package main

import (
	"testing"
)

func TestQualityFilter_evaluateRepo(t *testing.T) {
	tests := []struct {
		name       string
		repo       *RepoInfo
		wantPass   bool
		minScore   int
	}{
		{
			name: "High quality Rust repo",
			repo: &RepoInfo{
				Name:     "awesome-rust-project",
				FullName: "user/awesome-rust-project",
				Stars:    150,
				Forks:    25,
				Language: "Rust",
				Topics:   []string{"framework", "library"},
			},
			wantPass: true,
			minScore: 70,
		},
		{
			name: "Low stars repo",
			repo: &RepoInfo{
				Name:     "test-project",
				FullName: "user/test-project",
				Stars:    5,
				Forks:    1,
				Language: "Python",
			},
			wantPass: false,
			minScore: 0,
		},
		{
			name: "Tutorial repo should be filtered",
			repo: &RepoInfo{
				Name:        "rust-tutorial",
				FullName:    "user/rust-tutorial",
				Stars:       50,
				Forks:       10,
				Language:    "Rust",
				Description: "A tutorial for learning Rust",
			},
			wantPass: false,
			minScore: 0,
		},
	}

	filter := NewQualityFilter()
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			passed, score, reason := filter.evaluateRepo(tt.repo)
			if passed != tt.wantPass {
				t.Errorf("evaluateRepo() passed = %v, want %v. Reason: %s, Score: %d",
					passed, tt.wantPass, reason, score)
			}
			if passed && score < tt.minScore {
				t.Errorf("evaluateRepo() score = %d, want >= %d", score, tt.minScore)
			}
		})
	}
}

func TestCleanLanguageString(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{
			name:  "Simple language",
			input: "Rust",
			want:  "Rust",
		},
		{
			name:  "Language with percentage",
			input: "Rust 80%",
			want:  "Rust",
		},
		{
			name:  "Multi-language string",
			input: "Rust 80% Python 15% Shell 5%",
			want:  "Rust",
		},
		{
			name:  "Language with whitespace",
			input: "  Go  ",
			want:  "Go",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := cleanLanguageString(tt.input)
			if got != tt.want {
				t.Errorf("cleanLanguageString() = %v, want %v", got, tt.want)
			}
		})
	}
}
