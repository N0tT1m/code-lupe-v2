# Contributing to CodeLupe

Thank you for your interest in contributing to CodeLupe! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Go 1.21 or later
- Docker and Docker Compose
- Make (optional, but recommended)

### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/codelupe.git
   cd codelupe
   ```

3. Install development tools:
   ```bash
   make install-tools
   ```

4. Copy environment file:
   ```bash
   cp .env.example .env
   ```

5. Start services:
   ```bash
   make docker-up
   ```

## Project Structure

```
codelupe/
├── cmd/                    # Command-line applications
│   ├── crawler/           # GitHub crawler
│   ├── downloader/        # Repository downloader
│   ├── processor/         # Code processor
│   └── metrics-exporter/  # Metrics exporter
├── internal/              # Private application code
│   ├── crawler/          # Crawler logic
│   ├── downloader/       # Downloader logic
│   ├── quality/          # Quality filtering
│   ├── storage/          # Database abstractions
│   └── models/           # Data models
├── pkg/                   # Public libraries
├── test/                  # Additional test utilities
├── .github/              # GitHub Actions workflows
└── docs/                 # Documentation
```

## Development Workflow

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Run pre-commit checks:
   ```bash
   make pre-commit
   ```

4. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. Push and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Maintenance tasks

Example:
```
feat: add quality filter for repositories

- Implement minimum star threshold
- Add language filtering
- Include pattern matching
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run specific package tests
go test -v ./internal/quality/...
```

### Writing Tests

- Place tests in `*_test.go` files
- Use table-driven tests when appropriate
- Aim for >80% code coverage
- Test edge cases and error conditions

Example:
```go
func TestFilter_Evaluate(t *testing.T) {
    tests := []struct {
        name   string
        repo   *models.RepoInfo
        passed bool
    }{
        {
            name: "high quality repo",
            repo: &models.RepoInfo{/* ... */},
            passed: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Test implementation
        })
    }
}
```

## Code Style

### Go Code Guidelines

1. **Formatting**: Use `gofmt` and `goimports`
   ```bash
   make fmt
   ```

2. **Linting**: Pass `golangci-lint` checks
   ```bash
   make lint
   ```

3. **Error Handling**:
   - Don't use `log.Fatal` in libraries
   - Return errors instead
   - Wrap errors with context using `fmt.Errorf`

   ```go
   // Bad
   if err != nil {
       log.Fatal(err)
   }

   // Good
   if err != nil {
       return fmt.Errorf("failed to process repo: %w", err)
   }
   ```

4. **Documentation**:
   - Add godoc comments for exported functions
   - Include examples where helpful

   ```go
   // Evaluate checks if a repository meets quality standards.
   // It returns an EvaluationResult containing the pass/fail status,
   // quality score, and reason for the decision.
   func (f *Filter) Evaluate(repo *models.RepoInfo) EvaluationResult {
       // ...
   }
   ```

5. **Naming**:
   - Use clear, descriptive names
   - Follow Go naming conventions
   - Avoid abbreviations unless well-known

6. **Package Organization**:
   - Keep packages focused and cohesive
   - Avoid circular dependencies
   - Use internal/ for private code

## Database Changes

When modifying database schema:

1. Create migration scripts in `postgres/migrations/`
2. Update the schema documentation
3. Test migrations in both directions (up/down)
4. Update any affected queries

## Docker

### Building Images

```bash
make docker-build
```

### Testing Locally

```bash
# Start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

## CI/CD

All pull requests must pass:

- ✅ Tests (with >80% coverage)
- ✅ Linting (golangci-lint)
- ✅ Build (all platforms)
- ✅ Security scan (gosec)

The CI pipeline runs automatically on:
- Push to `main` or `develop`
- Pull requests

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure CI passes
4. Request review from maintainers
5. Address review comments
6. Squash commits if requested

## Performance Considerations

- Profile code for bottlenecks
- Use benchmarks for critical paths:
  ```go
  func BenchmarkFilter_Evaluate(b *testing.B) {
      // Benchmark implementation
  }
  ```
- Avoid premature optimization
- Document performance-critical code

## Security

- Never commit secrets or credentials
- Use environment variables for configuration
- Validate all external inputs
- Run security scans before submitting

## Getting Help

- Check existing issues and discussions
- Join our community chat (if available)
- Tag maintainers in your PR if stuck
- Be patient and respectful

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).
