# Error Handling Guide

## Overview

CodeLupe implements a comprehensive structured error handling system with:
- **Error Taxonomy**: Categorized error types (transient, permanent, network, database, etc.)
- **Retry Logic**: Automatic retry with exponential backoff
- **Circuit Breakers**: Prevent cascading failures
- **Error Tracking**: PostgreSQL-based error logging and analysis
- **Context Preservation**: Rich error context for debugging

## Error Types

| Type | Retryable | HTTP Status | Use Case |
|------|-----------|-------------|----------|
| `ErrorTypeTransient` | ✅ Yes | 500 | Temporary failures |
| `ErrorTypeNetwork` | ✅ Yes | 502 | Network issues |
| `ErrorTypeRateLimit` | ✅ Yes | 429 | API rate limiting |
| `ErrorTypeDatabase` | ⚠️ Sometimes | 503 | Database errors |
| `ErrorTypePermanent` | ❌ No | 500 | Non-recoverable errors |
| `ErrorTypeUser` | ❌ No | 400 | User input errors |
| `ErrorTypeValidation` | ❌ No | 400 | Validation failures |
| `ErrorTypeSystem` | ❌ No | 500 | Internal errors |

## Quick Start

### Basic Usage

```go
import "codelupe/pkg/errors"

// Create a simple error
err := errors.NewValidationError("invalid repository path")

// Wrap an existing error
dbErr := sql.ErrNoRows
wrappedErr := errors.NewDatabaseError("failed to fetch repository", dbErr)

// Add context
err.WithContext("repo_url", "https://github.com/user/repo")
err.WithContext("attempt", 3)
err.WithCode("DB001")
```

### Retry Pattern

```go
import "codelupe/pkg/errors"

ctx := context.Background()

// Simple retry with defaults
err := errors.Retry(ctx, func() error {
    return downloadRepository()
})

// Custom retry policy
policy := &errors.RetryPolicy{
    MaxAttempts:  5,
    InitialDelay: 1 * time.Second,
    MaxDelay:     30 * time.Second,
    Multiplier:   2.0,
    Jitter:       true,
}

err = errors.RetryWithPolicy(ctx, policy, func() error {
    return callExternalAPI()
})
```

### Circuit Breaker

```go
// Create circuit breaker for external service
cb := errors.NewCircuitBreaker("github-api", 5, 30*time.Second)

// Execute through circuit breaker
err := cb.Execute(func() error {
    return callGitHubAPI()
})

// Check circuit state
stats := cb.GetStats()
// stats = {"state": "closed", "failures": 0, ...}
```

### Error Tracking

```go
// Initialize tracker
tracker, _ := errors.NewErrorTracker(db)

// Track errors
err := errors.NewNetworkError("download failed", originalErr)
tracker.Track(err, "downloader")

// Get recent errors
recentErrors, _ := tracker.GetRecentErrors(10, "downloader")

// Get statistics
stats, _ := tracker.GetErrorStats()
// Returns error counts by type and component
```

## Error Constructors

```go
// Create specific error types
err1 := errors.NewTransientError("temporary issue")
err2 := errors.NewPermanentError("fatal error")
err3 := errors.NewDatabaseError("query failed", sqlErr)
err4 := errors.NewNetworkError("connection timeout", netErr)
err5 := errors.NewValidationError("invalid input")
err6 := errors.NewRateLimitError("too many requests", 60*time.Second)
err7 := errors.NewUserError("missing required field")
err8 := errors.NewSystemError("internal error", sysErr)
```

## Best Practices

### 1. **Use Specific Error Types**

```go
// ✅ Good - specific error type
if repo.Stars < 10 {
    return errors.NewValidationError("repository has insufficient stars")
}

// ❌ Bad - generic error
if repo.Stars < 10 {
    return fmt.Errorf("invalid stars")
}
```

### 2. **Add Context**

```go
// ✅ Good - rich context
err := errors.NewDatabaseError("failed to insert file", dbErr)
err.WithContext("file_path", filePath)
err.WithContext("repo_id", repoID)
err.WithCode("DB_INSERT_001")

// ❌ Bad - no context
return errors.NewDatabaseError("insert failed", dbErr)
```

### 3. **Wrap Errors**

```go
// ✅ Good - preserve error chain
if err := downloadRepo(url); err != nil {
    return errors.Wrap(err, errors.ErrorTypeNetwork, "failed to download")
}

// ❌ Bad - lose original error
if err := downloadRepo(url); err != nil {
    return errors.NewNetworkError("download failed", nil)
}
```

### 4. **Use Circuit Breakers for External Services**

```go
// ✅ Good - protect against cascading failures
var githubCircuit = errors.NewCircuitBreaker("github", 5, 30*time.Second)

func callGitHub() error {
    return githubCircuit.Execute(func() error {
        return makeAPICall()
    })
}
```

### 5. **Track Important Errors**

```go
// ✅ Good - track for monitoring
if err := processFile(file); err != nil {
    tracker.Track(err, "processor")
    return err
}
```

## Integration Examples

### Crawler Integration

```go
func (c *Crawler) searchGitHub(term string) error {
    policy := &errors.RetryPolicy{
        MaxAttempts:  5,
        InitialDelay: 3 * time.Second,
        MaxDelay:     60 * time.Second,
    }

    return errors.RetryWithPolicy(c.ctx, policy, func() error {
        resp, err := c.client.Get(searchURL)
        if err != nil {
            return errors.NewNetworkError("HTTP request failed", err).
                WithContext("url", searchURL).
                WithContext("term", term)
        }

        if resp.StatusCode == 429 {
            retryAfter := parseRetryAfter(resp.Header)
            return errors.NewRateLimitError("rate limited", retryAfter).
                WithContext("endpoint", searchURL)
        }

        return nil
    })
}
```

### Database Operations

```go
var dbCircuit = errors.NewCircuitBreaker("postgres", 3, 10*time.Second)

func (p *Processor) saveFile(file *ProcessedFile) error {
    return dbCircuit.Execute(func() error {
        _, err := p.db.Exec(insertQuery, file.Content, file.Hash)
        if err != nil {
            return errors.NewDatabaseError("failed to insert file", err).
                WithContext("hash", file.Hash).
                WithContext("size", file.Size).
                WithCode("DB_INSERT_FAIL")
        }
        return nil
    })
}
```

## Error Tracking Schema

The error tracker creates the following table:

```sql
CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,           -- Error type
    message TEXT NOT NULL,         -- Error message
    code TEXT,                     -- Optional error code
    context JSONB,                 -- Additional context
    file TEXT,                     -- Source file
    line INTEGER,                  -- Source line
    cause TEXT,                    -- Underlying error
    retryable BOOLEAN,             -- Can be retried
    component TEXT NOT NULL,       -- Component name
    created_at TIMESTAMP           -- When it occurred
);
```

### Querying Errors

```sql
-- Recent errors by component
SELECT * FROM error_logs
WHERE component = 'crawler'
ORDER BY created_at DESC
LIMIT 10;

-- Error statistics (last 24 hours)
SELECT * FROM error_stats;

-- Find retryable errors
SELECT type, message, COUNT(*)
FROM error_logs
WHERE retryable = TRUE
GROUP BY type, message;
```

## Metrics Integration

Expose error metrics for Prometheus:

```go
var (
    errorCounter = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "codelupe_errors_total",
            Help: "Total number of errors by type and component",
        },
        []string{"type", "component", "retryable"},
    )
)

func trackError(err error, component string) {
    if structuredErr, ok := err.(*errors.Error); ok {
        errorCounter.WithLabelValues(
            string(structuredErr.Type),
            component,
            fmt.Sprintf("%v", structuredErr.Retryable),
        ).Inc()
    }
}
```

## Testing

```go
func TestErrorHandling(t *testing.T) {
    // Test error creation
    err := errors.NewValidationError("test error")
    assert.Equal(t, errors.ErrorTypeValidation, err.Type)
    assert.False(t, err.Retryable)

    // Test error wrapping
    cause := fmt.Errorf("original error")
    wrapped := errors.Wrap(cause, errors.ErrorTypeDatabase, "wrapped")
    assert.Equal(t, cause, wrapped.Unwrap())

    // Test retry logic
    attempts := 0
    err = errors.Retry(context.Background(), func() error {
        attempts++
        if attempts < 3 {
            return errors.NewTransientError("try again")
        }
        return nil
    })
    assert.NoError(t, err)
    assert.Equal(t, 3, attempts)
}
```

## Troubleshooting

### High Error Rates

```sql
-- Check error rate by hour
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    component,
    type,
    COUNT(*) as error_count
FROM error_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour, component, type
ORDER BY hour DESC, error_count DESC;
```

### Circuit Breaker Always Open

```go
// Check circuit state
stats := circuitBreaker.GetStats()
log.Printf("Circuit state: %+v", stats)

// Manually reset if needed
circuitBreaker.Reset()
```

### Error Context Not Captured

Ensure errors are properly wrapped:

```go
// ✅ Correct
return errors.Wrap(err, errors.ErrorTypeNetwork, "download failed")

// ❌ Wrong - creates new error without wrapping
return errors.NewNetworkError("download failed", nil)
```

## Migration from Standard Errors

```go
// Before
if err != nil {
    return fmt.Errorf("failed to process: %w", err)
}

// After
if err != nil {
    return errors.Wrap(err, errors.ErrorTypeSystem, "failed to process").
        WithContext("component", "processor").
        WithContext("file_count", fileCount)
}
```

---

**Last Updated**: 2025-10-14
