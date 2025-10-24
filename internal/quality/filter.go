package quality

import (
	"fmt"
	"strings"

	"codelupe/internal/models"
)

// Filter provides quality filtering for repositories
type Filter struct {
	minStars          int
	minForks          int
	minCodeLines      int
	maxBinaryPercent  float64
	requiredLanguages []string
	excludePatterns   []string
	includePatterns   []string
}

// Config holds quality filter configuration
type Config struct {
	MinStars          int
	MinForks          int
	MinCodeLines      int
	MaxBinaryPercent  float64
	RequiredLanguages []string
	ExcludePatterns   []string
	IncludePatterns   []string
}

// NewFilter creates a new quality filter with default settings
func NewFilter() *Filter {
	return &Filter{
		minStars:          10,
		minForks:          3,
		minCodeLines:      100,
		maxBinaryPercent:  0.5,
		requiredLanguages: []string{"Rust", "Go", "Python", "TypeScript", "JavaScript", "Dart", "Java", "C", "C++"},
		excludePatterns: []string{
			"tutorial", "example", "demo", "test", "homework", "assignment",
			"practice", "exercise", "learning", "study", "course", "lesson",
			"template", "boilerplate", "starter", "hello-world", "getting-started",
			"playground", "sandbox", "experiment", "toy", "simple", "basic",
			"beginner", "introduction", "intro", "guide", "walkthrough",
			"duplicate", "fork", "copy", "mirror", "clone", "backup",
		},
		includePatterns: []string{
			"framework", "library", "tool", "utility", "cli", "api", "server",
			"client", "sdk", "driver", "connector", "plugin", "extension",
			"application", "app", "service", "microservice", "platform",
			"system", "engine", "compiler", "interpreter", "parser",
			"generator", "builder", "analyzer", "validator", "optimizer",
			"database", "orm", "migration", "query", "model", "schema",
			"authentication", "authorization", "security", "encryption",
			"monitoring", "logging", "testing", "deployment", "docker",
			"kubernetes", "terraform", "ansible", "ci-cd", "pipeline",
		},
	}
}

// NewFilterWithConfig creates a filter with custom configuration
func NewFilterWithConfig(cfg Config) *Filter {
	return &Filter{
		minStars:          cfg.MinStars,
		minForks:          cfg.MinForks,
		minCodeLines:      cfg.MinCodeLines,
		maxBinaryPercent:  cfg.MaxBinaryPercent,
		requiredLanguages: cfg.RequiredLanguages,
		excludePatterns:   cfg.ExcludePatterns,
		includePatterns:   cfg.IncludePatterns,
	}
}

// EvaluationResult holds the result of repository evaluation
type EvaluationResult struct {
	Passed bool
	Score  int
	Reason string
}

// Evaluate checks if a repository meets quality standards
func (f *Filter) Evaluate(repo *models.RepoInfo) EvaluationResult {
	score := 10 // Base score
	reasons := []string{}

	// Check minimum stars
	if repo.Stars < f.minStars {
		return EvaluationResult{
			Passed: false,
			Score:  score,
			Reason: fmt.Sprintf("too few stars (%d < %d)", repo.Stars, f.minStars),
		}
	}
	score += 10

	// Check minimum forks
	if repo.Forks < f.minForks {
		return EvaluationResult{
			Passed: false,
			Score:  score,
			Reason: fmt.Sprintf("too few forks (%d < %d)", repo.Forks, f.minForks),
		}
	}
	score += 5

	// Check language
	hasRequiredLanguage := false
	for _, lang := range f.requiredLanguages {
		if strings.EqualFold(repo.Language, lang) {
			hasRequiredLanguage = true
			score += 15
			break
		}
	}

	if !hasRequiredLanguage {
		return EvaluationResult{
			Passed: false,
			Score:  score,
			Reason: fmt.Sprintf("language '%s' not in required list", repo.Language),
		}
	}

	repoNameLower := strings.ToLower(repo.Name)
	descLower := strings.ToLower(repo.Description)
	fullNameLower := strings.ToLower(repo.FullName)

	// Check exclude patterns
	for _, pattern := range f.excludePatterns {
		if strings.Contains(repoNameLower, pattern) ||
			strings.Contains(descLower, pattern) ||
			strings.Contains(fullNameLower, pattern) {
			return EvaluationResult{
				Passed: false,
				Score:  score,
				Reason: fmt.Sprintf("contains excluded pattern: %s", pattern),
			}
		}
	}

	// Check include patterns
	hasIncludePattern := false
	for _, pattern := range f.includePatterns {
		if strings.Contains(repoNameLower, pattern) ||
			strings.Contains(descLower, pattern) ||
			strings.Contains(fullNameLower, pattern) {
			hasIncludePattern = true
			score += 10
			break
		}
	}

	// Check topics for include patterns
	for _, topic := range repo.Topics {
		topicLower := strings.ToLower(topic)
		for _, pattern := range f.includePatterns {
			if strings.Contains(topicLower, pattern) {
				hasIncludePattern = true
				score += 5
				break
			}
		}
	}

	// Bonus points for popularity
	if repo.Stars > 100 {
		score += 20
	} else if repo.Stars > 50 {
		score += 10
	}

	if repo.Forks > 20 {
		score += 15
	} else if repo.Forks > 10 {
		score += 8
	}

	if hasIncludePattern {
		score += 15
	}

	passed := score >= 50
	reason := "passed quality check"
	if !passed {
		reason = strings.Join(reasons, "; ")
	}

	return EvaluationResult{
		Passed: passed,
		Score:  score,
		Reason: reason,
	}
}
