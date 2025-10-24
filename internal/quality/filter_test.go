package quality

import (
	"testing"

	"codelupe/internal/models"
)

func TestFilter_Evaluate_MinimumStars(t *testing.T) {
	filter := NewFilter()

	tests := []struct {
		name   string
		repo   *models.RepoInfo
		passed bool
	}{
		{
			name: "below minimum stars",
			repo: &models.RepoInfo{
				FullName: "test/repo",
				Stars:    5,
				Forks:    5,
				Language: "Go",
			},
			passed: false,
		},
		{
			name: "meets minimum stars",
			repo: &models.RepoInfo{
				FullName: "test/repo",
				Stars:    10,
				Forks:    5,
				Language: "Go",
			},
			passed: false, // Still fails on other criteria
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := filter.Evaluate(tt.repo)
			if result.Passed != tt.passed {
				t.Errorf("Expected passed=%v, got %v. Reason: %s", tt.passed, result.Passed, result.Reason)
			}
		})
	}
}

func TestFilter_Evaluate_Language(t *testing.T) {
	filter := NewFilter()

	tests := []struct {
		name     string
		language string
		passed   bool
	}{
		{"Rust is accepted", "Rust", true},
		{"Go is accepted", "Go", true},
		{"Python is accepted", "Python", true},
		{"PHP is rejected", "PHP", false},
		{"Ruby is rejected", "Ruby", false},
		{"Empty language is rejected", "", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := &models.RepoInfo{
				FullName:    "company/high-quality-lib",
				Name:        "high-quality-lib",
				Description: "A production-grade library framework",
				Stars:       150,
				Forks:       25,
				Language:    tt.language,
			}

			result := filter.Evaluate(repo)
			if result.Passed != tt.passed {
				t.Errorf("Language %s: expected passed=%v, got %v. Score: %d, Reason: %s",
					tt.language, tt.passed, result.Passed, result.Score, result.Reason)
			}
		})
	}
}

func TestFilter_Evaluate_ExcludePatterns(t *testing.T) {
	filter := NewFilter()

	tests := []struct {
		name     string
		fullName string
		desc     string
		passed   bool
	}{
		{
			name:     "tutorial in name",
			fullName: "user/rust-tutorial",
			desc:     "A tutorial for Rust",
			passed:   false,
		},
		{
			name:     "example in description",
			fullName: "user/myproject",
			desc:     "An example project for learning",
			passed:   false,
		},
		{
			name:     "homework in full name",
			fullName: "user/homework-assignment",
			desc:     "My homework",
			passed:   false,
		},
		{
			name:     "production library",
			fullName: "company/production-api",
			desc:     "Production-grade API library",
			passed:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := &models.RepoInfo{
				FullName:    tt.fullName,
				Name:        tt.fullName,
				Description: tt.desc,
				Stars:       100,
				Forks:       20,
				Language:    "Rust",
			}

			result := filter.Evaluate(repo)
			if result.Passed != tt.passed {
				t.Errorf("Expected passed=%v, got %v. Score: %d, Reason: %s",
					tt.passed, result.Passed, result.Score, result.Reason)
			}
		})
	}
}

func TestFilter_Evaluate_IncludePatterns(t *testing.T) {
	filter := NewFilter()

	// High-quality repo with include pattern should get bonus points
	repo := &models.RepoInfo{
		FullName:    "company/production-framework",
		Name:        "production-framework",
		Description: "A production-grade web framework",
		Stars:       500,
		Forks:       100,
		Language:    "Go",
		Topics:      []string{"framework", "web", "api"},
	}

	result := filter.Evaluate(repo)
	if !result.Passed {
		t.Errorf("High quality repo with include patterns should pass. Score: %d, Reason: %s",
			result.Score, result.Reason)
	}

	if result.Score < 70 {
		t.Errorf("Expected score >= 70 for high quality repo with bonuses, got %d", result.Score)
	}
}

func TestFilter_Evaluate_CompleteScenario(t *testing.T) {
	filter := NewFilter()

	// Perfect repository
	perfectRepo := &models.RepoInfo{
		FullName:    "kubernetes/kubernetes",
		Name:        "kubernetes",
		Description: "Production-grade container orchestration system",
		Stars:       100000,
		Forks:       35000,
		Language:    "Go",
		Topics:      []string{"containers", "orchestration", "cloud", "kubernetes"},
	}

	result := filter.Evaluate(perfectRepo)
	if !result.Passed {
		t.Errorf("Perfect repo should pass. Score: %d, Reason: %s", result.Score, result.Reason)
	}

	// Low quality tutorial
	tutorialRepo := &models.RepoInfo{
		FullName:    "student/go-tutorial",
		Name:        "go-tutorial",
		Description: "Learning Go programming basics",
		Stars:       5,
		Forks:       1,
		Language:    "Go",
	}

	result = filter.Evaluate(tutorialRepo)
	if result.Passed {
		t.Errorf("Tutorial repo should fail quality filter. Score: %d", result.Score)
	}
}

func TestNewFilterWithConfig(t *testing.T) {
	cfg := Config{
		MinStars:          50,
		MinForks:          10,
		MinCodeLines:      500,
		MaxBinaryPercent:  0.3,
		RequiredLanguages: []string{"Go", "Rust"},
		ExcludePatterns:   []string{"test"},
		IncludePatterns:   []string{"production"},
	}

	filter := NewFilterWithConfig(cfg)

	// Test that custom config is applied
	repo := &models.RepoInfo{
		FullName:    "company/repo",
		Name:        "repo",
		Description: "Production system",
		Stars:       40, // Below custom minimum
		Forks:       15,
		Language:    "Go",
	}

	result := filter.Evaluate(repo)
	if result.Passed {
		t.Errorf("Should fail with custom high star threshold. Score: %d", result.Score)
	}
}

func BenchmarkFilter_Evaluate(b *testing.B) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		FullName:    "company/framework",
		Name:        "framework",
		Description: "A production-grade framework",
		Stars:       100,
		Forks:       20,
		Language:    "Go",
		Topics:      []string{"framework", "production"},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		filter.Evaluate(repo)
	}
}
