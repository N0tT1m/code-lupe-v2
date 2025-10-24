package main

import (
	"log"
	"os"

	"codelupe/internal/api"
	"codelupe/pkg/secrets"
)

func main() {
	// Load database configuration
	dbConfig, err := secrets.LoadDatabaseConfig()
	if err != nil {
		log.Fatalf("Failed to load database config: %v", err)
	}

	// Get Elasticsearch URL
	esURL := secrets.ReadSecretOrDefault("ELASTICSEARCH_URL", "http://localhost:9200")

	// Get API port
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8080"
	}

	// Create and start API server
	server := api.NewServer(api.Config{
		Port:             port,
		DatabaseConnStr:  dbConfig.ConnectionString(),
		ElasticsearchURL: esURL,
		EnableCORS:       true,
		EnableMetrics:    true,
	})

	log.Printf("Starting API server on port %s...", port)
	if err := server.Start(); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
