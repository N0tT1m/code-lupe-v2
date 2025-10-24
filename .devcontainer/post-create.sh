#!/bin/bash

set -e

echo "🚀 Setting up CodeLupe development environment..."

# Install Go dependencies
echo "📦 Installing Go dependencies..."
go mod download
go mod tidy

# Install Go tools
echo "🔧 Installing Go development tools..."
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
go install golang.org/x/tools/gopls@latest
go install github.com/go-delve/delve/cmd/dlv@latest

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
fi

# Install pre-commit hooks if available
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🪝 Installing pre-commit hooks..."
    pip install pre-commit
    pre-commit install
fi

# Setup git config
echo "📝 Configuring Git..."
if [ -f ".gitmessage" ]; then
    git config commit.template .gitmessage
fi
if [ -f ".commitlintrc.json" ]; then
    echo "✅ Commitlint config detected"
fi

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 5

# Check PostgreSQL
echo "🔍 Checking PostgreSQL connection..."
until pg_isready -h postgres -p 5432 -U coding_user 2>/dev/null; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check Elasticsearch
echo "🔍 Checking Elasticsearch connection..."
until curl -sf http://elasticsearch:9200 >/dev/null; do
    echo "Waiting for Elasticsearch..."
    sleep 2
done
echo "✅ Elasticsearch is ready"

# Check Redis
echo "🔍 Checking Redis connection..."
until redis-cli -h redis -p 6379 ping 2>/dev/null | grep -q PONG; do
    echo "Waiting for Redis..."
    sleep 2
done
echo "✅ Redis is ready"

# Run database migrations if available
if [ -d "migrations" ]; then
    echo "🗄️  Running database migrations..."
    if [ -f "scripts/migrate.sh" ]; then
        bash scripts/migrate.sh || echo "⚠️  Migration failed (might be okay if already migrated)"
    fi
fi

# Build Go binaries
echo "🏗️  Building Go binaries..."
go build -o bin/codelupe ./main.go || echo "⚠️  Main build skipped"
go build -o bin/downloader ./downloader.go || echo "⚠️  Downloader build skipped"
go build -o bin/processor ./resumable_processor.go || echo "⚠️  Processor build skipped"

# Run tests
echo "🧪 Running tests..."
echo "Running Go tests..."
go test ./... -v -short || echo "⚠️  Some Go tests failed"

echo "Running Python tests..."
if [ -d "tests/python" ]; then
    pytest tests/python/ -v --tb=short || echo "⚠️  Some Python tests failed"
fi

echo ""
echo "✨ Development environment setup complete!"
echo ""
echo "📚 Quick Start:"
echo "  - Run crawler:    go run main.go"
echo "  - Run downloader: go run downloader.go download /app/repos 3"
echo "  - Run processor:  go run resumable_processor.go"
echo "  - Run API server: go run cmd/api/main.go"
echo "  - Run tests:      go test ./... -v"
echo "  - View API docs:  http://localhost:8080/api/docs"
echo ""
echo "🔗 Services:"
echo "  - PostgreSQL:     postgres:5432"
echo "  - Elasticsearch:  http://elasticsearch:9200"
echo "  - Redis:          redis:6379"
echo "  - Grafana:        http://localhost:3000"
echo "  - Kibana:         http://localhost:5601"
echo ""
