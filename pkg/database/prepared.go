package database

import (
	"database/sql"
	"fmt"
	"sync"
)

// PreparedStatements manages prepared SQL statements
type PreparedStatements struct {
	db         *sql.DB
	statements map[string]*sql.Stmt
	mu         sync.RWMutex
}

// NewPreparedStatements creates a new PreparedStatements manager
func NewPreparedStatements(db *sql.DB) *PreparedStatements {
	return &PreparedStatements{
		db:         db,
		statements: make(map[string]*sql.Stmt),
	}
}

// Prepare prepares a statement if it doesn't exist
func (ps *PreparedStatements) Prepare(name, query string) error {
	ps.mu.Lock()
	defer ps.mu.Unlock()

	if _, exists := ps.statements[name]; exists {
		return nil // Already prepared
	}

	stmt, err := ps.db.Prepare(query)
	if err != nil {
		return fmt.Errorf("failed to prepare statement %s: %w", name, err)
	}

	ps.statements[name] = stmt
	return nil
}

// Get retrieves a prepared statement
func (ps *PreparedStatements) Get(name string) (*sql.Stmt, error) {
	ps.mu.RLock()
	defer ps.mu.RUnlock()

	stmt, exists := ps.statements[name]
	if !exists {
		return nil, fmt.Errorf("statement %s not found", name)
	}

	return stmt, nil
}

// Close closes all prepared statements
func (ps *PreparedStatements) Close() error {
	ps.mu.Lock()
	defer ps.mu.Unlock()

	var errs []error
	for name, stmt := range ps.statements {
		if err := stmt.Close(); err != nil {
			errs = append(errs, fmt.Errorf("failed to close statement %s: %w", name, err))
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("errors closing statements: %v", errs)
	}

	return nil
}

// Common prepared statement queries
const (
	QueryFetchNewFiles = `
		SELECT id, content, language, quality_score, file_path
		FROM processed_files
		WHERE id > $1
		  AND quality_score >= $2
		  AND LENGTH(content) BETWEEN $3 AND $4
		ORDER BY quality_score DESC, id ASC
		LIMIT $5
	`

	QueryCountNewFiles = `
		SELECT COUNT(*)
		FROM processed_files
		WHERE id > $1
		  AND quality_score >= $2
		  AND LENGTH(content) BETWEEN $3 AND $4
	`

	QueryInsertFile = `
		INSERT INTO processed_files
		(job_id, file_path, relative_path, content, language, lines, size, hash, repo_name, quality_score)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (hash) DO NOTHING
	`

	QueryUpdateRepoStatus = `
		UPDATE repositories
		SET download_status = $1, downloaded_at = $2, local_path = $3
		WHERE id = $4
	`
)

// InitCommonStatements initializes commonly used prepared statements
func (ps *PreparedStatements) InitCommonStatements() error {
	statements := map[string]string{
		"fetch_new_files":     QueryFetchNewFiles,
		"count_new_files":     QueryCountNewFiles,
		"insert_file":         QueryInsertFile,
		"update_repo_status":  QueryUpdateRepoStatus,
	}

	for name, query := range statements {
		if err := ps.Prepare(name, query); err != nil {
			return err
		}
	}

	return nil
}
