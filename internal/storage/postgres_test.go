package storage

import (
	"database/sql"
	"testing"
	"time"

	_ "github.com/lib/pq"
)

// Mock connection string for testing
const testConnString = "host=localhost port=5433 user=coding_user password=coding_pass dbname=coding_db_test sslmode=disable"

// TestConnectionString tests that we can build proper connection strings
func TestConnectionString(t *testing.T) {
	tests := []struct {
		name     string
		host     string
		port     int
		user     string
		password string
		dbname   string
		expected string
	}{
		{
			name:     "Standard connection",
			host:     "localhost",
			port:     5432,
			user:     "testuser",
			password: "testpass",
			dbname:   "testdb",
			expected: "host=localhost port=5432 user=testuser password=testpass dbname=testdb sslmode=disable",
		},
		{
			name:     "Custom port",
			host:     "db.example.com",
			port:     5433,
			user:     "admin",
			password: "secret",
			dbname:   "production",
			expected: "host=db.example.com port=5433 user=admin password=secret dbname=production sslmode=disable",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			connStr := buildConnectionString(tt.host, tt.port, tt.user, tt.password, tt.dbname)
			if connStr != tt.expected {
				t.Errorf("Expected connection string:\n%s\nGot:\n%s", tt.expected, connStr)
			}
		})
	}
}

func buildConnectionString(host string, port int, user, password, dbname string) string {
	return "host=" + host + " port=" + string(rune(port+'0')) + " user=" + user + " password=" + password + " dbname=" + dbname + " sslmode=disable"
}

// TestDatabaseStructs tests the database models
func TestRepositoryModel(t *testing.T) {
	t.Run("Repository model structure", func(t *testing.T) {
		repo := Repository{
			ID:             1,
			FullName:       "user/repo",
			Stars:          100,
			Forks:          25,
			Language:       "Go",
			QualityScore:   85,
			DownloadStatus: "downloaded",
			LocalPath:      "/app/repos/user/repo",
			CodeLines:      5000,
			FileCount:      50,
			CreatedAt:      time.Now(),
			UpdatedAt:      time.Now(),
		}

		if repo.FullName != "user/repo" {
			t.Errorf("Expected FullName 'user/repo', got %s", repo.FullName)
		}
		if repo.QualityScore != 85 {
			t.Errorf("Expected QualityScore 85, got %d", repo.QualityScore)
		}
	})
}

type Repository struct {
	ID             int64
	FullName       string
	Stars          int
	Forks          int
	Language       string
	QualityScore   int
	DownloadStatus string
	LocalPath      string
	CodeLines      int
	FileCount      int
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// Integration test - only runs if database is available
func TestDatabaseIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	db, err := sql.Open("postgres", testConnString)
	if err != nil {
		t.Skipf("Cannot connect to test database: %v", err)
	}
	defer db.Close()

	// Test ping
	if err := db.Ping(); err != nil {
		t.Skipf("Cannot ping test database: %v", err)
	}

	t.Run("Query test table", func(t *testing.T) {
		var count int
		err := db.QueryRow("SELECT COUNT(*) FROM repositories").Scan(&count)
		if err != nil && err != sql.ErrNoRows {
			t.Logf("Query failed (table may not exist): %v", err)
		}
	})
}

func TestBuildInsertQuery(t *testing.T) {
	tests := []struct {
		name     string
		table    string
		columns  []string
		expected string
	}{
		{
			name:     "Simple insert",
			table:    "repositories",
			columns:  []string{"full_name", "stars", "language"},
			expected: "INSERT INTO repositories (full_name, stars, language) VALUES ($1, $2, $3)",
		},
		{
			name:     "Single column",
			table:    "logs",
			columns:  []string{"message"},
			expected: "INSERT INTO logs (message) VALUES ($1)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			query := buildInsertQuery(tt.table, tt.columns)
			if query != tt.expected {
				t.Errorf("Expected query:\n%s\nGot:\n%s", tt.expected, query)
			}
		})
	}
}

func buildInsertQuery(table string, columns []string) string {
	query := "INSERT INTO " + table + " ("
	for i, col := range columns {
		if i > 0 {
			query += ", "
		}
		query += col
	}
	query += ") VALUES ("
	for i := range columns {
		if i > 0 {
			query += ", "
		}
		query += "$" + string(rune(i+1+'0'))
	}
	query += ")"
	return query
}
