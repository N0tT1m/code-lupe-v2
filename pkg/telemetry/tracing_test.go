package telemetry

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
)

func TestNewTracerProvider_Jaeger(t *testing.T) {
	// Skip if Jaeger is not available
	t.Skip("Skipping Jaeger test - requires running Jaeger instance")

	cfg := TracerConfig{
		ServiceName:    "test-service",
		ServiceVersion: "1.0.0",
		Environment:    "test",
		ExporterType:   "jaeger",
		JaegerEndpoint: "http://localhost:14268/api/traces",
		SamplingRatio:  1.0,
	}

	tp, err := NewTracerProvider(cfg)
	require.NoError(t, err)
	assert.NotNil(t, tp)

	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		tp.Shutdown(ctx)
	}()
}

func TestNewTracerProvider_OTLP(t *testing.T) {
	// Skip if OTLP collector is not available
	t.Skip("Skipping OTLP test - requires running OTLP collector")

	cfg := TracerConfig{
		ServiceName:    "test-service",
		ServiceVersion: "1.0.0",
		Environment:    "test",
		ExporterType:   "otlp",
		OTLPEndpoint:   "localhost:4317",
		SamplingRatio:  1.0,
	}

	tp, err := NewTracerProvider(cfg)
	require.NoError(t, err)
	assert.NotNil(t, tp)

	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		tp.Shutdown(ctx)
	}()
}

func TestTracerProvider_StartSpan(t *testing.T) {
	// Create in-memory exporter for testing
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")
	span.End()

	// Verify span was created
	spans := exporter.GetSpans()
	assert.Len(t, spans, 1)
	assert.Equal(t, "test-span", spans[0].Name)
}

func TestAddSpanAttributes(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")

	AddSpanAttributes(ctx,
		attribute.String("key1", "value1"),
		attribute.Int("key2", 42),
	)

	span.End()

	// Verify attributes
	spans := exporter.GetSpans()
	require.Len(t, spans, 1)

	attrs := spans[0].Attributes
	assert.Contains(t, attrs, attribute.String("key1", "value1"))
	assert.Contains(t, attrs, attribute.Int("key2", 42))
}

func TestAddSpanEvent(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")

	AddSpanEvent(ctx, "test-event",
		attribute.String("event-key", "event-value"),
	)

	span.End()

	// Verify event
	spans := exporter.GetSpans()
	require.Len(t, spans, 1)

	events := spans[0].Events
	require.Len(t, events, 1)
	assert.Equal(t, "test-event", events[0].Name)
}

func TestRecordError(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")

	testErr := errors.New("test error")
	RecordError(ctx, testErr)

	span.End()

	// Verify error was recorded
	spans := exporter.GetSpans()
	require.Len(t, spans, 1)

	// Check for error attribute
	attrs := spans[0].Attributes
	assert.Contains(t, attrs, attribute.Bool("error", true))

	// Check for error event
	events := spans[0].Events
	require.Greater(t, len(events), 0)
	assert.Equal(t, "exception", events[0].Name)
}

func TestTraceFunction(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()

	// Test successful function
	err := TraceFunction(ctx, tracer, "test-function", func(ctx context.Context) error {
		AddSpanAttributes(ctx, attribute.String("operation", "success"))
		return nil
	})

	assert.NoError(t, err)

	spans := exporter.GetSpans()
	require.Len(t, spans, 1)
	assert.Equal(t, "test-function", spans[0].Name)

	// Reset exporter
	exporter.Reset()

	// Test function with error
	testErr := errors.New("function error")
	err = TraceFunction(ctx, tracer, "test-function-error", func(ctx context.Context) error {
		return testErr
	})

	assert.Error(t, err)
	assert.Equal(t, testErr, err)

	spans = exporter.GetSpans()
	require.Len(t, spans, 1)
	assert.Equal(t, "test-function-error", spans[0].Name)

	// Verify error was recorded
	attrs := spans[0].Attributes
	assert.Contains(t, attrs, attribute.Bool("error", true))
}

func TestGetTraceID(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()

	// Without span, should return empty string
	traceID := GetTraceID(ctx)
	assert.Empty(t, traceID)

	// With span, should return trace ID
	ctx, span := tracer.Start(ctx, "test-span")
	traceID = GetTraceID(ctx)
	assert.NotEmpty(t, traceID)

	span.End()
}

func TestGetSpanID(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()

	// Without span, should return empty string
	spanID := GetSpanID(ctx)
	assert.Empty(t, spanID)

	// With span, should return span ID
	ctx, span := tracer.Start(ctx, "test-span")
	spanID = GetSpanID(ctx)
	assert.NotEmpty(t, spanID)

	span.End()
}

func TestSpanLogger(t *testing.T) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("test-tracer")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")

	logger := NewSpanLogger(ctx)

	// Test Info logging
	logger.Info("test info message", attribute.String("info-key", "info-value"))

	// Test Error logging
	testErr := errors.New("test error")
	logger.Error("test error message", testErr, attribute.String("error-key", "error-value"))

	span.End()

	// Verify events were added
	spans := exporter.GetSpans()
	require.Len(t, spans, 1)

	events := spans[0].Events
	assert.Greater(t, len(events), 0)
}

func BenchmarkStartSpan(b *testing.B) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("benchmark-tracer")
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, span := tracer.Start(ctx, "benchmark-span")
		span.End()
	}
}

func BenchmarkAddSpanAttributes(b *testing.B) {
	exporter := tracetest.NewInMemoryExporter()

	tp := trace.NewTracerProvider(
		trace.WithSyncer(exporter),
	)

	tracer := tp.Tracer("benchmark-tracer")
	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "benchmark-span")
	defer span.End()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		AddSpanAttributes(ctx,
			attribute.String("key1", "value1"),
			attribute.Int("key2", 42),
		)
	}
}
