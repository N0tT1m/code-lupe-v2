package errors

import (
	"database/sql"
	"encoding/json"
	"sync"
	"time"
)

// ErrorTracker tracks errors in PostgreSQL for analysis
type ErrorTracker struct {
	db *sql.DB
	mu sync.Mutex
}

// ErrorRecord represents an error record in the database
type ErrorRecord struct {
	ID        int64                  `json:"id"`
	Type      string                 `json:"type"`
	Message   string                 `json:"message"`
	Code      string                 `json:"code"`
	Context   map[string]interface{} `json:"context"`
	File      string                 `json:"file"`
	Line      int                    `json:"line"`
	Cause     string                 `json:"cause"`
	Retryable bool                   `json:"retryable"`
	Component string                 `json:"component"` // crawler, processor, trainer, etc.
	CreatedAt time.Time              `json:"created_at"`
}

// NewErrorTracker creates a new error tracker
func NewErrorTracker(db *sql.DB) (*ErrorTracker, error) {
	tracker := &ErrorTracker{db: db}

	// Initialize schema
	if err := tracker.initSchema(); err != nil {
		return nil, err
	}

	return tracker, nil
}

// initSchema creates the error tracking table
func (t *ErrorTracker) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS error_logs (
		id SERIAL PRIMARY KEY,
		type TEXT NOT NULL,
		message TEXT NOT NULL,
		code TEXT,
		context JSONB,
		file TEXT,
		line INTEGER,
		cause TEXT,
		retryable BOOLEAN DEFAULT FALSE,
		component TEXT NOT NULL,
		created_at TIMESTAMP DEFAULT NOW()
	);

	-- Indexes for querying
	CREATE INDEX IF NOT EXISTS idx_error_logs_type ON error_logs(type);
	CREATE INDEX IF NOT EXISTS idx_error_logs_component ON error_logs(component);
	CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at DESC);
	CREATE INDEX IF NOT EXISTS idx_error_logs_retryable ON error_logs(retryable);

	-- Create view for error statistics
	CREATE OR REPLACE VIEW error_stats AS
	SELECT
		component,
		type,
		COUNT(*) as count,
		COUNT(*) FILTER (WHERE retryable = TRUE) as retryable_count,
		MAX(created_at) as last_occurrence
	FROM error_logs
	WHERE created_at >= NOW() - INTERVAL '24 hours'
	GROUP BY component, type
	ORDER BY count DESC;
	`

	_, err := t.db.Exec(schema)
	return err
}

// Track records an error in the database
func (t *ErrorTracker) Track(err error, component string) error {
	if err == nil {
		return nil
	}

	t.mu.Lock()
	defer t.mu.Unlock()

	var record ErrorRecord
	record.Component = component
	record.CreatedAt = time.Now()

	// Extract information from structured error
	if structuredErr, ok := err.(*Error); ok {
		record.Type = string(structuredErr.Type)
		record.Message = structuredErr.Message
		record.Code = structuredErr.Code
		record.Context = structuredErr.Context
		record.File = structuredErr.File
		record.Line = structuredErr.Line
		record.Retryable = structuredErr.Retryable

		if structuredErr.Cause != nil {
			record.Cause = structuredErr.Cause.Error()
		}
	} else {
		// Fallback for non-structured errors
		record.Type = string(ErrorTypeSystem)
		record.Message = err.Error()
		record.Retryable = false
	}

	// Serialize context to JSON
	var contextJSON []byte
	if record.Context != nil {
		contextJSON, _ = json.Marshal(record.Context)
	}

	// Insert into database
	_, err = t.db.Exec(`
		INSERT INTO error_logs (type, message, code, context, file, line, cause, retryable, component)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`, record.Type, record.Message, record.Code, contextJSON, record.File, record.Line, record.Cause, record.Retryable, record.Component)

	return err
}

// GetRecentErrors retrieves recent errors
func (t *ErrorTracker) GetRecentErrors(limit int, component string) ([]ErrorRecord, error) {
	query := `
		SELECT id, type, message, code, context, file, line, cause, retryable, component, created_at
		FROM error_logs
		WHERE component = $1
		ORDER BY created_at DESC
		LIMIT $2
	`

	rows, err := t.db.Query(query, component, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var errors []ErrorRecord
	for rows.Next() {
		var record ErrorRecord
		var contextJSON []byte

		err := rows.Scan(
			&record.ID,
			&record.Type,
			&record.Message,
			&record.Code,
			&contextJSON,
			&record.File,
			&record.Line,
			&record.Cause,
			&record.Retryable,
			&record.Component,
			&record.CreatedAt,
		)
		if err != nil {
			continue
		}

		// Deserialize context
		if len(contextJSON) > 0 {
			json.Unmarshal(contextJSON, &record.Context)
		}

		errors = append(errors, record)
	}

	return errors, nil
}

// GetErrorStats returns error statistics
func (t *ErrorTracker) GetErrorStats() ([]map[string]interface{}, error) {
	rows, err := t.db.Query(`
		SELECT component, type, count, retryable_count, last_occurrence
		FROM error_stats
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var stats []map[string]interface{}
	for rows.Next() {
		var component, errType string
		var count, retryableCount int
		var lastOccurrence time.Time

		if err := rows.Scan(&component, &errType, &count, &retryableCount, &lastOccurrence); err != nil {
			continue
		}

		stats = append(stats, map[string]interface{}{
			"component":       component,
			"type":            errType,
			"count":           count,
			"retryable_count": retryableCount,
			"last_occurrence": lastOccurrence,
		})
	}

	return stats, nil
}

// CleanupOldErrors removes old error logs
func (t *ErrorTracker) CleanupOldErrors(olderThan time.Duration) (int64, error) {
	result, err := t.db.Exec(`
		DELETE FROM error_logs
		WHERE created_at < $1
	`, time.Now().Add(-olderThan))

	if err != nil {
		return 0, err
	}

	return result.RowsAffected()
}
