package api

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/elastic/go-elasticsearch/v8"
	"github.com/gorilla/mux"
)

func setupMockServer(t *testing.T) (*Server, sqlmock.Sqlmock) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}

	server := &Server{
		config: Config{
			Port:             "8080",
			DatabaseConnStr:  "mock",
			ElasticsearchURL: "http://localhost:9200",
			EnableCORS:       true,
		},
		router:   mux.NewRouter(),
		db:       db,
		esClient: nil, // Would need ES mock for full tests
	}

	server.setupRoutes()

	return server, mock
}

func TestNewServer(t *testing.T) {
	config := Config{
		Port:             "8080",
		DatabaseConnStr:  "test",
		ElasticsearchURL: "http://localhost:9200",
		EnableCORS:       true,
	}

	server := NewServer(config)

	if server == nil {
		t.Fatal("NewServer() returned nil")
	}

	if server.config.Port != "8080" {
		t.Errorf("Port = %s, want 8080", server.config.Port)
	}

	if server.router == nil {
		t.Error("Router was not initialized")
	}
}

func TestHandleHealth(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	// Mock database ping
	mock.ExpectPing()

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	server.handleHealth(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response["status"] != "healthy" {
		t.Errorf("status = %v, want healthy", response["status"])
	}

	if response["database"] != "ok" {
		t.Errorf("database status = %v, want ok", response["database"])
	}
}

func TestHandleHealth_DatabaseError(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	// Mock database ping failure
	mock.ExpectPing().WillReturnError(sql.ErrConnDone)

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	server.handleHealth(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusServiceUnavailable)
	}

	var response map[string]interface{}
	json.NewDecoder(w.Body).Decode(&response)

	if response["status"] != "unhealthy" {
		t.Errorf("status = %v, want unhealthy", response["status"])
	}
}

func TestHandleListRepositories(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	// Mock repository query
	rows := sqlmock.NewRows([]string{
		"id", "full_name", "name", "description", "language",
		"stars", "forks", "quality_score", "download_status",
		"created_at", "updated_at",
	}).AddRow(
		1, "rust-lang/rust", "rust", "A safe, concurrent language",
		"Rust", 50000, 10000, 95, "downloaded",
		time.Now(), time.Now(),
	)

	mock.ExpectQuery("SELECT id, full_name, name").
		WithArgs(20, 0).
		WillReturnRows(rows)

	// Mock count query
	countRows := sqlmock.NewRows([]string{"count"}).AddRow(1)
	mock.ExpectQuery("SELECT COUNT").WillReturnRows(countRows)

	req := httptest.NewRequest("GET", "/api/v1/repositories?page=1&limit=20", nil)
	w := httptest.NewRecorder()

	server.handleListRepositories(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if response["page"] != float64(1) {
		t.Errorf("page = %v, want 1", response["page"])
	}

	if response["total"] != float64(1) {
		t.Errorf("total = %v, want 1", response["total"])
	}
}

func TestHandleGetRepository(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	// Mock repository query by ID
	rows := sqlmock.NewRows([]string{
		"id", "full_name", "name", "description", "language",
		"stars", "forks", "quality_score", "download_status",
		"local_path", "created_at", "updated_at",
	}).AddRow(
		1, "rust-lang/rust", "rust", "A safe language",
		"Rust", 50000, 10000, 95, "downloaded",
		"/repos/rust-lang/rust", time.Now(), time.Now(),
	)

	mock.ExpectQuery("SELECT id, full_name").
		WithArgs("1").
		WillReturnRows(rows)

	req := httptest.NewRequest("GET", "/api/v1/repositories/1", nil)
	req = mux.SetURLVars(req, map[string]string{"id": "1"})
	w := httptest.NewRecorder()

	server.handleGetRepository(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var repo Repository
	if err := json.NewDecoder(w.Body).Decode(&repo); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if repo.FullName != "rust-lang/rust" {
		t.Errorf("full_name = %s, want rust-lang/rust", repo.FullName)
	}

	if repo.Stars != 50000 {
		t.Errorf("stars = %d, want 50000", repo.Stars)
	}
}

func TestHandleGetRepository_NotFound(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	mock.ExpectQuery("SELECT id, full_name").
		WithArgs("999").
		WillReturnError(sql.ErrNoRows)

	req := httptest.NewRequest("GET", "/api/v1/repositories/999", nil)
	req = mux.SetURLVars(req, map[string]string{"id": "999"})
	w := httptest.NewRecorder()

	server.handleGetRepository(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusNotFound)
	}
}

func TestHandleSearchRepositories(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	rows := sqlmock.NewRows([]string{
		"id", "full_name", "name", "description", "language",
		"stars", "forks", "quality_score", "download_status",
	}).AddRow(
		1, "rust-lang/rust", "rust", "A safe language",
		"Rust", 50000, 10000, 95, "downloaded",
	)

	mock.ExpectQuery("SELECT id, full_name").
		WithArgs("%rust%").
		WillReturnRows(rows)

	req := httptest.NewRequest("GET", "/api/v1/repositories/search?q=rust", nil)
	w := httptest.NewRecorder()

	server.handleSearchRepositories(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var response map[string]interface{}
	json.NewDecoder(w.Body).Decode(&response)

	if response["count"] != float64(1) {
		t.Errorf("count = %v, want 1", response["count"])
	}
}

func TestHandleSearchRepositories_MissingQuery(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	req := httptest.NewRequest("GET", "/api/v1/repositories/search", nil)
	w := httptest.NewRecorder()

	server.handleSearchRepositories(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusBadRequest)
	}
}

func TestHandleRepositoryStats(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	// Mock stats queries
	totalRows := sqlmock.NewRows([]string{"count"}).AddRow(100)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM repositories").WillReturnRows(totalRows)

	downloadedRows := sqlmock.NewRows([]string{"count"}).AddRow(80)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM repositories WHERE download_status").
		WillReturnRows(downloadedRows)

	avgQualityRows := sqlmock.NewRows([]string{"avg"}).AddRow(75.5)
	mock.ExpectQuery("SELECT AVG\\(quality_score\\)").WillReturnRows(avgQualityRows)

	langRows := sqlmock.NewRows([]string{"language", "count"}).
		AddRow("Rust", 30).
		AddRow("Go", 25)
	mock.ExpectQuery("SELECT language, COUNT").WillReturnRows(langRows)

	req := httptest.NewRequest("GET", "/api/v1/repositories/stats", nil)
	w := httptest.NewRecorder()

	server.handleRepositoryStats(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var response map[string]interface{}
	json.NewDecoder(w.Body).Decode(&response)

	if response["total"] != float64(100) {
		t.Errorf("total = %v, want 100", response["total"])
	}

	if response["downloaded"] != float64(80) {
		t.Errorf("downloaded = %v, want 80", response["downloaded"])
	}

	if response["avg_quality_score"] != 75.5 {
		t.Errorf("avg_quality_score = %v, want 75.5", response["avg_quality_score"])
	}
}

func TestHandleTopQualityRepos(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	rows := sqlmock.NewRows([]string{
		"id", "full_name", "name", "language", "stars", "forks", "quality_score",
	}).AddRow(1, "rust-lang/rust", "rust", "Rust", 50000, 10000, 95).
		AddRow(2, "golang/go", "go", "Go", 45000, 9000, 92)

	mock.ExpectQuery("SELECT id, full_name, name").
		WithArgs(20).
		WillReturnRows(rows)

	req := httptest.NewRequest("GET", "/api/v1/quality/top?limit=20", nil)
	w := httptest.NewRecorder()

	server.handleTopQualityRepos(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var repos []Repository
	json.NewDecoder(w.Body).Decode(&repos)

	if len(repos) != 2 {
		t.Errorf("len(repos) = %d, want 2", len(repos))
	}

	if repos[0].QualityScore != 95 {
		t.Errorf("Quality score = %d, want 95", repos[0].QualityScore)
	}
}

func TestHandleQualityDistribution(t *testing.T) {
	server, mock := setupMockServer(t)
	defer server.db.Close()

	rows := sqlmock.NewRows([]string{"range", "count"}).
		AddRow("90-100", 10).
		AddRow("80-89", 25).
		AddRow("70-79", 40)

	mock.ExpectQuery("SELECT").WillReturnRows(rows)

	req := httptest.NewRequest("GET", "/api/v1/quality/distribution", nil)
	w := httptest.NewRecorder()

	server.handleQualityDistribution(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	var distribution []map[string]interface{}
	json.NewDecoder(w.Body).Decode(&distribution)

	if len(distribution) != 3 {
		t.Errorf("len(distribution) = %d, want 3", len(distribution))
	}
}

func TestCORSMiddleware(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	wrapped := corsMiddleware(handler)

	req := httptest.NewRequest("GET", "/test", nil)
	w := httptest.NewRecorder()

	wrapped.ServeHTTP(w, req)

	if w.Header().Get("Access-Control-Allow-Origin") != "*" {
		t.Error("CORS header not set")
	}
}

func TestLoggingMiddleware(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	wrapped := loggingMiddleware(handler)

	req := httptest.NewRequest("GET", "/test", nil)
	w := httptest.NewRecorder()

	wrapped.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}
}

func TestServerClose(t *testing.T) {
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}

	server := &Server{db: db}

	if err := server.Close(); err != nil {
		t.Errorf("Close() error = %v, want nil", err)
	}
}

func BenchmarkHandleHealth(b *testing.B) {
	db, mock, _ := sqlmock.New()
	defer db.Close()

	server := &Server{db: db}
	mock.ExpectPing().WillReturnError(nil)

	req := httptest.NewRequest("GET", "/health", nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		server.handleHealth(w, req)
	}
}
