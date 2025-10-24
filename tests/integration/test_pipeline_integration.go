package integration

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"github.com/elastic/go-elasticsearch/v8"
	"github.com/go-redis/redis/v8"
	_ "github.com/lib/pq"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestDatabaseConnection tests PostgreSQL connectivity
func TestDatabaseConnection(t *testing.testing) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	dbURL := getEnv("DATABASE_URL", "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable")
	db, err := sql.Open("postgres", dbURL)
	require.NoError(t, err)
	defer db.Close()

	err = db.Ping()
	assert.NoError(t, err, "Should connect to PostgreSQL")

	// Test repositories table exists
	var exists bool
	err = db.QueryRow("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'repositories')").Scan(&exists)
	require.NoError(t, err)
	assert.True(t, exists, "Repositories table should exist")
}

// TestElasticsearchConnection tests Elasticsearch connectivity
func TestElasticsearchConnection(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	esURL := getEnv("ELASTICSEARCH_URL", "http://localhost:9200")
	cfg := elasticsearch.Config{
		Addresses: []string{esURL},
	}

	es, err := elasticsearch.NewClient(cfg)
	require.NoError(t, err)

	// Test connection
	res, err := es.Info()
	require.NoError(t, err)
	defer res.Body.Close()

	assert.Equal(t, 200, res.StatusCode, "Should connect to Elasticsearch")
}

// TestRedisConnection tests Redis connectivity
func TestRedisConnection(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	redisURL := getEnv("REDIS_URL", "localhost:6379")
	client := redis.NewClient(&redis.Options{
		Addr: redisURL,
	})
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Test ping
	pong, err := client.Ping(ctx).Result()
	assert.NoError(t, err)
	assert.Equal(t, "PONG", pong, "Should receive PONG from Redis")
}

// TestFullPipelineFlow tests the complete data flow
func TestFullPipelineFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	// 1. Insert test repository into PostgreSQL
	dbURL := getEnv("DATABASE_URL", "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable")
	db, err := sql.Open("postgres", dbURL)
	require.NoError(t, err)
	defer db.Close()

	testRepo := "test-user/test-repo-" + time.Now().Format("20060102150405")
	_, err = db.Exec(`
		INSERT INTO repositories (full_name, clone_url, language, quality_score)
		VALUES ($1, $2, $3, $4)
	`, testRepo, "https://github.com/"+testRepo, "Go", 85)
	require.NoError(t, err)

	// 2. Verify repository was inserted
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM repositories WHERE full_name = $1", testRepo).Scan(&count)
	require.NoError(t, err)
	assert.Equal(t, 1, count, "Repository should be inserted")

	// 3. Clean up
	_, err = db.Exec("DELETE FROM repositories WHERE full_name = $1", testRepo)
	require.NoError(t, err)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
