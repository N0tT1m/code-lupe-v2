package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	_ "github.com/lib/pq"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Prometheus metrics
var (
	// Processing metrics
	jobsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "codelupe_jobs_total",
			Help: "Total number of processing jobs",
		},
		[]string{"status"},
	)

	jobsInProgress = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "codelupe_jobs_in_progress",
			Help: "Number of jobs currently being processed",
		},
	)

	filesProcessedTotal = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "codelupe_files_processed_total",
			Help: "Total number of files processed",
		},
	)

	bytesProcessedTotal = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "codelupe_bytes_processed_total",
			Help: "Total bytes of code processed",
		},
	)

	processingDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "codelupe_processing_duration_seconds",
			Help:    "Time taken to process jobs",
			Buckets: prometheus.ExponentialBuckets(1, 2, 10),
		},
		[]string{"job_type"},
	)

	qualityScoreHistogram = prometheus.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "codelupe_quality_score",
			Help:    "Distribution of file quality scores",
			Buckets: []float64{0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100},
		},
	)

	languageFilesTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "codelupe_language_files_total",
			Help: "Total files processed by language",
		},
		[]string{"language"},
	)

	// Worker metrics
	workerActiveCount = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_workers_active",
			Help: "Number of active workers",
		},
		[]string{"worker_id", "worker_type"},
	)

	workerJobsCompleted = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "codelupe_worker_jobs_completed_total",
			Help: "Total jobs completed by worker",
		},
		[]string{"worker_id"},
	)

	// Database metrics
	dbConnections = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_db_connections",
			Help: "Database connection pool statistics",
		},
		[]string{"state"}, // active, idle, etc.
	)

	dbQueryDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "codelupe_db_query_duration_seconds",
			Help:    "Database query execution time",
			Buckets: prometheus.ExponentialBuckets(0.001, 2, 10),
		},
		[]string{"query_type"},
	)

	// System metrics
	systemCPUUsage = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "codelupe_system_cpu_usage_percent",
			Help: "Current CPU usage percentage",
		},
	)

	systemMemoryUsage = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "codelupe_system_memory_usage_bytes",
			Help: "Current memory usage in bytes",
		},
	)

	systemDiskUsage = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_system_disk_usage_bytes",
			Help: "Disk usage by mount point",
		},
		[]string{"mountpoint"},
	)

	// Repository metrics
	repoSizeBytes = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_repo_size_bytes",
			Help: "Repository size in bytes",
		},
		[]string{"repo_name"},
	)

	repoFileCount = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_repo_file_count",
			Help: "Number of files in repository",
		},
		[]string{"repo_name"},
	)

	// Error metrics
	errorsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "codelupe_errors_total",
			Help: "Total number of errors",
		},
		[]string{"component", "error_type"},
	)

	// Rate metrics
	processingRate = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "codelupe_processing_rate_per_second",
			Help: "Current processing rate",
		},
		[]string{"metric_type"}, // files_per_sec, jobs_per_sec, bytes_per_sec
	)
)

type MetricsExporter struct {
	db *sql.DB
}

func NewMetricsExporter(dbURL string) (*MetricsExporter, error) {
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		return nil, err
	}

	return &MetricsExporter{db: db}, nil
}

func (m *MetricsExporter) RegisterMetrics() {
	prometheus.MustRegister(
		jobsTotal,
		jobsInProgress,
		filesProcessedTotal,
		bytesProcessedTotal,
		processingDuration,
		qualityScoreHistogram,
		languageFilesTotal,
		workerActiveCount,
		workerJobsCompleted,
		dbConnections,
		dbQueryDuration,
		systemCPUUsage,
		systemMemoryUsage,
		systemDiskUsage,
		repoSizeBytes,
		repoFileCount,
		errorsTotal,
		processingRate,
	)
}

func (m *MetricsExporter) UpdateJobMetrics() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("job_stats").Observe(time.Since(start).Seconds())
	}()

	// Job status counts
	rows, err := m.db.Query(`
		SELECT status, COUNT(*) 
		FROM processing_jobs 
		GROUP BY status
	`)
	if err != nil {
		errorsTotal.WithLabelValues("metrics_exporter", "db_query").Inc()
		return err
	}
	defer rows.Close()

	// Reset gauges
	jobsInProgress.Set(0)

	for rows.Next() {
		var status string
		var count float64
		if err := rows.Scan(&status, &count); err != nil {
			continue
		}

		jobsTotal.WithLabelValues(status).Add(count)

		if status == "processing" {
			jobsInProgress.Set(count)
		}
	}

	return nil
}

func (m *MetricsExporter) UpdateFileMetrics() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("file_stats").Observe(time.Since(start).Seconds())
	}()

	// Total files and bytes
	var totalFiles, totalBytes float64
	err := m.db.QueryRow(`
		SELECT COUNT(*), COALESCE(SUM(size), 0) 
		FROM processed_files
	`).Scan(&totalFiles, &totalBytes)
	if err != nil {
		errorsTotal.WithLabelValues("metrics_exporter", "db_query").Inc()
		return err
	}

	filesProcessedTotal.Add(totalFiles)
	bytesProcessedTotal.Add(totalBytes)

	// Language distribution
	rows, err := m.db.Query(`
		SELECT language, COUNT(*) 
		FROM processed_files 
		GROUP BY language
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var language string
		var count float64
		if err := rows.Scan(&language, &count); err != nil {
			continue
		}
		languageFilesTotal.WithLabelValues(language).Add(count)
	}

	// Quality score distribution
	qualityRows, err := m.db.Query(`
		SELECT quality_score 
		FROM processed_files 
		WHERE processed_at >= NOW() - INTERVAL '1 hour'
	`)
	if err != nil {
		return err
	}
	defer qualityRows.Close()

	for qualityRows.Next() {
		var score float64
		if err := qualityRows.Scan(&score); err != nil {
			continue
		}
		qualityScoreHistogram.Observe(score)
	}

	return nil
}

func (m *MetricsExporter) UpdateWorkerMetrics() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("worker_stats").Observe(time.Since(start).Seconds())
	}()

	// Active workers
	rows, err := m.db.Query(`
		SELECT worker_id, COUNT(*) 
		FROM processing_jobs 
		WHERE status = 'processing' AND worker_id IS NOT NULL
		GROUP BY worker_id
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	// Reset worker gauges
	workerActiveCount.Reset()

	for rows.Next() {
		var workerID string
		var jobCount float64
		if err := rows.Scan(&workerID, &jobCount); err != nil {
			continue
		}
		workerActiveCount.WithLabelValues(workerID, "processor").Set(1)
		workerJobsCompleted.WithLabelValues(workerID).Add(jobCount)
	}

	return nil
}

func (m *MetricsExporter) UpdateRepositoryMetrics() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("repo_stats").Observe(time.Since(start).Seconds())
	}()

	// Repository statistics
	rows, err := m.db.Query(`
		SELECT 
			repo_name,
			COUNT(*) as file_count,
			SUM(size) as total_size
		FROM processed_files 
		GROUP BY repo_name
		HAVING COUNT(*) >= 10  -- Only repos with significant files
		ORDER BY total_size DESC
		LIMIT 100  -- Top 100 repos
	`)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var repoName string
		var fileCount, totalSize float64
		if err := rows.Scan(&repoName, &fileCount, &totalSize); err != nil {
			continue
		}
		repoFileCount.WithLabelValues(repoName).Set(fileCount)
		repoSizeBytes.WithLabelValues(repoName).Set(totalSize)
	}

	return nil
}

func (m *MetricsExporter) UpdateProcessingRates() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("rate_stats").Observe(time.Since(start).Seconds())
	}()

	// Calculate processing rates for the last hour
	var filesLastHour, bytesLastHour float64
	err := m.db.QueryRow(`
		SELECT 
			COUNT(*),
			COALESCE(SUM(size), 0)
		FROM processed_files 
		WHERE processed_at >= NOW() - INTERVAL '1 hour'
	`).Scan(&filesLastHour, &bytesLastHour)
	if err != nil {
		return err
	}

	// Convert to per-second rates
	processingRate.WithLabelValues("files_per_second").Set(filesLastHour / 3600)
	processingRate.WithLabelValues("bytes_per_second").Set(bytesLastHour / 3600)

	// Jobs completed in last hour
	var jobsLastHour float64
	err = m.db.QueryRow(`
		SELECT COUNT(*) 
		FROM processing_jobs 
		WHERE completed_at >= NOW() - INTERVAL '1 hour'
	`).Scan(&jobsLastHour)
	if err != nil {
		return err
	}

	processingRate.WithLabelValues("jobs_per_second").Set(jobsLastHour / 3600)

	return nil
}

func (m *MetricsExporter) UpdateDatabaseMetrics() error {
	start := time.Now()
	defer func() {
		dbQueryDuration.WithLabelValues("db_internal").Observe(time.Since(start).Seconds())
	}()

	// Database connection stats
	stats := m.db.Stats()
	dbConnections.WithLabelValues("open").Set(float64(stats.OpenConnections))
	dbConnections.WithLabelValues("idle").Set(float64(stats.Idle))
	dbConnections.WithLabelValues("in_use").Set(float64(stats.InUse))

	// Database size metrics
	var dbSize float64
	err := m.db.QueryRow(`
		SELECT pg_database_size(current_database())
	`).Scan(&dbSize)
	if err != nil {
		return err
	}

	systemDiskUsage.WithLabelValues("database").Set(dbSize)

	return nil
}

func (m *MetricsExporter) UpdateSystemMetrics() error {
	// Note: In a real implementation, you'd use system calls or libraries
	// to get actual CPU, memory, and disk usage. For now, we'll use placeholders.

	// Placeholder system metrics - replace with actual system monitoring
	systemCPUUsage.Set(45.2)                                // Would be actual CPU usage
	systemMemoryUsage.Set(8589934592)                       // Would be actual memory usage
	systemDiskUsage.WithLabelValues("/").Set(1073741824000) // Would be actual disk usage

	return nil
}

func (m *MetricsExporter) CollectAllMetrics() {
	log.Println("🔄 Collecting metrics...")

	// Update all metric categories
	if err := m.UpdateJobMetrics(); err != nil {
		log.Printf("❌ Failed to update job metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "job_metrics").Inc()
	}

	if err := m.UpdateFileMetrics(); err != nil {
		log.Printf("❌ Failed to update file metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "file_metrics").Inc()
	}

	if err := m.UpdateWorkerMetrics(); err != nil {
		log.Printf("❌ Failed to update worker metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "worker_metrics").Inc()
	}

	if err := m.UpdateRepositoryMetrics(); err != nil {
		log.Printf("❌ Failed to update repository metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "repo_metrics").Inc()
	}

	if err := m.UpdateProcessingRates(); err != nil {
		log.Printf("❌ Failed to update processing rates: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "rate_metrics").Inc()
	}

	if err := m.UpdateDatabaseMetrics(); err != nil {
		log.Printf("❌ Failed to update database metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "db_metrics").Inc()
	}

	if err := m.UpdateSystemMetrics(); err != nil {
		log.Printf("❌ Failed to update system metrics: %v", err)
		errorsTotal.WithLabelValues("metrics_exporter", "system_metrics").Inc()
	}

	log.Println("✅ Metrics collection completed")
}

func (m *MetricsExporter) StartMetricsServer(port string) {
	http.Handle("/metrics", promhttp.Handler())

	// Health check endpoint
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"healthy","timestamp":"%s"}`, time.Now().UTC().Format(time.RFC3339))
	})

	// Metrics summary endpoint
	http.HandleFunc("/summary", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		// Get summary data from database
		var totalJobs, completedJobs, totalFiles int64
		var totalBytes float64

		m.db.QueryRow("SELECT COUNT(*) FROM processing_jobs").Scan(&totalJobs)
		m.db.QueryRow("SELECT COUNT(*) FROM processing_jobs WHERE status = 'completed'").Scan(&completedJobs)
		m.db.QueryRow("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM processed_files").Scan(&totalFiles, &totalBytes)

		summary := map[string]interface{}{
			"total_jobs":     totalJobs,
			"completed_jobs": completedJobs,
			"total_files":    totalFiles,
			"total_bytes":    totalBytes,
			"completion_pct": float64(completedJobs) / float64(totalJobs) * 100,
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
		}

		if err := json.NewEncoder(w).Encode(summary); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
	})

	log.Printf("🌐 Metrics server starting on port %s", port)
	log.Printf("📊 Prometheus metrics: http://localhost:%s/metrics", port)
	log.Printf("💚 Health check: http://localhost:%s/health", port)
	log.Printf("📈 Summary: http://localhost:%s/summary", port)

	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func main() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"
	}

	port := os.Getenv("METRICS_PORT")
	if port == "" {
		port = "9091"
	}

	fmt.Printf("🚀 CodeLupe Metrics Exporter Starting\n")
	fmt.Printf("💾 Database: %s\n", dbURL)
	fmt.Printf("🌐 Port: %s\n", port)

	exporter, err := NewMetricsExporter(dbURL)
	if err != nil {
		log.Fatalf("❌ Failed to create metrics exporter: %v", err)
	}
	defer exporter.db.Close()

	// Register Prometheus metrics
	exporter.RegisterMetrics()

	// Start metrics collection in background
	go func() {
		ticker := time.NewTicker(30 * time.Second) // Collect every 30 seconds
		defer ticker.Stop()

		// Initial collection
		exporter.CollectAllMetrics()

		for range ticker.C {
			exporter.CollectAllMetrics()
		}
	}()

	// Start HTTP server
	exporter.StartMetricsServer(port)
}
