package errors

import (
	"context"
	"math"
	"time"
)

// RetryPolicy defines retry behavior
type RetryPolicy struct {
	MaxAttempts     int
	InitialDelay    time.Duration
	MaxDelay        time.Duration
	Multiplier      float64
	Jitter          bool
	RetryableErrors []ErrorType
}

// DefaultRetryPolicy returns a sensible default retry policy
func DefaultRetryPolicy() *RetryPolicy {
	return &RetryPolicy{
		MaxAttempts:  5,
		InitialDelay: 1 * time.Second,
		MaxDelay:     30 * time.Second,
		Multiplier:   2.0,
		Jitter:       true,
		RetryableErrors: []ErrorType{
			ErrorTypeTransient,
			ErrorTypeNetwork,
			ErrorTypeRateLimit,
		},
	}
}

// RetryWithPolicy executes a function with retry logic
func RetryWithPolicy(ctx context.Context, policy *RetryPolicy, fn func() error) error {
	var lastErr error

	for attempt := 0; attempt < policy.MaxAttempts; attempt++ {
		// Execute function
		err := fn()
		if err == nil {
			return nil
		}

		lastErr = err

		// Check if error is retryable
		if !policy.isRetryable(err) {
			return err
		}

		// Don't sleep after last attempt
		if attempt == policy.MaxAttempts-1 {
			break
		}

		// Calculate delay with exponential backoff
		delay := policy.calculateDelay(attempt)

		// Wait or check for context cancellation
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(delay):
			// Continue to next attempt
		}
	}

	return lastErr
}

// isRetryable checks if an error should be retried
func (p *RetryPolicy) isRetryable(err error) bool {
	structuredErr, ok := err.(*Error)
	if !ok {
		return false
	}

	// Check if error type is in retryable list
	for _, retryableType := range p.RetryableErrors {
		if structuredErr.Type == retryableType {
			return structuredErr.Retryable
		}
	}

	return false
}

// calculateDelay calculates the delay before next retry
func (p *RetryPolicy) calculateDelay(attempt int) time.Duration {
	delay := float64(p.InitialDelay) * math.Pow(p.Multiplier, float64(attempt))

	if delay > float64(p.MaxDelay) {
		delay = float64(p.MaxDelay)
	}

	// Add jitter to prevent thundering herd
	if p.Jitter {
		jitter := delay * 0.1 * (0.5 - float64(time.Now().UnixNano()%1000)/1000.0)
		delay += jitter
	}

	return time.Duration(delay)
}

// Retry executes a function with default retry policy
func Retry(ctx context.Context, fn func() error) error {
	return RetryWithPolicy(ctx, DefaultRetryPolicy(), fn)
}
