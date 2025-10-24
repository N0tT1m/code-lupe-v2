package errors

import (
	"fmt"
	"runtime"
	"time"
)

// ErrorType represents the category of error
type ErrorType string

const (
	// Transient errors - can be retried
	ErrorTypeTransient ErrorType = "transient"
	// Permanent errors - should not be retried
	ErrorTypePermanent ErrorType = "permanent"
	// User errors - caused by user input
	ErrorTypeUser ErrorType = "user"
	// System errors - internal system failures
	ErrorTypeSystem ErrorType = "system"
	// Network errors - network connectivity issues
	ErrorTypeNetwork ErrorType = "network"
	// Database errors - database operation failures
	ErrorTypeDatabase ErrorType = "database"
	// Validation errors - input validation failures
	ErrorTypeValidation ErrorType = "validation"
	// RateLimit errors - API rate limiting
	ErrorTypeRateLimit ErrorType = "rate_limit"
)

// Error represents a structured error with context
type Error struct {
	// Type categorizes the error
	Type ErrorType
	// Message is the error message
	Message string
	// Cause is the underlying error
	Cause error
	// Code is an optional error code
	Code string
	// Context provides additional context
	Context map[string]interface{}
	// Timestamp when error occurred
	Timestamp time.Time
	// File and Line where error was created
	File string
	Line int
	// Retryable indicates if the error can be retried
	Retryable bool
	// HTTPStatus is the recommended HTTP status code
	HTTPStatus int
}

// Error implements the error interface
func (e *Error) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("[%s] %s: %v", e.Type, e.Message, e.Cause)
	}
	return fmt.Sprintf("[%s] %s", e.Type, e.Message)
}

// Unwrap returns the underlying error
func (e *Error) Unwrap() error {
	return e.Cause
}

// WithContext adds context to the error
func (e *Error) WithContext(key string, value interface{}) *Error {
	if e.Context == nil {
		e.Context = make(map[string]interface{})
	}
	e.Context[key] = value
	return e
}

// WithCode sets the error code
func (e *Error) WithCode(code string) *Error {
	e.Code = code
	return e
}

// New creates a new structured error
func New(errType ErrorType, message string) *Error {
	_, file, line, _ := runtime.Caller(1)

	return &Error{
		Type:       errType,
		Message:    message,
		Timestamp:  time.Now(),
		File:       file,
		Line:       line,
		Retryable:  errType == ErrorTypeTransient || errType == ErrorTypeNetwork || errType == ErrorTypeRateLimit,
		HTTPStatus: getDefaultHTTPStatus(errType),
	}
}

// Wrap wraps an existing error with additional context
func Wrap(err error, errType ErrorType, message string) *Error {
	if err == nil {
		return nil
	}

	_, file, line, _ := runtime.Caller(1)

	// If already a structured error, preserve its properties
	if structuredErr, ok := err.(*Error); ok {
		return &Error{
			Type:       errType,
			Message:    message,
			Cause:      structuredErr,
			Timestamp:  time.Now(),
			File:       file,
			Line:       line,
			Retryable:  structuredErr.Retryable,
			HTTPStatus: structuredErr.HTTPStatus,
			Context:    structuredErr.Context,
		}
	}

	return &Error{
		Type:       errType,
		Message:    message,
		Cause:      err,
		Timestamp:  time.Now(),
		File:       file,
		Line:       line,
		Retryable:  errType == ErrorTypeTransient || errType == ErrorTypeNetwork || errType == ErrorTypeRateLimit,
		HTTPStatus: getDefaultHTTPStatus(errType),
	}
}

// getDefaultHTTPStatus returns the default HTTP status code for an error type
func getDefaultHTTPStatus(errType ErrorType) int {
	switch errType {
	case ErrorTypeUser, ErrorTypeValidation:
		return 400 // Bad Request
	case ErrorTypeRateLimit:
		return 429 // Too Many Requests
	case ErrorTypeDatabase:
		return 503 // Service Unavailable
	case ErrorTypeNetwork:
		return 502 // Bad Gateway
	case ErrorTypePermanent:
		return 500 // Internal Server Error
	case ErrorTypeSystem:
		return 500 // Internal Server Error
	default:
		return 500
	}
}

// IsRetryable checks if an error is retryable
func IsRetryable(err error) bool {
	if structuredErr, ok := err.(*Error); ok {
		return structuredErr.Retryable
	}
	return false
}

// GetType returns the error type
func GetType(err error) ErrorType {
	if structuredErr, ok := err.(*Error); ok {
		return structuredErr.Type
	}
	return ErrorTypeSystem
}

// GetContext returns the error context
func GetContext(err error) map[string]interface{} {
	if structuredErr, ok := err.(*Error); ok {
		return structuredErr.Context
	}
	return nil
}

// Common error constructors

// NewTransientError creates a transient error
func NewTransientError(message string) *Error {
	return New(ErrorTypeTransient, message)
}

// NewPermanentError creates a permanent error
func NewPermanentError(message string) *Error {
	return New(ErrorTypePermanent, message)
}

// NewDatabaseError creates a database error
func NewDatabaseError(message string, err error) *Error {
	return Wrap(err, ErrorTypeDatabase, message)
}

// NewNetworkError creates a network error
func NewNetworkError(message string, err error) *Error {
	return Wrap(err, ErrorTypeNetwork, message)
}

// NewValidationError creates a validation error
func NewValidationError(message string) *Error {
	return New(ErrorTypeValidation, message)
}

// NewRateLimitError creates a rate limit error
func NewRateLimitError(message string, retryAfter time.Duration) *Error {
	err := New(ErrorTypeRateLimit, message)
	err.WithContext("retry_after", retryAfter)
	return err
}

// NewUserError creates a user error
func NewUserError(message string) *Error {
	return New(ErrorTypeUser, message)
}

// NewSystemError creates a system error
func NewSystemError(message string, err error) *Error {
	return Wrap(err, ErrorTypeSystem, message)
}
