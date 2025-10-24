package cache

import (
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/go-redis/redis/v8"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestRedis(t *testing.T) (*RedisCache, *miniredis.Miniredis) {
	// Create an in-memory Redis server for testing
	mr, err := miniredis.Run()
	require.NoError(t, err)

	// Create Redis client
	client := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})

	rc := &RedisCache{
		client: client,
		ctx:    client.Context(),
	}

	return rc, mr
}

func TestRedisCache_SetAndGet(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	type testData struct {
		Name  string
		Value int
	}

	data := testData{Name: "test", Value: 42}

	// Test Set
	err := rc.Set("test:key", data, time.Minute)
	require.NoError(t, err)

	// Test Get
	var retrieved testData
	err = rc.Get("test:key", &retrieved)
	require.NoError(t, err)
	assert.Equal(t, data.Name, retrieved.Name)
	assert.Equal(t, data.Value, retrieved.Value)
}

func TestRedisCache_Exists(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	// Test non-existent key
	exists, err := rc.Exists("nonexistent")
	require.NoError(t, err)
	assert.False(t, exists)

	// Set a key
	err = rc.Set("existing", "value", time.Minute)
	require.NoError(t, err)

	// Test existing key
	exists, err = rc.Exists("existing")
	require.NoError(t, err)
	assert.True(t, exists)
}

func TestRedisCache_Delete(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	// Set a key
	err := rc.Set("to_delete", "value", time.Minute)
	require.NoError(t, err)

	// Verify it exists
	exists, err := rc.Exists("to_delete")
	require.NoError(t, err)
	assert.True(t, exists)

	// Delete the key
	err = rc.Delete("to_delete")
	require.NoError(t, err)

	// Verify it's gone
	exists, err = rc.Exists("to_delete")
	require.NoError(t, err)
	assert.False(t, exists)
}

func TestRedisCache_SetNX(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	// First SetNX should succeed
	ok, err := rc.SetNX("lock:key", "value1", time.Minute)
	require.NoError(t, err)
	assert.True(t, ok)

	// Second SetNX should fail (key already exists)
	ok, err = rc.SetNX("lock:key", "value2", time.Minute)
	require.NoError(t, err)
	assert.False(t, ok)

	// Verify the original value is unchanged
	var value string
	err = rc.Get("lock:key", &value)
	require.NoError(t, err)
	assert.Equal(t, "value1", value)
}

func TestRedisCache_Increment(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	// First increment should return 1
	val, err := rc.Increment("counter")
	require.NoError(t, err)
	assert.Equal(t, int64(1), val)

	// Second increment should return 2
	val, err = rc.Increment("counter")
	require.NoError(t, err)
	assert.Equal(t, int64(2), val)
}

func TestRedisCache_RepositoryMetadata(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	type RepoMetadata struct {
		Stars int
		Forks int
		Lang  string
	}

	metadata := RepoMetadata{
		Stars: 100,
		Forks: 50,
		Lang:  "Go",
	}

	// Cache repository metadata
	err := rc.CacheRepositoryMetadata("user/repo", metadata, time.Minute)
	require.NoError(t, err)

	// Retrieve repository metadata
	var retrieved RepoMetadata
	err = rc.GetRepositoryMetadata("user/repo", &retrieved)
	require.NoError(t, err)
	assert.Equal(t, metadata.Stars, retrieved.Stars)
	assert.Equal(t, metadata.Forks, retrieved.Forks)
	assert.Equal(t, metadata.Lang, retrieved.Lang)
}

func TestRedisCache_SearchResults(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	results := []string{"repo1", "repo2", "repo3"}

	// Cache search results
	err := rc.CacheSearchResults("golang", 1, results, time.Minute)
	require.NoError(t, err)

	// Retrieve search results
	var retrieved []string
	err = rc.GetSearchResults("golang", 1, &retrieved)
	require.NoError(t, err)
	assert.Equal(t, results, retrieved)
}

func TestRedisCache_MarkAndCheckProcessed(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	repoName := "user/repo"

	// Check if repository is processed (should be false)
	processed, err := rc.IsRepositoryProcessed(repoName)
	require.NoError(t, err)
	assert.False(t, processed)

	// Mark repository as processed
	err = rc.MarkRepositoryProcessed(repoName)
	require.NoError(t, err)

	// Check again (should be true)
	processed, err = rc.IsRepositoryProcessed(repoName)
	require.NoError(t, err)
	assert.True(t, processed)
}

func TestRedisCache_Expiration(t *testing.T) {
	rc, mr := setupTestRedis(t)
	defer mr.Close()
	defer rc.Close()

	// Set a key with 1 second expiration
	err := rc.Set("temp:key", "value", time.Second)
	require.NoError(t, err)

	// Fast forward time in miniredis
	mr.FastForward(2 * time.Second)

	// Key should be expired
	var value string
	err = rc.Get("temp:key", &value)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "key not found")
}
