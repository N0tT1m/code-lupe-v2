package models

import "time"

// RepoInfo represents repository information from Elasticsearch
type RepoInfo struct {
	FullName    string    `json:"full_name"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	URL         string    `json:"url"`
	Stars       int       `json:"stars"`
	Forks       int       `json:"forks"`
	Language    string    `json:"language"`
	Topics      []string  `json:"topics"`
	LastUpdated time.Time `json:"last_updated"`
	CrawledAt   time.Time `json:"crawled_at"`
}

// Repository represents a repository in the database
type Repository struct {
	ID             string
	FullName       string
	Name           string
	Description    string
	URL            string
	CloneURL       string
	Language       string
	Stars          int
	Forks          int
	Watchers       int
	SizeKB         int
	LastUpdated    *time.Time
	CreatedAt      time.Time
	CrawledAt      time.Time
	DownloadedAt   *time.Time
	DownloadStatus string
	Topics         []string
	IsFork         bool
	IsArchived     bool
	IsPrivate      bool
	DefaultBranch  string
	OwnerLogin     string
	OwnerType      string
	LicenseName    string
	LicenseKey     string
	LocalPath      string
	ErrorMessage   string
	QualityScore   int
	CodeLines      int
	FileCount      int
}

// DownloadStats tracks download statistics
type DownloadStats struct {
	Total      int
	Downloaded int
	Failed     int
	Skipped    int
	Filtered   int
}

// Validate checks if RepoInfo has required fields
func (r *RepoInfo) Validate() error {
	if r.FullName == "" {
		return ErrMissingFullName
	}
	if r.Stars < 0 {
		return ErrInvalidStars
	}
	if r.Forks < 0 {
		return ErrInvalidForks
	}
	return nil
}

// CalculateQualityScore calculates a quality score for the repository
func (r *RepoInfo) CalculateQualityScore() int {
	score := 50 // Base score

	// Stars contribution (max 25 points)
	if r.Stars >= 10000 {
		score += 25
	} else if r.Stars >= 1000 {
		score += 20
	} else if r.Stars >= 100 {
		score += 10
	}

	// Forks contribution (max 15 points)
	if r.Forks >= 1000 {
		score += 15
	} else if r.Forks >= 100 {
		score += 10
	} else if r.Forks >= 10 {
		score += 5
	}

	// Description quality (5 points)
	if len(r.Description) > 50 {
		score += 5
	}

	// Topics (5 points)
	if len(r.Topics) >= 3 {
		score += 5
	}

	// Ensure score is within bounds
	if score > 100 {
		score = 100
	}
	if score < 0 {
		score = 0
	}

	return score
}

// IsHighQuality checks if repository meets high quality criteria
func (r *RepoInfo) IsHighQuality() bool {
	return r.Stars >= 100 && r.Forks >= 10 && r.CalculateQualityScore() >= 70
}

// AgeInDays returns the age of the repository in days
func (r *RepoInfo) AgeInDays() int {
	if r.CrawledAt.IsZero() {
		return 0
	}
	return int(time.Since(r.CrawledAt).Hours() / 24)
}

// Custom errors for validation
var (
	ErrMissingFullName = &ValidationError{Field: "full_name", Message: "full_name is required"}
	ErrInvalidStars    = &ValidationError{Field: "stars", Message: "stars cannot be negative"}
	ErrInvalidForks    = &ValidationError{Field: "forks", Message: "forks cannot be negative"}
)

// ValidationError represents a validation error
type ValidationError struct {
	Field   string
	Message string
}

func (e *ValidationError) Error() string {
	return e.Field + ": " + e.Message
}
