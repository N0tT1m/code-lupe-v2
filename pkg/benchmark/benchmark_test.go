package benchmark

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestBenchmark_Run(t *testing.T) {
	b := New("test-benchmark").
		WithIterations(100).
		WithWarmup(10)

	counter := 0
	result := b.Run(func() error {
		counter++
		time.Sleep(1 * time.Millisecond)
		return nil
	})

	assert.NotNil(t, result)
	assert.Equal(t, "test-benchmark", result.Name)
	assert.Equal(t, int64(100), result.Operations)
	assert.Greater(t, result.OpsPerSecond, 0.0)
	assert.Equal(t, int64(0), result.ErrorCount)
}

func TestBenchmark_RunWithErrors(t *testing.T) {
	b := New("test-with-errors").
		WithIterations(100).
		WithWarmup(0)

	counter := 0
	result := b.Run(func() error {
		counter++
		if counter%10 == 0 {
			return errors.New("simulated error")
		}
		return nil
	})

	assert.NotNil(t, result)
	assert.Equal(t, int64(100), result.Operations)
	assert.Equal(t, int64(10), result.ErrorCount)
}

func TestBenchmark_RunConcurrent(t *testing.T) {
	b := New("test-concurrent").
		WithIterations(1000).
		WithConcurrency(10).
		WithWarmup(10)

	var counter int64
	result := b.Run(func() error {
		time.Sleep(1 * time.Millisecond)
		counter++
		return nil
	})

	assert.NotNil(t, result)
	assert.Equal(t, int64(1000), result.Operations)
	assert.Greater(t, result.OpsPerSecond, 0.0)
}

func TestBenchmark_RunContext(t *testing.T) {
	ctx := context.Background()
	b := New("test-context").
		WithIterations(100).
		WithWarmup(10)

	result := b.RunContext(ctx, func(ctx context.Context) error {
		time.Sleep(1 * time.Millisecond)
		return nil
	})

	assert.NotNil(t, result)
	assert.Equal(t, int64(100), result.Operations)
}

func TestBenchmark_RunContextCancellation(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	b := New("test-cancellation").
		WithIterations(1000).
		WithWarmup(0)

	result := b.RunContext(ctx, func(ctx context.Context) error {
		time.Sleep(1 * time.Millisecond)
		return nil
	})

	// Result might be nil or have fewer operations due to cancellation
	if result != nil {
		assert.Less(t, result.Operations, int64(1000))
	}
}

func TestResult_Latencies(t *testing.T) {
	b := New("test-latencies").
		WithIterations(100).
		WithWarmup(0)

	result := b.Run(func() error {
		// Variable latency
		sleep := time.Duration(1+len(b.results)%10) * time.Millisecond
		time.Sleep(sleep)
		return nil
	})

	assert.NotNil(t, result)
	assert.Greater(t, result.AvgLatency, time.Duration(0))
	assert.Greater(t, result.MinLatency, time.Duration(0))
	assert.Greater(t, result.MaxLatency, time.Duration(0))
	assert.Greater(t, result.P50Latency, time.Duration(0))
	assert.Greater(t, result.P95Latency, time.Duration(0))
	assert.Greater(t, result.P99Latency, time.Duration(0))
	assert.LessOrEqual(t, result.MinLatency, result.P50Latency)
	assert.LessOrEqual(t, result.P50Latency, result.P95Latency)
	assert.LessOrEqual(t, result.P95Latency, result.P99Latency)
	assert.LessOrEqual(t, result.P99Latency, result.MaxLatency)
}

func TestSortDurations(t *testing.T) {
	durations := []time.Duration{
		5 * time.Millisecond,
		2 * time.Millisecond,
		8 * time.Millisecond,
		1 * time.Millisecond,
		3 * time.Millisecond,
	}

	sortDurations(durations)

	assert.Equal(t, 1*time.Millisecond, durations[0])
	assert.Equal(t, 2*time.Millisecond, durations[1])
	assert.Equal(t, 3*time.Millisecond, durations[2])
	assert.Equal(t, 5*time.Millisecond, durations[3])
	assert.Equal(t, 8*time.Millisecond, durations[4])
}

func TestPercentile(t *testing.T) {
	durations := []time.Duration{
		1 * time.Millisecond,
		2 * time.Millisecond,
		3 * time.Millisecond,
		4 * time.Millisecond,
		5 * time.Millisecond,
		6 * time.Millisecond,
		7 * time.Millisecond,
		8 * time.Millisecond,
		9 * time.Millisecond,
		10 * time.Millisecond,
	}

	p50 := percentile(durations, 0.50)
	p95 := percentile(durations, 0.95)
	p99 := percentile(durations, 0.99)

	assert.Equal(t, 5*time.Millisecond, p50)
	assert.Equal(t, 9*time.Millisecond, p95)
	assert.Equal(t, 9*time.Millisecond, p99)
}

// Benchmark tests (using Go's testing.B)

func BenchmarkSimpleOperation(b *testing.B) {
	bench := New("simple-op").
		WithIterations(b.N).
		WithWarmup(0)

	result := bench.Run(func() error {
		_ = 1 + 1
		return nil
	})

	result.Print()
}

func BenchmarkWithSleep(b *testing.B) {
	bench := New("with-sleep").
		WithIterations(b.N).
		WithWarmup(0)

	result := bench.Run(func() error {
		time.Sleep(100 * time.Microsecond)
		return nil
	})

	result.Print()
}

func BenchmarkConcurrent(b *testing.B) {
	bench := New("concurrent").
		WithIterations(b.N).
		WithConcurrency(10).
		WithWarmup(0)

	result := bench.Run(func() error {
		time.Sleep(100 * time.Microsecond)
		return nil
	})

	result.Print()
}
