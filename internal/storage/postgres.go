package storage

import (
	"database/sql"
	"fmt"
	"time"

	"codelupe/internal/models"

	"github.com/lib/pq"
	_ "github.com/lib/pq"
)

// PostgresStore handles PostgreSQL database operations
type PostgresStore struct {
	db *sql.DB
}

// Config holds database configuration
type Config struct {
	Host     string
	Port     string
	User     string
	Password string
	DBName   string
}

// NewPostgresStore creates a new PostgreSQL store
func NewPostgresStore(cfg Config) (*PostgresStore, error) {
	psqlInfo := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName)

	db, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	if err = db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &PostgresStore{db: db}, nil
}

// Close closes the database connection
func (s *PostgresStore) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}

// UpsertRepository inserts or updates a repository
func (s *PostgresStore) UpsertRepository(repo *models.RepoInfo, qualityScore int) (*models.Repository, error) {
	var repoRecord models.Repository

	// Check if repo exists
	query := `SELECT id, full_name, download_status, quality_score FROM repositories WHERE full_name = $1`
	err := s.db.QueryRow(query, repo.FullName).Scan(
		&repoRecord.ID,
		&repoRecord.FullName,
		&repoRecord.DownloadStatus,
		&repoRecord.QualityScore,
	)

	if err == sql.ErrNoRows {
		// Insert new repository
		return s.insertRepository(repo, qualityScore)
	} else if err != nil {
		return nil, fmt.Errorf("failed to query repository: %w", err)
	}

	// Update existing repository
	return s.updateRepository(repo, qualityScore, &repoRecord)
}

func (s *PostgresStore) insertRepository(repo *models.RepoInfo, qualityScore int) (*models.Repository, error) {
	parts := splitFullName(repo.FullName)
	if parts == nil {
		return nil, fmt.Errorf("invalid repository full name: %s", repo.FullName)
	}

	insertQuery := `
		INSERT INTO repositories (
			full_name, name, description, url, clone_url, language, stars, forks,
			last_updated, crawled_at, download_status, topics, owner_login, quality_score
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING id, created_at`

	var repoRecord models.Repository
	topicsArray := pq.Array(repo.Topics)
	cloneURL := repo.URL + ".git"

	err := s.db.QueryRow(insertQuery,
		repo.FullName, parts.name, repo.Description, repo.URL, cloneURL,
		repo.Language, repo.Stars, repo.Forks, repo.LastUpdated, repo.CrawledAt,
		"pending", topicsArray, parts.owner, qualityScore,
	).Scan(&repoRecord.ID, &repoRecord.CreatedAt)

	if err != nil {
		return nil, fmt.Errorf("failed to insert repository: %w", err)
	}

	repoRecord.FullName = repo.FullName
	repoRecord.DownloadStatus = "pending"
	repoRecord.QualityScore = qualityScore

	return &repoRecord, nil
}

func (s *PostgresStore) updateRepository(repo *models.RepoInfo, qualityScore int, existing *models.Repository) (*models.Repository, error) {
	updateQuery := `
		UPDATE repositories
		SET description = $2, stars = $3, forks = $4, language = $5,
			last_updated = $6, topics = $7, quality_score = $8
		WHERE full_name = $1`

	topicsArray := pq.Array(repo.Topics)
	_, err := s.db.Exec(updateQuery,
		repo.FullName, repo.Description, repo.Stars, repo.Forks,
		repo.Language, repo.LastUpdated, topicsArray, qualityScore,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to update repository: %w", err)
	}

	existing.QualityScore = qualityScore
	return existing, nil
}

// UpdateDownloadStatus updates the download status of a repository
func (s *PostgresStore) UpdateDownloadStatus(repoID, status, localPath, errorMessage string) error {
	var query string
	var args []interface{}

	switch status {
	case "downloaded":
		query = `UPDATE repositories SET download_status = $1, downloaded_at = $2, local_path = $3 WHERE id = $4`
		args = []interface{}{status, time.Now(), localPath, repoID}
	case "failed":
		query = `UPDATE repositories SET download_status = $1, error_message = $2 WHERE id = $3`
		args = []interface{}{status, errorMessage, repoID}
	default:
		query = `UPDATE repositories SET download_status = $1 WHERE id = $2`
		args = []interface{}{status, repoID}
	}

	_, err := s.db.Exec(query, args...)
	if err != nil {
		return fmt.Errorf("failed to update download status: %w", err)
	}

	return nil
}

// UpdateRepoSize updates repository size
func (s *PostgresStore) UpdateRepoSize(repoID string, sizeKB int) error {
	query := `UPDATE repositories SET size_kb = $1 WHERE id = $2`
	_, err := s.db.Exec(query, sizeKB, repoID)
	if err != nil {
		return fmt.Errorf("failed to update repository size: %w", err)
	}
	return nil
}

// UpdateDefaultBranch updates repository default branch
func (s *PostgresStore) UpdateDefaultBranch(repoID, branch string) error {
	query := `UPDATE repositories SET default_branch = $1 WHERE id = $2`
	_, err := s.db.Exec(query, branch, repoID)
	if err != nil {
		return fmt.Errorf("failed to update default branch: %w", err)
	}
	return nil
}

// UpdateCodeMetrics updates code line count and file count
func (s *PostgresStore) UpdateCodeMetrics(repoID string, codeLines, fileCount int) error {
	query := `UPDATE repositories SET code_lines = $1, file_count = $2 WHERE id = $3`
	_, err := s.db.Exec(query, codeLines, fileCount, repoID)
	if err != nil {
		return fmt.Errorf("failed to update code metrics: %w", err)
	}
	return nil
}

type repoNameParts struct {
	owner string
	name  string
}

func splitFullName(fullName string) *repoNameParts {
	parts := make([]string, 0, 2)
	lastSlash := -1
	for i, c := range fullName {
		if c == '/' {
			if lastSlash >= 0 {
				return nil // More than one slash
			}
			parts = append(parts, fullName[:i])
			lastSlash = i
		}
	}
	if lastSlash < 0 || lastSlash == len(fullName)-1 {
		return nil // No slash or slash at end
	}
	parts = append(parts, fullName[lastSlash+1:])

	if len(parts) != 2 {
		return nil
	}

	return &repoNameParts{
		owner: parts[0],
		name:  parts[1],
	}
}
