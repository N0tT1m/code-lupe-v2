package benchmark

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Result represents a benchmark result
type Result struct {
	Name           string
	Duration       time.Duration
	Operations     int64
	OpsPerSecond   float64
	AvgLatency     time.Duration
	MinLatency     time.Duration
	MaxLatency     time.Duration
	P50Latency     time.Duration
	P95Latency     time.Duration
	P99Latency     time.Duration
	ErrorCount     int64
	MemAllocated   uint64
	MemAllocations uint64
}

// Benchmark represents a performance test
type Benchmark struct {
	name        string
	iterations  int
	concurrency int
	warmup      int
	results     []time.Duration
	errors      int64
	mu          sync.Mutex
}

// New creates a new benchmark
func New(name string) *Benchmark {
	return &Benchmark{
		name:        name,
		iterations:  10000,
		concurrency: 1,
		warmup:      100,
		results:     make([]time.Duration, 0),
	}
}

// WithIterations sets the number of iterations
func (b *Benchmark) WithIterations(n int) *Benchmark {
	b.iterations = n
	return b
}

// WithConcurrency sets the concurrency level
func (b *Benchmark) WithConcurrency(n int) *Benchmark {
	b.concurrency = n
	return b
}

// WithWarmup sets the number of warmup iterations
func (b *Benchmark) WithWarmup(n int) *Benchmark {
	b.warmup = n
	return b
}

// Run executes the benchmark
func (b *Benchmark) Run(fn func() error) *Result {
	// Warmup phase
	for i := 0; i < b.warmup; i++ {
		fn()
	}

	// Reset results
	b.results = make([]time.Duration, 0, b.iterations)
	b.errors = 0

	start := time.Now()

	if b.concurrency <= 1 {
		// Sequential execution
		for i := 0; i < b.iterations; i++ {
			opStart := time.Now()
			if err := fn(); err != nil {
				b.errors++
			}
			b.results = append(b.results, time.Since(opStart))
		}
	} else {
		// Concurrent execution
		b.runConcurrent(fn)
	}

	totalDuration := time.Since(start)

	return b.computeResult(totalDuration)
}

// RunContext executes the benchmark with context
func (b *Benchmark) RunContext(ctx context.Context, fn func(context.Context) error) *Result {
	// Warmup phase
	for i := 0; i < b.warmup; i++ {
		fn(ctx)
	}

	// Reset results
	b.results = make([]time.Duration, 0, b.iterations)
	b.errors = 0

	start := time.Now()

	if b.concurrency <= 1 {
		// Sequential execution
		for i := 0; i < b.iterations; i++ {
			select {
			case <-ctx.Done():
				return nil
			default:
				opStart := time.Now()
				if err := fn(ctx); err != nil {
					b.errors++
				}
				b.results = append(b.results, time.Since(opStart))
			}
		}
	} else {
		// Concurrent execution with context
		b.runConcurrentContext(ctx, fn)
	}

	totalDuration := time.Since(start)

	return b.computeResult(totalDuration)
}

// runConcurrent executes the benchmark concurrently
func (b *Benchmark) runConcurrent(fn func() error) {
	var wg sync.WaitGroup
	results := make(chan time.Duration, b.iterations)
	errors := make(chan error, b.iterations)

	iterationsPerWorker := b.iterations / b.concurrency
	remainder := b.iterations % b.concurrency

	for i := 0; i < b.concurrency; i++ {
		wg.Add(1)
		iterations := iterationsPerWorker
		if i < remainder {
			iterations++
		}

		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				start := time.Now()
				if err := fn(); err != nil {
					errors <- err
				}
				results <- time.Since(start)
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
		close(errors)
	}()

	for duration := range results {
		b.mu.Lock()
		b.results = append(b.results, duration)
		b.mu.Unlock()
	}

	for range errors {
		b.errors++
	}
}

// runConcurrentContext executes the benchmark concurrently with context
func (b *Benchmark) runConcurrentContext(ctx context.Context, fn func(context.Context) error) {
	var wg sync.WaitGroup
	results := make(chan time.Duration, b.iterations)
	errors := make(chan error, b.iterations)

	iterationsPerWorker := b.iterations / b.concurrency
	remainder := b.iterations % b.concurrency

	for i := 0; i < b.concurrency; i++ {
		wg.Add(1)
		iterations := iterationsPerWorker
		if i < remainder {
			iterations++
		}

		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				select {
				case <-ctx.Done():
					return
				default:
					start := time.Now()
					if err := fn(ctx); err != nil {
						errors <- err
					}
					results <- time.Since(start)
				}
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
		close(errors)
	}()

	for duration := range results {
		b.mu.Lock()
		b.results = append(b.results, duration)
		b.mu.Unlock()
	}

	for range errors {
		b.errors++
	}
}

// computeResult calculates statistics from the results
func (b *Benchmark) computeResult(totalDuration time.Duration) *Result {
	if len(b.results) == 0 {
		return &Result{
			Name: b.name,
		}
	}

	// Sort results for percentile calculation
	sortedResults := make([]time.Duration, len(b.results))
	copy(sortedResults, b.results)
	sortDurations(sortedResults)

	// Calculate statistics
	var totalLatency time.Duration
	minLatency := sortedResults[0]
	maxLatency := sortedResults[len(sortedResults)-1]

	for _, d := range b.results {
		totalLatency += d
	}

	avgLatency := totalLatency / time.Duration(len(b.results))
	opsPerSecond := float64(len(b.results)) / totalDuration.Seconds()

	return &Result{
		Name:         b.name,
		Duration:     totalDuration,
		Operations:   int64(len(b.results)),
		OpsPerSecond: opsPerSecond,
		AvgLatency:   avgLatency,
		MinLatency:   minLatency,
		MaxLatency:   maxLatency,
		P50Latency:   percentile(sortedResults, 0.50),
		P95Latency:   percentile(sortedResults, 0.95),
		P99Latency:   percentile(sortedResults, 0.99),
		ErrorCount:   b.errors,
	}
}

// sortDurations sorts a slice of durations in ascending order
func sortDurations(durations []time.Duration) {
	// Simple insertion sort for small slices
	for i := 1; i < len(durations); i++ {
		j := i
		for j > 0 && durations[j-1] > durations[j] {
			durations[j-1], durations[j] = durations[j], durations[j-1]
			j--
		}
	}
}

// percentile calculates the percentile value from sorted durations
func percentile(sorted []time.Duration, p float64) time.Duration {
	if len(sorted) == 0 {
		return 0
	}
	index := int(float64(len(sorted)-1) * p)
	return sorted[index]
}

// Print prints the benchmark result
func (r *Result) Print() {
	fmt.Printf("=== Benchmark: %s ===\n", r.Name)
	fmt.Printf("Duration:       %v\n", r.Duration)
	fmt.Printf("Operations:     %d\n", r.Operations)
	fmt.Printf("Ops/sec:        %.2f\n", r.OpsPerSecond)
	fmt.Printf("Avg Latency:    %v\n", r.AvgLatency)
	fmt.Printf("Min Latency:    %v\n", r.MinLatency)
	fmt.Printf("Max Latency:    %v\n", r.MaxLatency)
	fmt.Printf("P50 Latency:    %v\n", r.P50Latency)
	fmt.Printf("P95 Latency:    %v\n", r.P95Latency)
	fmt.Printf("P99 Latency:    %v\n", r.P99Latency)
	fmt.Printf("Errors:         %d (%.2f%%)\n", r.ErrorCount, float64(r.ErrorCount)/float64(r.Operations)*100)
	fmt.Println()
}

// Suite represents a collection of benchmarks
type Suite struct {
	name    string
	benches []*Benchmark
	results []*Result
}

// NewSuite creates a new benchmark suite
func NewSuite(name string) *Suite {
	return &Suite{
		name:    name,
		benches: make([]*Benchmark, 0),
		results: make([]*Result, 0),
	}
}

// Add adds a benchmark to the suite
func (s *Suite) Add(bench *Benchmark) {
	s.benches = append(s.benches, bench)
}

// Run executes all benchmarks in the suite
func (s *Suite) Run() []*Result {
	fmt.Printf("Running benchmark suite: %s\n", s.name)
	fmt.Printf("%s\n", repeatString("=", 60))

	for _, bench := range s.benches {
		// This would need to be modified to accept a function per benchmark
		// For now, this is a placeholder
		fmt.Printf("Benchmark: %s (skipped - needs function)\n", bench.name)
	}

	return s.results
}

// PrintSummary prints a summary of all benchmark results
func (s *Suite) PrintSummary() {
	fmt.Printf("\n=== Benchmark Suite Summary: %s ===\n", s.name)
	fmt.Printf("%s\n", repeatString("=", 60))

	for _, result := range s.results {
		fmt.Printf("%-30s | %10.2f ops/sec | %10v avg | %10v p99\n",
			result.Name,
			result.OpsPerSecond,
			result.AvgLatency,
			result.P99Latency,
		)
	}
	fmt.Println()
}

// repeatString repeats a string n times
func repeatString(s string, n int) string {
	result := ""
	for i := 0; i < n; i++ {
		result += s
	}
	return result
}
