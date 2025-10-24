package circuitbreaker

import (
	"errors"
	"testing"
	"time"
)

func TestCircuitBreaker_SuccessfulRequests(t *testing.T) {
	cb := New(Config{
		MaxFailures: 3,
		Timeout:     time.Second,
	})

	// Execute successful requests
	for i := 0; i < 10; i++ {
		err := cb.Execute(func() error {
			return nil
		})
		if err != nil {
			t.Errorf("Expected no error, got %v", err)
		}
	}

	if cb.State() != StateClosed {
		t.Errorf("Expected state to be Closed, got %v", cb.State())
	}
}

func TestCircuitBreaker_FailureOpensCircuit(t *testing.T) {
	cb := New(Config{
		MaxFailures: 3,
		Timeout:     time.Second,
	})

	testError := errors.New("test error")

	// Execute failing requests until circuit opens
	for i := 0; i < 3; i++ {
		err := cb.Execute(func() error {
			return testError
		})
		if err != testError {
			t.Errorf("Expected test error, got %v", err)
		}
	}

	// Circuit should now be open
	if cb.State() != StateOpen {
		t.Errorf("Expected state to be Open, got %v", cb.State())
	}

	// Next request should fail immediately with ErrCircuitOpen
	err := cb.Execute(func() error {
		t.Error("Function should not be called when circuit is open")
		return nil
	})

	if err != ErrCircuitOpen {
		t.Errorf("Expected ErrCircuitOpen, got %v", err)
	}
}

func TestCircuitBreaker_HalfOpenState(t *testing.T) {
	cb := New(Config{
		MaxFailures: 2,
		Timeout:     100 * time.Millisecond,
		MaxRequests: 1,
	})

	testError := errors.New("test error")

	// Open the circuit
	for i := 0; i < 2; i++ {
		cb.Execute(func() error { return testError })
	}

	if cb.State() != StateOpen {
		t.Errorf("Expected state to be Open, got %v", cb.State())
	}

	// Wait for timeout
	time.Sleep(150 * time.Millisecond)

	// Next request should be allowed (half-open)
	executed := false
	err := cb.Execute(func() error {
		executed = true
		return nil // Success
	})

	if err != nil {
		t.Errorf("Expected no error in half-open state, got %v", err)
	}

	if !executed {
		t.Error("Function should have been executed in half-open state")
	}

	// Circuit should close after successful request
	if cb.State() != StateClosed {
		t.Errorf("Expected state to be Closed after successful half-open request, got %v", cb.State())
	}
}

func TestCircuitBreaker_HalfOpenFailureReopens(t *testing.T) {
	cb := New(Config{
		MaxFailures: 2,
		Timeout:     100 * time.Millisecond,
		MaxRequests: 1,
	})

	testError := errors.New("test error")

	// Open the circuit
	for i := 0; i < 2; i++ {
		cb.Execute(func() error { return testError })
	}

	// Wait for timeout
	time.Sleep(150 * time.Millisecond)

	// Fail the half-open request
	cb.Execute(func() error { return testError })

	// Circuit should be open again
	if cb.State() != StateOpen {
		t.Errorf("Expected state to be Open after failed half-open request, got %v", cb.State())
	}
}

func TestCircuitBreaker_Reset(t *testing.T) {
	cb := New(Config{
		MaxFailures: 2,
		Timeout:     time.Second,
	})

	testError := errors.New("test error")

	// Open the circuit
	for i := 0; i < 2; i++ {
		cb.Execute(func() error { return testError })
	}

	if cb.State() != StateOpen {
		t.Error("Circuit should be open")
	}

	// Reset the circuit
	cb.Reset()

	if cb.State() != StateClosed {
		t.Error("Circuit should be closed after reset")
	}

	if cb.Failures() != 0 {
		t.Errorf("Expected 0 failures after reset, got %d", cb.Failures())
	}
}

func TestCircuitBreaker_StateChange_Callback(t *testing.T) {
	stateChanges := []struct {
		from State
		to   State
	}{}

	cb := New(Config{
		MaxFailures: 2,
		Timeout:     50 * time.Millisecond,
		OnStateChange: func(from, to State) {
			stateChanges = append(stateChanges, struct {
				from State
				to   State
			}{from, to})
		},
	})

	testError := errors.New("test error")

	// Open the circuit
	for i := 0; i < 2; i++ {
		cb.Execute(func() error { return testError })
	}

	// Give callback time to execute
	time.Sleep(10 * time.Millisecond)

	if len(stateChanges) != 1 {
		t.Errorf("Expected 1 state change, got %d", len(stateChanges))
	}

	if stateChanges[0].from != StateClosed || stateChanges[0].to != StateOpen {
		t.Errorf("Expected Closed->Open, got %v->%v", stateChanges[0].from, stateChanges[0].to)
	}
}

func TestCircuitBreaker_Stats(t *testing.T) {
	cb := New(Config{
		MaxFailures: 3,
		Timeout:     time.Second,
	})

	testError := errors.New("test error")

	// Generate some failures
	for i := 0; i < 2; i++ {
		cb.Execute(func() error { return testError })
	}

	stats := cb.Stats()

	if stats.State != StateClosed {
		t.Errorf("Expected state Closed, got %v", stats.State)
	}

	if stats.Failures != 2 {
		t.Errorf("Expected 2 failures, got %d", stats.Failures)
	}

	if stats.LastFailTime.IsZero() {
		t.Error("Expected LastFailTime to be set")
	}
}

func BenchmarkCircuitBreaker_Success(b *testing.B) {
	cb := New(Config{
		MaxFailures: 5,
		Timeout:     time.Second,
	})

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		cb.Execute(func() error {
			return nil
		})
	}
}

func BenchmarkCircuitBreaker_Failure(b *testing.B) {
	cb := New(Config{
		MaxFailures: 1000000, // Large number to prevent opening
		Timeout:     time.Second,
	})

	testError := errors.New("test error")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		cb.Execute(func() error {
			return testError
		})
	}
}
