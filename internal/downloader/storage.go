package downloader

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"

	"codelupe/internal/models"

	"github.com/elastic/go-elasticsearch/v8"
	_ "github.com/lib/pq"
)

// Storage handles persistence operations
type Storage struct {
	db       *sql.DB
	esClient *elasticsearch.Client
}

// NewStorage creates a new storage instance
func NewStorage(postgresConnString, elasticsearchURL string) (*Storage, error) {
	// Connect to PostgreSQL
	db, err := sql.Open("postgres", postgresConnString)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to PostgreSQL: %w", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping PostgreSQL: %w", err)
	}

	// Connect to Elasticsearch
	esClient, err := elasticsearch.NewClient(elasticsearch.Config{
		Addresses: []string{elasticsearchURL},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create Elasticsearch client: %w", err)
	}

	return &Storage{
		db:       db,
		esClient: esClient,
	}, nil
}

// SaveRepository saves repository metadata to database
func (s *Storage) SaveRepository(repo *models.RepoInfo) error {
	query := `
		INSERT INTO repositories (
			full_name, stars, forks, language, description,
			quality_score, local_path, download_status, downloaded_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (full_name) DO UPDATE SET
			local_path = EXCLUDED.local_path,
			download_status = EXCLUDED.download_status,
			downloaded_at = EXCLUDED.downloaded_at
	`

	_, err := s.db.Exec(
		query,
		repo.FullName,
		repo.Stars,
		repo.Forks,
		repo.Language,
		repo.Description,
		repo.QualityScore,
		repo.LocalPath,
		"downloaded",
		repo.DownloadedAt,
	)

	return err
}

// GetPendingRepositories fetches repositories pending download
func (s *Storage) GetPendingRepositories(limit int) ([]*models.RepoInfo, error) {
	query := `
		SELECT full_name, url, stars, forks, language, description
		FROM repositories
		WHERE download_status IS NULL OR download_status = 'pending'
		ORDER BY stars DESC
		LIMIT $1
	`

	rows, err := s.db.Query(query, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var repos []*models.RepoInfo
	for rows.Next() {
		repo := &models.RepoInfo{}
		err := rows.Scan(
			&repo.FullName,
			&repo.URL,
			&repo.Stars,
			&repo.Forks,
			&repo.Language,
			&repo.Description,
		)
		if err != nil {
			return nil, err
		}
		repos = append(repos, repo)
	}

	return repos, nil
}

// IndexToElasticsearch indexes repository to Elasticsearch
func (s *Storage) IndexToElasticsearch(repo *models.RepoInfo) error {
	data, err := json.Marshal(repo)
	if err != nil {
		return err
	}

	docID := strings.ReplaceAll(repo.FullName, "/", "-")

	_, err = s.esClient.Index(
		"github-coding-repos",
		strings.NewReader(string(data)),
		s.esClient.Index.WithDocumentID(docID),
		s.esClient.Index.WithContext(context.Background()),
	)

	return err
}

// Close closes all connections
func (s *Storage) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}
