package circuitbreaker

import (
	"context"
	"errors"
	"sync"
	"time"
)

// State represents the circuit breaker state
type State int

const (
	// StateClosed allows requests through
	StateClosed State = iota
	// StateOpen blocks requests
	StateOpen
	// StateHalfOpen allows limited requests through to test recovery
	StateHalfOpen
)

// String returns the string representation of the state
func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}

var (
	// ErrCircuitOpen is returned when the circuit breaker is open
	ErrCircuitOpen = errors.New("circuit breaker is open")
	// ErrTooManyRequests is returned when too many requests are in half-open state
	ErrTooManyRequests = errors.New("too many requests in half-open state")
)

// Config holds circuit breaker configuration
type Config struct {
	// MaxFailures is the maximum number of failures before opening the circuit
	MaxFailures uint32
	// Timeout is how long to wait before attempting to close an open circuit
	Timeout time.Duration
	// MaxRequests is the maximum number of requests allowed in half-open state
	MaxRequests uint32
	// OnStateChange is called when the circuit breaker state changes
	OnStateChange func(from, to State)
}

// CircuitBreaker implements the circuit breaker pattern
type CircuitBreaker struct {
	config Config
	state  State
	mu     sync.RWMutex

	failures      uint32
	requests      uint32
	lastFailTime  time.Time
	lastStateTime time.Time
}

// New creates a new circuit breaker
func New(config Config) *CircuitBreaker {
	if config.MaxFailures == 0 {
		config.MaxFailures = 5
	}
	if config.Timeout == 0 {
		config.Timeout = 60 * time.Second
	}
	if config.MaxRequests == 0 {
		config.MaxRequests = 1
	}

	return &CircuitBreaker{
		config:        config,
		state:         StateClosed,
		lastStateTime: time.Now(),
	}
}

// Execute runs the given function with circuit breaker protection
func (cb *CircuitBreaker) Execute(fn func() error) error {
	return cb.ExecuteContext(context.Background(), func(ctx context.Context) error {
		return fn()
	})
}

// ExecuteContext runs the given function with circuit breaker protection and context
func (cb *CircuitBreaker) ExecuteContext(ctx context.Context, fn func(context.Context) error) error {
	// Check if we can execute
	if err := cb.beforeRequest(); err != nil {
		return err
	}

	// Execute the function
	err := fn(ctx)

	// Record the result
	cb.afterRequest(err)

	return err
}

// beforeRequest checks if a request can be executed
func (cb *CircuitBreaker) beforeRequest() error {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case StateClosed:
		// Allow request
		return nil

	case StateOpen:
		// Check if timeout has passed
		if time.Since(cb.lastFailTime) > cb.config.Timeout {
			cb.setState(StateHalfOpen)
			cb.requests = 0
			return nil
		}
		return ErrCircuitOpen

	case StateHalfOpen:
		// Check if we've exceeded max requests in half-open state
		if cb.requests >= cb.config.MaxRequests {
			return ErrTooManyRequests
		}
		cb.requests++
		return nil

	default:
		return ErrCircuitOpen
	}
}

// afterRequest records the result of a request
func (cb *CircuitBreaker) afterRequest(err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		// Request failed
		cb.failures++
		cb.lastFailTime = time.Now()

		if cb.state == StateHalfOpen {
			// Failure in half-open state -> back to open
			cb.setState(StateOpen)
		} else if cb.failures >= cb.config.MaxFailures {
			// Too many failures -> open the circuit
			cb.setState(StateOpen)
		}
	} else {
		// Request succeeded
		if cb.state == StateHalfOpen {
			// Success in half-open -> close the circuit
			cb.setState(StateClosed)
		}
		// Reset failure count on success
		cb.failures = 0
	}
}

// setState changes the circuit breaker state
func (cb *CircuitBreaker) setState(newState State) {
	oldState := cb.state
	cb.state = newState
	cb.lastStateTime = time.Now()

	if cb.config.OnStateChange != nil && oldState != newState {
		go cb.config.OnStateChange(oldState, newState)
	}
}

// State returns the current circuit breaker state
func (cb *CircuitBreaker) State() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// Failures returns the current failure count
func (cb *CircuitBreaker) Failures() uint32 {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.failures
}

// Reset resets the circuit breaker to closed state
func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.setState(StateClosed)
	cb.failures = 0
	cb.requests = 0
}

// Stats returns circuit breaker statistics
type Stats struct {
	State         State
	Failures      uint32
	LastFailTime  time.Time
	LastStateTime time.Time
}

// Stats returns the current circuit breaker statistics
func (cb *CircuitBreaker) Stats() Stats {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	return Stats{
		State:         cb.state,
		Failures:      cb.failures,
		LastFailTime:  cb.lastFailTime,
		LastStateTime: cb.lastStateTime,
	}
}
