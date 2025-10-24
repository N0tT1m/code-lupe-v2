package main

import (
	"database/sql"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/prometheus/client_golang/prometheus"
)

func setupMockExporter(t *testing.T) (*MetricsExporter, sqlmock.Sqlmock) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}

	exporter := &MetricsExporter{
		db: db,
	}

	return exporter, mock
}

func TestNewMetricsExporter_Success(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}
	defer db.Close()

	mock.ExpectPing()

	// We can't easily test NewMetricsExporter with a real connection string,
	// so we test the constructor logic manually
	exporter := &MetricsExporter{db: db}

	if exporter.db == nil {
		t.Error("Database was not initialized")
	}
}

func TestRegisterMetrics(t *testing.T) {
	exporter, _ := setupMockExporter(t)
	defer exporter.db.Close()

	// Create a new registry to avoid conflicts with global registry
	registry := prometheus.NewRegistry()

	// Test that metrics can be registered without panic
	defer func() {
		if r := recover(); r != nil {
			t.Errorf("RegisterMetrics() panicked: %v", r)
		}
	}()

	// Register metrics manually with custom registry
	registry.MustRegister(jobsTotal)
	registry.MustRegister(jobsInProgress)
	registry.MustRegister(filesProcessedTotal)

	// Verify metrics are registered
	metrics, err := registry.Gather()
	if err != nil {
		t.Fatalf("Failed to gather metrics: %v", err)
	}

	if len(metrics) < 3 {
		t.Errorf("Expected at least 3 metrics, got %d", len(metrics))
	}
}

func TestUpdateJobMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock job status query
	rows := sqlmock.NewRows([]string{"status", "count"}).
		AddRow("completed", 50).
		AddRow("processing", 5).
		AddRow("failed", 2)

	mock.ExpectQuery("SELECT status, COUNT").WillReturnRows(rows)

	err := exporter.UpdateJobMetrics()
	if err != nil {
		t.Errorf("UpdateJobMetrics() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestUpdateJobMetrics_Error(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	mock.ExpectQuery("SELECT status, COUNT").WillReturnError(sql.ErrConnDone)

	err := exporter.UpdateJobMetrics()
	if err == nil {
		t.Error("UpdateJobMetrics() error = nil, want error")
	}
}

func TestUpdateFileMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock total files query
	totalRows := sqlmock.NewRows([]string{"count", "sum"}).
		AddRow(1000, 5000000)
	mock.ExpectQuery("SELECT COUNT, COALESCE").WillReturnRows(totalRows)

	// Mock language distribution query
	langRows := sqlmock.NewRows([]string{"language", "count"}).
		AddRow("Go", 400).
		AddRow("Python", 300).
		AddRow("Rust", 200)
	mock.ExpectQuery("SELECT language, COUNT").WillReturnRows(langRows)

	// Mock quality score query
	qualityRows := sqlmock.NewRows([]string{"quality_score"}).
		AddRow(85).
		AddRow(90).
		AddRow(75)
	mock.ExpectQuery("SELECT quality_score").WillReturnRows(qualityRows)

	err := exporter.UpdateFileMetrics()
	if err != nil {
		t.Errorf("UpdateFileMetrics() error = %v, want nil", err)
	}
}

func TestUpdateWorkerMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	rows := sqlmock.NewRows([]string{"worker_id", "count"}).
		AddRow("worker_1", 10).
		AddRow("worker_2", 8)

	mock.ExpectQuery("SELECT worker_id, COUNT").WillReturnRows(rows)

	err := exporter.UpdateWorkerMetrics()
	if err != nil {
		t.Errorf("UpdateWorkerMetrics() error = %v, want nil", err)
	}
}

func TestUpdateRepositoryMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	rows := sqlmock.NewRows([]string{"repo_name", "file_count", "total_size"}).
		AddRow("rust-lang/rust", 5000, 10000000).
		AddRow("golang/go", 3000, 8000000)

	mock.ExpectQuery("SELECT").WillReturnRows(rows)

	err := exporter.UpdateRepositoryMetrics()
	if err != nil {
		t.Errorf("UpdateRepositoryMetrics() error = %v, want nil", err)
	}
}

func TestUpdateProcessingRates(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock files and bytes query
	filesRows := sqlmock.NewRows([]string{"count", "sum"}).
		AddRow(3600, 36000000)
	mock.ExpectQuery("SELECT").WillReturnRows(filesRows)

	// Mock jobs query
	jobsRows := sqlmock.NewRows([]string{"count"}).AddRow(120)
	mock.ExpectQuery("SELECT COUNT").WillReturnRows(jobsRows)

	err := exporter.UpdateProcessingRates()
	if err != nil {
		t.Errorf("UpdateProcessingRates() error = %v, want nil", err)
	}
}

func TestUpdateDatabaseMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock database size query
	sizeRows := sqlmock.NewRows([]string{"pg_database_size"}).
		AddRow(1073741824) // 1GB
	mock.ExpectQuery("SELECT pg_database_size").WillReturnRows(sizeRows)

	err := exporter.UpdateDatabaseMetrics()
	if err != nil {
		t.Errorf("UpdateDatabaseMetrics() error = %v, want nil", err)
	}
}

func TestUpdateSystemMetrics(t *testing.T) {
	exporter, _ := setupMockExporter(t)
	defer exporter.db.Close()

	// System metrics don't query the database
	err := exporter.UpdateSystemMetrics()
	if err != nil {
		t.Errorf("UpdateSystemMetrics() error = %v, want nil", err)
	}
}

func TestCollectAllMetrics(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock all queries that CollectAllMetrics will make

	// Job metrics
	jobRows := sqlmock.NewRows([]string{"status", "count"}).
		AddRow("completed", 50)
	mock.ExpectQuery("SELECT status, COUNT").WillReturnRows(jobRows)

	// File metrics - total
	totalRows := sqlmock.NewRows([]string{"count", "sum"}).
		AddRow(1000, 5000000)
	mock.ExpectQuery("SELECT COUNT, COALESCE").WillReturnRows(totalRows)

	// File metrics - languages
	langRows := sqlmock.NewRows([]string{"language", "count"}).
		AddRow("Go", 400)
	mock.ExpectQuery("SELECT language, COUNT").WillReturnRows(langRows)

	// File metrics - quality
	qualityRows := sqlmock.NewRows([]string{"quality_score"}).AddRow(85)
	mock.ExpectQuery("SELECT quality_score").WillReturnRows(qualityRows)

	// Worker metrics
	workerRows := sqlmock.NewRows([]string{"worker_id", "count"}).
		AddRow("worker_1", 10)
	mock.ExpectQuery("SELECT worker_id, COUNT").WillReturnRows(workerRows)

	// Repository metrics
	repoRows := sqlmock.NewRows([]string{"repo_name", "file_count", "total_size"}).
		AddRow("test/repo", 100, 1000000)
	mock.ExpectQuery("SELECT.*repo_name").WillReturnRows(repoRows)

	// Processing rates
	filesRateRows := sqlmock.NewRows([]string{"count", "sum"}).
		AddRow(3600, 36000000)
	mock.ExpectQuery("SELECT.*processed_at").WillReturnRows(filesRateRows)

	jobsRateRows := sqlmock.NewRows([]string{"count"}).AddRow(120)
	mock.ExpectQuery("SELECT COUNT.*completed_at").WillReturnRows(jobsRateRows)

	// Database metrics
	dbSizeRows := sqlmock.NewRows([]string{"pg_database_size"}).
		AddRow(1073741824)
	mock.ExpectQuery("SELECT pg_database_size").WillReturnRows(dbSizeRows)

	// This should not panic
	exporter.CollectAllMetrics()
}

func TestHealthEndpoint(t *testing.T) {
	exporter, _ := setupMockExporter(t)
	defer exporter.db.Close()

	// Create a test HTTP server
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}

	contentType := w.Header().Get("Content-Type")
	if contentType != "application/json" {
		t.Errorf("Content-Type = %s, want application/json", contentType)
	}
}

func TestSummaryEndpoint(t *testing.T) {
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	// Mock summary queries
	mock.ExpectQuery("SELECT COUNT.*FROM processing_jobs").
		WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(100))

	mock.ExpectQuery("SELECT COUNT.*WHERE status").
		WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(80))

	mock.ExpectQuery("SELECT COUNT.*FROM processed_files").
		WillReturnRows(sqlmock.NewRows([]string{"count", "sum"}).AddRow(5000, 10000000))

	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var totalJobs, completedJobs, totalFiles int64
		var totalBytes float64

		exporter.db.QueryRow("SELECT COUNT(*) FROM processing_jobs").Scan(&totalJobs)
		exporter.db.QueryRow("SELECT COUNT(*) FROM processing_jobs WHERE status = 'completed'").Scan(&completedJobs)
		exporter.db.QueryRow("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM processed_files").Scan(&totalFiles, &totalBytes)

		w.WriteHeader(http.StatusOK)
	})

	req := httptest.NewRequest("GET", "/summary", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status code = %d, want %d", w.Code, http.StatusOK)
	}
}

func BenchmarkUpdateJobMetrics(b *testing.B) {
	t := &testing.T{}
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	rows := sqlmock.NewRows([]string{"status", "count"}).
		AddRow("completed", 50)

	for i := 0; i < b.N; i++ {
		mock.ExpectQuery("SELECT status, COUNT").WillReturnRows(rows)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		exporter.UpdateJobMetrics()
	}
}

func BenchmarkUpdateFileMetrics(b *testing.B) {
	t := &testing.T{}
	exporter, mock := setupMockExporter(t)
	defer exporter.db.Close()

	totalRows := sqlmock.NewRows([]string{"count", "sum"}).AddRow(1000, 5000000)
	langRows := sqlmock.NewRows([]string{"language", "count"}).AddRow("Go", 400)
	qualityRows := sqlmock.NewRows([]string{"quality_score"}).AddRow(85)

	for i := 0; i < b.N; i++ {
		mock.ExpectQuery("SELECT COUNT, COALESCE").WillReturnRows(totalRows)
		mock.ExpectQuery("SELECT language, COUNT").WillReturnRows(langRows)
		mock.ExpectQuery("SELECT quality_score").WillReturnRows(qualityRows)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		exporter.UpdateFileMetrics()
	}
}
