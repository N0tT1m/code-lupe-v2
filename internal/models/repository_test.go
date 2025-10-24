package models

import (
	"testing"
	"time"
)

func TestRepoInfo_Validation(t *testing.T) {
	tests := []struct {
		name    string
		repo    *RepoInfo
		wantErr bool
	}{
		{
			name: "valid repository",
			repo: &RepoInfo{
				FullName:    "rust-lang/rust",
				Name:        "rust",
				URL:         "https://github.com/rust-lang/rust",
				Language:    "Rust",
				Stars:       50000,
				Forks:       10000,
				Description: "Empowering everyone to build reliable and efficient software.",
			},
			wantErr: false,
		},
		{
			name: "missing full name",
			repo: &RepoInfo{
				Name:     "rust",
				Language: "Rust",
				Stars:    1000,
			},
			wantErr: true,
		},
		{
			name: "negative stars",
			repo: &RepoInfo{
				FullName: "user/repo",
				Name:     "repo",
				Stars:    -1,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.repo.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestRepoInfo_QualityScore(t *testing.T) {
	repo := &RepoInfo{
		FullName:    "awesome/library",
		Name:        "library",
		Language:    "Go",
		Stars:       1000,
		Forks:       200,
		Description: "A production-ready framework for building APIs",
		Topics:      []string{"api", "framework", "go"},
	}

	score := repo.CalculateQualityScore()

	if score < 50 || score > 100 {
		t.Errorf("CalculateQualityScore() = %d, want between 50 and 100", score)
	}
}

func TestRepoInfo_IsHighQuality(t *testing.T) {
	tests := []struct {
		name string
		repo *RepoInfo
		want bool
	}{
		{
			name: "high quality repo",
			repo: &RepoInfo{
				FullName:    "test/repo",
				Stars:       5000,
				Forks:       500,
				Description: "A production-ready framework for building APIs",
			},
			want: true,
		},
		{
			name: "low quality repo",
			repo: &RepoInfo{
				FullName: "test/repo",
				Stars:    10,
				Forks:    2,
			},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.repo.IsHighQuality()
			if got != tt.want {
				t.Errorf("IsHighQuality() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestRepoInfo_AgeInDays(t *testing.T) {
	now := time.Now()
	repo := &RepoInfo{
		CrawledAt: now.Add(-30 * 24 * time.Hour),
	}

	age := repo.AgeInDays()
	if age < 29 || age > 31 {
		t.Errorf("AgeInDays() = %d, want approximately 30", age)
	}
}

func TestRepoInfo_AgeInDays_Zero(t *testing.T) {
	repo := &RepoInfo{}

	age := repo.AgeInDays()
	if age != 0 {
		t.Errorf("AgeInDays() = %d, want 0 for zero time", age)
	}
}
