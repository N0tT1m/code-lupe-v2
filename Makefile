.PHONY: help test build clean dev up down logs migrate migrate-down docker-build lint format

help:
	@echo "CodeLupe - Available Commands:"
	@echo ""
	@echo "  make help          - Show this help message"
	@echo "  make dev           - Start development environment"
	@echo "  make test          - Run all tests"
	@echo "  make lint          - Run all linters"
	@echo "  make format        - Format code"
	@echo "  make build         - Build all services"
	@echo "  make up            - Start all Docker services"
	@echo "  make down          - Stop all Docker services"
	@echo "  make logs          - Follow logs from all services"
	@echo "  make migrate       - Run database migrations"
	@echo "  make clean         - Clean build artifacts"

dev:
	@echo "Starting development environment..."
	docker-compose up -d postgres elasticsearch redis

test:
	@echo "Running tests..."
	go test -v ./...
	pytest tests/python/ -v

lint:
	@echo "Running linters..."
	golangci-lint run
	ruff check src/python/

format:
	@echo "Formatting code..."
	gofmt -w -s .
	black src/python/

build:
	@echo "Building services..."
	docker-compose build

up:
	@echo "Starting all services..."
	docker-compose up -d

down:
	@echo "Stopping all services..."
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	@echo "Running migrations..."
	migrate -path migrations/postgres -database "postgres://coding_user:coding_pass@localhost:5433/coding_db?sslmode=disable" up

clean:
	@echo "Cleaning build artifacts..."
	rm -rf bin/ build/ coverage.out
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
