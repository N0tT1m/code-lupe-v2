package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/elastic/go-elasticsearch/v8"
	"github.com/gorilla/mux"
	_ "github.com/lib/pq"
)

// Config holds API server configuration
type Config struct {
	Port             string
	DatabaseConnStr  string
	ElasticsearchURL string
	EnableCORS       bool
	EnableMetrics    bool
}

// Server represents the API server
type Server struct {
	config   Config
	router   *mux.Router
	db       *sql.DB
	esClient *elasticsearch.Client
}

// NewServer creates a new API server
func NewServer(config Config) *Server {
	return &Server{
		config: config,
		router: mux.NewRouter(),
	}
}

// Start initializes and starts the API server
func (s *Server) Start() error {
	// Initialize database connection
	db, err := sql.Open("postgres", s.config.DatabaseConnStr)
	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}
	s.db = db

	// Initialize Elasticsearch client
	esClient, err := elasticsearch.NewClient(elasticsearch.Config{
		Addresses: []string{s.config.ElasticsearchURL},
	})
	if err != nil {
		return fmt.Errorf("failed to create Elasticsearch client: %w", err)
	}
	s.esClient = esClient

	// Setup routes
	s.setupRoutes()

	// Start server
	addr := ":" + s.config.Port
	log.Printf("API server listening on %s", addr)
	return http.ListenAndServe(addr, s.router)
}

// setupRoutes configures API routes
func (s *Server) setupRoutes() {
	// Health check
	s.router.HandleFunc("/health", s.handleHealth).Methods("GET")

	// API documentation
	s.router.HandleFunc("/api/docs", s.handleSwaggerUI).Methods("GET")
	s.router.HandleFunc("/api/openapi.yaml", s.handleOpenAPISpec).Methods("GET")

	// Repository endpoints
	s.router.HandleFunc("/api/v1/repositories", s.handleListRepositories).Methods("GET")
	s.router.HandleFunc("/api/v1/repositories/{id}", s.handleGetRepository).Methods("GET")
	s.router.HandleFunc("/api/v1/repositories/search", s.handleSearchRepositories).Methods("GET")
	s.router.HandleFunc("/api/v1/repositories/stats", s.handleRepositoryStats).Methods("GET")

	// Language statistics
	s.router.HandleFunc("/api/v1/languages", s.handleListLanguages).Methods("GET")
	s.router.HandleFunc("/api/v1/languages/{language}/stats", s.handleLanguageStats).Methods("GET")

	// Quality metrics
	s.router.HandleFunc("/api/v1/quality/top", s.handleTopQualityRepos).Methods("GET")
	s.router.HandleFunc("/api/v1/quality/distribution", s.handleQualityDistribution).Methods("GET")

	// CORS middleware
	if s.config.EnableCORS {
		s.router.Use(corsMiddleware)
	}

	// Logging middleware
	s.router.Use(loggingMiddleware)
}

// Repository represents a repository response
type Repository struct {
	ID             int64     `json:"id"`
	FullName       string    `json:"full_name"`
	Name           string    `json:"name"`
	Description    string    `json:"description"`
	Language       string    `json:"language"`
	Stars          int       `json:"stars"`
	Forks          int       `json:"forks"`
	QualityScore   int       `json:"quality_score"`
	DownloadStatus string    `json:"download_status"`
	LocalPath      string    `json:"local_path,omitempty"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// handleHealth returns server health status
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status": "healthy",
		"time":   time.Now().Format(time.RFC3339),
	}

	// Check database
	if err := s.db.Ping(); err != nil {
		health["status"] = "unhealthy"
		health["database"] = "error"
		w.WriteHeader(http.StatusServiceUnavailable)
	} else {
		health["database"] = "ok"
	}

	// Check Elasticsearch
	_, err := s.esClient.Info()
	if err != nil {
		health["elasticsearch"] = "error"
	} else {
		health["elasticsearch"] = "ok"
	}

	json.NewEncoder(w).Encode(health)
}

// handleListRepositories returns a paginated list of repositories
func (s *Server) handleListRepositories(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}

	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 || limit > 100 {
		limit = 20
	}

	offset := (page - 1) * limit

	// Query database
	query := `
		SELECT id, full_name, name, description, language, stars, forks,
		       quality_score, download_status, created_at, updated_at
		FROM repositories
		ORDER BY stars DESC
		LIMIT $1 OFFSET $2
	`

	rows, err := s.db.Query(query, limit, offset)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var repos []Repository
	for rows.Next() {
		var repo Repository
		var name, description sql.NullString
		err := rows.Scan(
			&repo.ID, &repo.FullName, &name, &description,
			&repo.Language, &repo.Stars, &repo.Forks,
			&repo.QualityScore, &repo.DownloadStatus,
			&repo.CreatedAt, &repo.UpdatedAt,
		)
		if err != nil {
			continue
		}

		if name.Valid {
			repo.Name = name.String
		}
		if description.Valid {
			repo.Description = description.String
		}

		repos = append(repos, repo)
	}

	// Get total count
	var total int
	s.db.QueryRow("SELECT COUNT(*) FROM repositories").Scan(&total)

	response := map[string]interface{}{
		"data":  repos,
		"page":  page,
		"limit": limit,
		"total": total,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// handleGetRepository returns a single repository by ID
func (s *Server) handleGetRepository(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	var repo Repository
	var name, description, localPath sql.NullString

	err := s.db.QueryRow(`
		SELECT id, full_name, name, description, language, stars, forks,
		       quality_score, download_status, local_path, created_at, updated_at
		FROM repositories WHERE id = $1
	`, id).Scan(
		&repo.ID, &repo.FullName, &name, &description,
		&repo.Language, &repo.Stars, &repo.Forks,
		&repo.QualityScore, &repo.DownloadStatus, &localPath,
		&repo.CreatedAt, &repo.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		http.Error(w, "Repository not found", http.StatusNotFound)
		return
	}
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	if name.Valid {
		repo.Name = name.String
	}
	if description.Valid {
		repo.Description = description.String
	}
	if localPath.Valid {
		repo.LocalPath = localPath.String
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repo)
}

// handleSearchRepositories searches repositories by query
func (s *Server) handleSearchRepositories(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "Query parameter 'q' is required", http.StatusBadRequest)
		return
	}

	language := r.URL.Query().Get("language")
	minStars, _ := strconv.Atoi(r.URL.Query().Get("min_stars"))

	// Build SQL query
	query := `
		SELECT id, full_name, name, description, language, stars, forks,
		       quality_score, download_status
		FROM repositories
		WHERE (full_name ILIKE $1 OR description ILIKE $1)
	`
	args := []interface{}{"%" + q + "%"}

	if language != "" {
		query += " AND language = $2"
		args = append(args, language)
	}

	if minStars > 0 {
		query += fmt.Sprintf(" AND stars >= $%d", len(args)+1)
		args = append(args, minStars)
	}

	query += " ORDER BY stars DESC LIMIT 50"

	rows, err := s.db.Query(query, args...)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var repos []Repository
	for rows.Next() {
		var repo Repository
		var name, description sql.NullString
		err := rows.Scan(
			&repo.ID, &repo.FullName, &name, &description,
			&repo.Language, &repo.Stars, &repo.Forks,
			&repo.QualityScore, &repo.DownloadStatus,
		)
		if err != nil {
			continue
		}

		if name.Valid {
			repo.Name = name.String
		}
		if description.Valid {
			repo.Description = description.String
		}

		repos = append(repos, repo)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"results": repos,
		"count":   len(repos),
	})
}

// handleRepositoryStats returns overall repository statistics
func (s *Server) handleRepositoryStats(w http.ResponseWriter, r *http.Request) {
	stats := make(map[string]interface{})

	// Total repositories
	var total int
	s.db.QueryRow("SELECT COUNT(*) FROM repositories").Scan(&total)
	stats["total"] = total

	// Downloaded count
	var downloaded int
	s.db.QueryRow("SELECT COUNT(*) FROM repositories WHERE download_status = 'downloaded'").Scan(&downloaded)
	stats["downloaded"] = downloaded

	// Average quality score
	var avgQuality float64
	s.db.QueryRow("SELECT AVG(quality_score) FROM repositories WHERE quality_score > 0").Scan(&avgQuality)
	stats["avg_quality_score"] = avgQuality

	// Top languages
	rows, _ := s.db.Query(`
		SELECT language, COUNT(*) as count
		FROM repositories
		WHERE language IS NOT NULL AND language != ''
		GROUP BY language
		ORDER BY count DESC
		LIMIT 10
	`)
	defer rows.Close()

	var languages []map[string]interface{}
	for rows.Next() {
		var lang string
		var count int
		rows.Scan(&lang, &count)
		languages = append(languages, map[string]interface{}{
			"language": lang,
			"count":    count,
		})
	}
	stats["top_languages"] = languages

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

// handleListLanguages returns list of languages with counts
func (s *Server) handleListLanguages(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.Query(`
		SELECT language, COUNT(*) as count, AVG(stars) as avg_stars
		FROM repositories
		WHERE language IS NOT NULL AND language != ''
		GROUP BY language
		ORDER BY count DESC
	`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var languages []map[string]interface{}
	for rows.Next() {
		var lang string
		var count int
		var avgStars float64
		rows.Scan(&lang, &count, &avgStars)
		languages = append(languages, map[string]interface{}{
			"language":  lang,
			"count":     count,
			"avg_stars": avgStars,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(languages)
}

// handleLanguageStats returns statistics for a specific language
func (s *Server) handleLanguageStats(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	language := vars["language"]

	stats := make(map[string]interface{})
	stats["language"] = language

	// Count
	var count int
	s.db.QueryRow("SELECT COUNT(*) FROM repositories WHERE language = $1", language).Scan(&count)
	stats["count"] = count

	// Stars statistics
	s.db.QueryRow(`
		SELECT AVG(stars), MAX(stars), MIN(stars)
		FROM repositories WHERE language = $1
	`, language).Scan(&stats["avg_stars"], &stats["max_stars"], &stats["min_stars"])

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

// handleTopQualityRepos returns top quality repositories
func (s *Server) handleTopQualityRepos(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 || limit > 100 {
		limit = 20
	}

	rows, err := s.db.Query(`
		SELECT id, full_name, name, language, stars, forks, quality_score
		FROM repositories
		WHERE quality_score >= 70
		ORDER BY quality_score DESC, stars DESC
		LIMIT $1
	`, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var repos []Repository
	for rows.Next() {
		var repo Repository
		var name sql.NullString
		rows.Scan(&repo.ID, &repo.FullName, &name, &repo.Language,
			&repo.Stars, &repo.Forks, &repo.QualityScore)
		if name.Valid {
			repo.Name = name.String
		}
		repos = append(repos, repo)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(repos)
}

// handleQualityDistribution returns quality score distribution
func (s *Server) handleQualityDistribution(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.Query(`
		SELECT
			CASE
				WHEN quality_score >= 90 THEN '90-100'
				WHEN quality_score >= 80 THEN '80-89'
				WHEN quality_score >= 70 THEN '70-79'
				WHEN quality_score >= 60 THEN '60-69'
				ELSE '0-59'
			END as range,
			COUNT(*) as count
		FROM repositories
		WHERE quality_score > 0
		GROUP BY range
		ORDER BY range DESC
	`)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var distribution []map[string]interface{}
	for rows.Next() {
		var rangeStr string
		var count int
		rows.Scan(&rangeStr, &count)
		distribution = append(distribution, map[string]interface{}{
			"range": rangeStr,
			"count": count,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(distribution)
}

// handleSwaggerUI serves the Swagger UI HTML page
func (s *Server) handleSwaggerUI(w http.ResponseWriter, r *http.Request) {
	html := `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CodeLupe API Documentation</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin:0; padding:0; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      const ui = SwaggerUIBundle({
        url: "/api/openapi.yaml",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
      });
      window.ui = ui;
    };
  </script>
</body>
</html>`

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(html))
}

// handleOpenAPISpec serves the OpenAPI specification file
func (s *Server) handleOpenAPISpec(w http.ResponseWriter, r *http.Request) {
	// Try to find openapi.yaml in the api directory
	specPath := filepath.Join("api", "openapi.yaml")

	// If not found, try project root
	if _, err := os.Stat(specPath); os.IsNotExist(err) {
		specPath = "openapi.yaml"
	}

	data, err := os.ReadFile(specPath)
	if err != nil {
		http.Error(w, "OpenAPI specification not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/x-yaml")
	w.Write(data)
}

// Middleware functions

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %v", r.Method, r.URL.Path, time.Since(start))
	})
}

// Close closes all connections
func (s *Server) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}
