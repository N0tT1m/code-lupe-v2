package logger

import (
	"os"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Logger wraps zerolog.Logger with additional methods
type Logger struct {
	zerolog.Logger
}

// Config holds logger configuration
type Config struct {
	Level   string
	Pretty  bool
	Service string
	Version string
	LogFile string
}

// New creates a new structured logger
func New(cfg Config) (*Logger, error) {
	// Parse log level
	level, err := zerolog.ParseLevel(cfg.Level)
	if err != nil {
		level = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(level)

	// Set time format
	zerolog.TimeFieldFormat = time.RFC3339Nano

	var output zerolog.LevelWriter

	if cfg.Pretty {
		// Pretty output for development
		output = zerolog.ConsoleWriter{
			Out:        os.Stdout,
			TimeFormat: time.RFC3339,
		}
	} else {
		// JSON output for production
		output = os.Stdout
	}

	// Add file output if specified
	if cfg.LogFile != "" {
		file, err := os.OpenFile(cfg.LogFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
		if err != nil {
			return nil, err
		}
		output = zerolog.MultiLevelWriter(output, file)
	}

	// Create logger with service context
	logger := zerolog.New(output).
		With().
		Timestamp().
		Str("service", cfg.Service).
		Str("version", cfg.Version).
		Logger()

	return &Logger{logger}, nil
}

// NewDefault creates a logger with default configuration
func NewDefault(service string) *Logger {
	cfg := Config{
		Level:   getEnv("LOG_LEVEL", "info"),
		Pretty:  getEnv("LOG_PRETTY", "false") == "true",
		Service: service,
		Version: getEnv("APP_VERSION", "dev"),
	}

	logger, err := New(cfg)
	if err != nil {
		// Fallback to basic logger
		l := log.With().Str("service", service).Logger()
		return &Logger{l}
	}

	return logger
}

// WithContext adds contextual fields to the logger
func (l *Logger) WithContext(fields map[string]interface{}) *Logger {
	ctx := l.With()
	for k, v := range fields {
		ctx = ctx.Interface(k, v)
	}
	newLogger := ctx.Logger()
	return &Logger{newLogger}
}

// WithField adds a single contextual field
func (l *Logger) WithField(key string, value interface{}) *Logger {
	newLogger := l.With().Interface(key, value).Logger()
	return &Logger{newLogger}
}

// WithError adds an error to the logger context
func (l *Logger) WithError(err error) *Logger {
	newLogger := l.With().Err(err).Logger()
	return &Logger{newLogger}
}

// WithRequestID adds a request ID to the logger context
func (l *Logger) WithRequestID(requestID string) *Logger {
	newLogger := l.With().Str("request_id", requestID).Logger()
	return &Logger{newLogger}
}

// Helper function to get environment variables
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// Global logger instance
var globalLogger *Logger

// Init initializes the global logger
func Init(cfg Config) error {
	logger, err := New(cfg)
	if err != nil {
		return err
	}
	globalLogger = logger
	return nil
}

// InitDefault initializes the global logger with defaults
func InitDefault(service string) {
	globalLogger = NewDefault(service)
}

// Get returns the global logger instance
func Get() *Logger {
	if globalLogger == nil {
		InitDefault("codelupe")
	}
	return globalLogger
}

// Info logs an info message
func Info(msg string) {
	Get().Info().Msg(msg)
}

// Debug logs a debug message
func Debug(msg string) {
	Get().Debug().Msg(msg)
}

// Warn logs a warning message
func Warn(msg string) {
	Get().Warn().Msg(msg)
}

// Error logs an error message
func Error(msg string) {
	Get().Error().Msg(msg)
}

// Fatal logs a fatal message and exits
func Fatal(msg string) {
	Get().Fatal().Msg(msg)
}

// WithContext creates a logger with contextual fields
func WithContext(fields map[string]interface{}) *Logger {
	return Get().WithContext(fields)
}

// WithField creates a logger with a single contextual field
func WithField(key string, value interface{}) *Logger {
	return Get().WithField(key, value)
}

// WithError creates a logger with an error context
func WithError(err error) *Logger {
	return Get().WithError(err)
}
