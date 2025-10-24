# Contributing to CodeLupe

Thank you for considering contributing to CodeLupe! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Code Style](#code-style)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please be respectful and professional in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/codelupe.git`
3. Add upstream remote: `git remote add upstream https://github.com/n0tt1m/codelupe.git`
4. Create a feature branch: `git checkout -b feat/your-feature-name`

## Development Setup

### Prerequisites

- Go 1.21+
- Python 3.10+
- Docker and Docker Compose
- PostgreSQL 16+
- Elasticsearch 8.11+

### Setup Steps

```bash
# Install Go dependencies
make deps

# Install Python dependencies
pip install -r requirements-test.txt

# Install development tools
make install-tools

# Start infrastructure services
docker-compose up -d elasticsearch postgres mongodb redis

# Run tests to verify setup
make test
```

## Commit Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

### Scopes

Common scopes in this project:
- `crawler`: GitHub repository crawler
- `downloader`: Repository downloader
- `processor`: Code processor
- `trainer`: Model training pipeline
- `api`: API layer
- `db`: Database related changes
- `docker`: Docker/deployment changes
- `ci`: CI/CD pipeline
- `docs`: Documentation
- `tests`: Test suite

### Examples

```bash
# Feature
git commit -m "feat(crawler): add exponential backoff for rate limiting"

# Bug fix
git commit -m "fix(trainer): resolve CUDA out of memory error"

# Documentation
git commit -m "docs(readme): update setup instructions for Windows"

# With body and footer
git commit -m "feat(api): add repository query endpoint

Implements a REST API endpoint for querying repositories
with filters for language, stars, and quality score.

Closes #123"
```

### Setting Up Commit Template

Configure git to use the commit message template:

```bash
git config --local commit.template .gitmessage
```

## Pull Request Process

1. **Update your fork**: Sync with upstream before creating a PR
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run pre-commit checks**:
   ```bash
   make pre-commit
   ```

3. **Create a Pull Request**:
   - Use a descriptive title following conventional commit format
   - Reference any related issues
   - Provide a detailed description of changes
   - Include screenshots for UI changes
   - Ensure all CI checks pass

4. **PR Title Format**:
   ```
   feat(crawler): add support for GitLab repositories
   fix(api): resolve race condition in connection pool
   docs: update API documentation
   ```

5. **PR Description Template**:
   ```markdown
   ## Description
   Brief description of changes

   ## Motivation
   Why is this change needed?

   ## Changes
   - List of changes made
   - Another change

   ## Testing
   - [ ] Unit tests added/updated
   - [ ] Integration tests pass
   - [ ] Manual testing completed

   ## Screenshots (if applicable)

   ## Related Issues
   Fixes #123
   Related to #456
   ```

## Testing Guidelines

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run only unit tests
pytest -m "not integration"

# Run only integration tests
pytest -m integration

# Run Go tests
go test -v ./...

# Run Python tests
pytest -v tests/python/
```

### Writing Tests

- **Unit tests**: Test individual functions/methods in isolation
- **Integration tests**: Test interaction between components
- **End-to-end tests**: Test complete workflows

```go
// Go test example
func TestCleanLanguageString(t *testing.T) {
    tests := []struct {
        name     string
        input    string
        expected string
    }{
        {"Simple", "Rust", "Rust"},
        {"WithPercent", "Rust 80%", "Rust"},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := cleanLanguageString(tt.input)
            if result != tt.expected {
                t.Errorf("got %q, want %q", result, tt.expected)
            }
        })
    }
}
```

```python
# Python test example
def test_quality_filter():
    """Test quality filtering logic"""
    filter = QualityFilter(min_stars=10, min_forks=3)
    repo = create_test_repo(stars=15, forks=5)

    assert filter.passes(repo) is True
```

### Test Coverage Requirements

- Aim for >60% code coverage
- Critical paths should have >80% coverage
- All new features must include tests

## Code Style

### Go

- Follow [Effective Go](https://golang.org/doc/effective_go.html)
- Use `gofmt` for formatting
- Run `golangci-lint` before committing

```bash
# Format code
make fmt

# Run linter
make lint
```

### Python

- Follow [PEP 8](https://pep8.org/)
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use `black` for formatting
- Use `mypy` for type checking

```bash
# Format Python code
black src/ tests/

# Type check
mypy src/
```

### Naming Conventions

**Go**:
- Variables: `camelCase`
- Functions: `PascalCase` for exported, `camelCase` for unexported
- Constants: `PascalCase` or `SCREAMING_SNAKE_CASE`

**Python**:
- Variables: `snake_case`
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `SCREAMING_SNAKE_CASE`

## Documentation

- Update README.md for user-facing changes
- Update ARCHITECTURE.md for architectural changes
- Add docstrings to all public functions/methods
- Update API documentation for endpoint changes
- Add inline comments for complex logic

## Questions?

Feel free to:
- Open an issue for bugs or feature requests
- Start a discussion for questions
- Contact maintainers for urgent matters

Thank you for contributing to CodeLupe! 🚀
