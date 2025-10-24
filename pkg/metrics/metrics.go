package metrics

import (
	"fmt"
	"net/http"
	"sync"
	"time"
)

// Metrics holds application metrics
type Metrics struct {
	mu               sync.RWMutex
	counters         map[string]int64
	gauges           map[string]float64
	histograms       map[string][]float64
	lastUpdate       time.Time
}

// NewMetrics creates a new Metrics instance
func NewMetrics() *Metrics {
	return &Metrics{
		counters:   make(map[string]int64),
		gauges:     make(map[string]float64),
		histograms: make(map[string][]float64),
		lastUpdate: time.Now(),
	}
}

// IncrCounter increments a counter metric
func (m *Metrics) IncrCounter(name string, value int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.counters[name] += value
	m.lastUpdate = time.Now()
}

// SetGauge sets a gauge metric
func (m *Metrics) SetGauge(name string, value float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.gauges[name] = value
	m.lastUpdate = time.Now()
}

// ObserveHistogram adds an observation to a histogram
func (m *Metrics) ObserveHistogram(name string, value float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.histograms[name] = append(m.histograms[name], value)
	// Keep last 1000 observations
	if len(m.histograms[name]) > 1000 {
		m.histograms[name] = m.histograms[name][len(m.histograms[name])-1000:]
	}
	m.lastUpdate = time.Now()
}

// GetMetrics returns all metrics as a formatted string
func (m *Metrics) GetMetrics() string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := "# HELP Metrics\n"
	result += fmt.Sprintf("# Last updated: %s\n\n", m.lastUpdate.Format(time.RFC3339))

	result += "# Counters\n"
	for name, value := range m.counters {
		result += fmt.Sprintf("%s %d\n", name, value)
	}

	result += "\n# Gauges\n"
	for name, value := range m.gauges {
		result += fmt.Sprintf("%s %.2f\n", name, value)
	}

	result += "\n# Histograms (count)\n"
	for name, values := range m.histograms {
		result += fmt.Sprintf("%s_count %d\n", name, len(values))
	}

	return result
}

// ServeHTTP implements http.Handler for exposing metrics
func (m *Metrics) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprint(w, m.GetMetrics())
}

// Global metrics instance
var globalMetrics = NewMetrics()

// IncrCounter increments a global counter
func IncrCounter(name string, value int64) {
	globalMetrics.IncrCounter(name, value)
}

// SetGauge sets a global gauge
func SetGauge(name string, value float64) {
	globalMetrics.SetGauge(name, value)
}

// ObserveHistogram adds a global histogram observation
func ObserveHistogram(name string, value float64) {
	globalMetrics.ObserveHistogram(name, value)
}

// Handler returns the metrics HTTP handler
func Handler() http.Handler {
	return globalMetrics
}
