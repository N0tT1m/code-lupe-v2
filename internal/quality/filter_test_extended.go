package quality

import (
	"testing"

	"codelupe/internal/models"
)

func TestNewFilter(t *testing.T) {
	filter := NewFilter()

	if filter.minStars != 10 {
		t.Errorf("Expected minStars to be 10, got %d", filter.minStars)
	}
	if filter.minForks != 3 {
		t.Errorf("Expected minForks to be 3, got %d", filter.minForks)
	}
	if filter.minCodeLines != 100 {
		t.Errorf("Expected minCodeLines to be 100, got %d", filter.minCodeLines)
	}
}

func TestNewFilterWithConfig(t *testing.T) {
	config := Config{
		MinStars:          20,
		MinForks:          5,
		MinCodeLines:      200,
		MaxBinaryPercent:  0.3,
		RequiredLanguages: []string{"Go", "Rust"},
		ExcludePatterns:   []string{"test", "demo"},
		IncludePatterns:   []string{"api", "library"},
	}

	filter := NewFilterWithConfig(config)

	if filter.minStars != 20 {
		t.Errorf("Expected minStars to be 20, got %d", filter.minStars)
	}
	if filter.minForks != 5 {
		t.Errorf("Expected minForks to be 5, got %d", filter.minForks)
	}
	if len(filter.requiredLanguages) != 2 {
		t.Errorf("Expected 2 required languages, got %d", len(filter.requiredLanguages))
	}
}

func TestEvaluate_TooFewStars(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "test-repo",
		FullName:    "user/test-repo",
		Description: "A framework for testing",
		Language:    "Go",
		Stars:       5, // Below minimum of 10
		Forks:       10,
		Topics:      []string{"framework"},
	}

	result := filter.Evaluate(repo)

	if result.Passed {
		t.Error("Expected evaluation to fail due to too few stars")
	}
	if result.Reason != "too few stars (5 < 10)" {
		t.Errorf("Unexpected reason: %s", result.Reason)
	}
}

func TestEvaluate_TooFewForks(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "test-repo",
		FullName:    "user/test-repo",
		Description: "A framework for testing",
		Language:    "Go",
		Stars:       15,
		Forks:       2, // Below minimum of 3
		Topics:      []string{"framework"},
	}

	result := filter.Evaluate(repo)

	if result.Passed {
		t.Error("Expected evaluation to fail due to too few forks")
	}
	if result.Reason != "too few forks (2 < 3)" {
		t.Errorf("Unexpected reason: %s", result.Reason)
	}
}

func TestEvaluate_WrongLanguage(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "test-repo",
		FullName:    "user/test-repo",
		Description: "A framework for testing",
		Language:    "PHP", // Not in required languages
		Stars:       20,
		Forks:       5,
		Topics:      []string{"framework"},
	}

	result := filter.Evaluate(repo)

	if result.Passed {
		t.Error("Expected evaluation to fail due to wrong language")
	}
	if result.Reason != "language 'PHP' not in required list" {
		t.Errorf("Unexpected reason: %s", result.Reason)
	}
}

func TestEvaluate_ExcludePattern(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "tutorial-repo", // Contains "tutorial" - excluded pattern
		FullName:    "user/tutorial-repo",
		Description: "A framework for testing",
		Language:    "Go",
		Stars:       20,
		Forks:       5,
		Topics:      []string{"framework"},
	}

	result := filter.Evaluate(repo)

	if result.Passed {
		t.Error("Expected evaluation to fail due to excluded pattern")
	}
	if result.Reason != "contains excluded pattern: tutorial" {
		t.Errorf("Unexpected reason: %s", result.Reason)
	}
}

func TestEvaluate_Success(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "awesome-framework",
		FullName:    "user/awesome-framework",
		Description: "A production-ready framework",
		Language:    "Rust",
		Stars:       150,
		Forks:       25,
		Topics:      []string{"framework", "library"},
	}

	result := filter.Evaluate(repo)

	if !result.Passed {
		t.Errorf("Expected evaluation to pass, but failed with reason: %s", result.Reason)
	}
	if result.Score < 50 {
		t.Errorf("Expected score >= 50, got %d", result.Score)
	}
}

func TestEvaluate_HighQualityRepo(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "production-api",
		FullName:    "bigcompany/production-api",
		Description: "Enterprise-grade API framework with microservices support",
		Language:    "Go",
		Stars:       5000,
		Forks:       500,
		Topics:      []string{"api", "framework", "microservices"},
	}

	result := filter.Evaluate(repo)

	if !result.Passed {
		t.Errorf("Expected evaluation to pass, but failed with reason: %s", result.Reason)
	}

	// High quality repo should score very well
	if result.Score < 80 {
		t.Errorf("Expected high score for quality repo, got %d", result.Score)
	}
}

func TestEvaluate_EdgeCase_MinimumPassingScore(t *testing.T) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "basic-library",
		FullName:    "user/basic-library",
		Description: "A simple library",
		Language:    "Python",
		Stars:       10,                  // Minimum
		Forks:       3,                   // Minimum
		Topics:      []string{"library"}, // Include pattern
	}

	result := filter.Evaluate(repo)

	if !result.Passed {
		t.Errorf("Expected evaluation to pass with minimum requirements, failed with: %s", result.Reason)
	}
}

func BenchmarkEvaluate(b *testing.B) {
	filter := NewFilter()
	repo := &models.RepoInfo{
		Name:        "test-framework",
		FullName:    "user/test-framework",
		Description: "A comprehensive testing framework for Go applications",
		Language:    "Go",
		Stars:       1000,
		Forks:       100,
		Topics:      []string{"testing", "framework", "tool"},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		filter.Evaluate(repo)
	}
}
