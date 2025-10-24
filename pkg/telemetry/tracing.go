package telemetry

import (
	"context"
	"fmt"
	"log"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/jaeger"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
	"go.opentelemetry.io/otel/trace"
)

// TracerConfig holds configuration for the tracer
type TracerConfig struct {
	ServiceName    string
	ServiceVersion string
	Environment    string
	ExporterType   string // "jaeger", "otlp", or "stdout"
	JaegerEndpoint string // e.g., "http://localhost:14268/api/traces"
	OTLPEndpoint   string // e.g., "localhost:4317"
	SamplingRatio  float64
}

// TracerProvider manages the OpenTelemetry tracer
type TracerProvider struct {
	provider *sdktrace.TracerProvider
	tracer   trace.Tracer
}

// NewTracerProvider creates and configures a new tracer provider
func NewTracerProvider(cfg TracerConfig) (*TracerProvider, error) {
	var exporter sdktrace.SpanExporter
	var err error

	// Create appropriate exporter based on config
	switch cfg.ExporterType {
	case "jaeger":
		exporter, err = jaeger.New(
			jaeger.WithCollectorEndpoint(jaeger.WithEndpoint(cfg.JaegerEndpoint)),
		)
		if err != nil {
			return nil, fmt.Errorf("failed to create Jaeger exporter: %w", err)
		}

	case "otlp":
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		client := otlptracegrpc.NewClient(
			otlptracegrpc.WithEndpoint(cfg.OTLPEndpoint),
			otlptracegrpc.WithInsecure(),
		)
		exporter, err = otlptrace.New(ctx, client)
		if err != nil {
			return nil, fmt.Errorf("failed to create OTLP exporter: %w", err)
		}

	default:
		return nil, fmt.Errorf("unsupported exporter type: %s", cfg.ExporterType)
	}

	// Create resource with service information
	res, err := resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(cfg.ServiceName),
			semconv.ServiceVersion(cfg.ServiceVersion),
			semconv.DeploymentEnvironment(cfg.Environment),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Configure sampling
	var sampler sdktrace.Sampler
	if cfg.SamplingRatio <= 0 {
		sampler = sdktrace.NeverSample()
	} else if cfg.SamplingRatio >= 1 {
		sampler = sdktrace.AlwaysSample()
	} else {
		sampler = sdktrace.TraceIDRatioBased(cfg.SamplingRatio)
	}

	// Create tracer provider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sampler),
	)

	// Set global tracer provider
	otel.SetTracerProvider(tp)

	// Set global propagator for distributed tracing
	otel.SetTextMapPropagator(
		propagation.NewCompositeTextMapPropagator(
			propagation.TraceContext{},
			propagation.Baggage{},
		),
	)

	return &TracerProvider{
		provider: tp,
		tracer:   tp.Tracer(cfg.ServiceName),
	}, nil
}

// Tracer returns the configured tracer
func (tp *TracerProvider) Tracer() trace.Tracer {
	return tp.tracer
}

// Shutdown gracefully shuts down the tracer provider
func (tp *TracerProvider) Shutdown(ctx context.Context) error {
	return tp.provider.Shutdown(ctx)
}

// StartSpan starts a new span with the given name and options
func (tp *TracerProvider) StartSpan(ctx context.Context, spanName string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	return tp.tracer.Start(ctx, spanName, opts...)
}

// Helper functions for common tracing patterns

// TraceFunction wraps a function with tracing
func TraceFunction(ctx context.Context, tracer trace.Tracer, funcName string, fn func(context.Context) error) error {
	ctx, span := tracer.Start(ctx, funcName)
	defer span.End()

	err := fn(ctx)
	if err != nil {
		span.RecordError(err)
		span.SetAttributes(attribute.Bool("error", true))
	}

	return err
}

// AddSpanAttributes adds attributes to the current span
func AddSpanAttributes(ctx context.Context, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(attrs...)
}

// AddSpanEvent adds an event to the current span
func AddSpanEvent(ctx context.Context, name string, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	span.AddEvent(name, trace.WithAttributes(attrs...))
}

// RecordError records an error in the current span
func RecordError(ctx context.Context, err error) {
	span := trace.SpanFromContext(ctx)
	span.RecordError(err)
	span.SetAttributes(attribute.Bool("error", true))
}

// SpanLogger provides structured logging with trace context
type SpanLogger struct {
	ctx context.Context
}

// NewSpanLogger creates a logger that includes trace context
func NewSpanLogger(ctx context.Context) *SpanLogger {
	return &SpanLogger{ctx: ctx}
}

// Info logs an info message with trace context
func (sl *SpanLogger) Info(msg string, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(sl.ctx)
	spanCtx := span.SpanContext()

	if spanCtx.IsValid() {
		log.Printf("[INFO] [trace_id=%s span_id=%s] %s", spanCtx.TraceID(), spanCtx.SpanID(), msg)
	} else {
		log.Printf("[INFO] %s", msg)
	}

	if len(attrs) > 0 {
		AddSpanEvent(sl.ctx, msg, attrs...)
	}
}

// Error logs an error message with trace context
func (sl *SpanLogger) Error(msg string, err error, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(sl.ctx)
	spanCtx := span.SpanContext()

	if spanCtx.IsValid() {
		log.Printf("[ERROR] [trace_id=%s span_id=%s] %s: %v", spanCtx.TraceID(), spanCtx.SpanID(), msg, err)
	} else {
		log.Printf("[ERROR] %s: %v", msg, err)
	}

	if err != nil {
		RecordError(sl.ctx, err)
	}

	if len(attrs) > 0 {
		AddSpanEvent(sl.ctx, msg, attrs...)
	}
}

// GetTraceID returns the trace ID from the context
func GetTraceID(ctx context.Context) string {
	span := trace.SpanFromContext(ctx)
	spanCtx := span.SpanContext()
	if spanCtx.IsValid() {
		return spanCtx.TraceID().String()
	}
	return ""
}

// GetSpanID returns the span ID from the context
func GetSpanID(ctx context.Context) string {
	span := trace.SpanFromContext(ctx)
	spanCtx := span.SpanContext()
	if spanCtx.IsValid() {
		return spanCtx.SpanID().String()
	}
	return ""
}
