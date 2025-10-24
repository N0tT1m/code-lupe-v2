package errors

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// Example 1: Basic error creation and wrapping
func ExampleBasicUsage() {
	// Create a simple error
	err := NewValidationError("invalid repository path")
	fmt.Println(err.Error())
	// Output: [validation] invalid repository path

	// Wrap an existing error
	dbErr := sql.ErrNoRows
	wrappedErr := NewDatabaseError("failed to fetch repository", dbErr)
	fmt.Println(wrappedErr.Error())
	// Output: [database] failed to fetch repository: sql: no rows in result set
}

// Example 2: Error with context
func ExampleErrorWithContext() {
	err := NewNetworkError("failed to download repository", nil)
	err.WithContext("repo_url", "https://github.com/user/repo")
	err.WithContext("attempt", 3)
	err.WithCode("NET001")

	fmt.Printf("Error: %s\n", err.Error())
	fmt.Printf("Context: %+v\n", err.Context)
	fmt.Printf("Retryable: %v\n", err.Retryable)
}

// Example 3: Retry pattern
func ExampleRetryPattern(ctx context.Context) error {
	// Operation that might fail
	operation := func() error {
		// Simulate transient failure
		return NewTransientError("temporary network issue")
	}

	// Retry with default policy
	err := Retry(ctx, operation)
	return err
}

// Example 4: Custom retry policy
func ExampleCustomRetry(ctx context.Context) error {
	policy := &RetryPolicy{
		MaxAttempts:  3,
		InitialDelay: 500 * time.Millisecond,
		MaxDelay:     5 * time.Second,
		Multiplier:   2.0,
		Jitter:       true,
		RetryableErrors: []ErrorType{
			ErrorTypeNetwork,
			ErrorTypeRateLimit,
		},
	}

	operation := func() error {
		// Your operation here
		return nil
	}

	return RetryWithPolicy(ctx, policy, operation)
}

// Example 5: Circuit breaker pattern
func ExampleCircuitBreaker() error {
	// Create circuit breaker for external API
	cb := NewCircuitBreaker("github-api", 5, 30*time.Second)

	// Execute operation through circuit breaker
	err := cb.Execute(func() error {
		// Call external API
		return callGitHubAPI()
	})

	if err != nil {
		// Check if circuit is open
		stats := cb.GetStats()
		fmt.Printf("Circuit breaker stats: %+v\n", stats)
	}

	return err
}

// Example 6: Error tracking
func ExampleErrorTracking(db *sql.DB) error {
	tracker, err := NewErrorTracker(db)
	if err != nil {
		return err
	}

	// Track an error
	err = NewDatabaseError("connection timeout", sql.ErrConnDone)
	tracker.Track(err, "crawler")

	// Get recent errors
	recentErrors, _ := tracker.GetRecentErrors(10, "crawler")
	fmt.Printf("Found %d recent errors\n", len(recentErrors))

	// Get error statistics
	stats, _ := tracker.GetErrorStats()
	fmt.Printf("Error stats: %+v\n", stats)

	return nil
}

// Example 7: Combining retry and circuit breaker
func ExampleRetryWithCircuitBreaker(ctx context.Context) error {
	cb := NewCircuitBreaker("database", 3, 10*time.Second)
	policy := DefaultRetryPolicy()

	operation := func() error {
		return cb.Execute(func() error {
			// Database operation
			return queryDatabase()
		})
	}

	return RetryWithPolicy(ctx, policy, operation)
}

// Helper functions for examples
func callGitHubAPI() error {
	// Placeholder
	return nil
}

func queryDatabase() error {
	// Placeholder
	return nil
}
