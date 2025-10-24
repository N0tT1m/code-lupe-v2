# CI/CD Security Guide

## Overview

CodeLupe implements a comprehensive security-enhanced CI/CD pipeline with multiple layers of automated security scanning, testing, and compliance checks.

## Security Scanning Tools

### 1. **Trivy** - Container Vulnerability Scanning
- **Purpose**: Scans Docker images for OS and library vulnerabilities
- **Severity Levels**: CRITICAL, HIGH, MEDIUM
- **Runs On**: Every push, PR, and daily at 2 AM UTC
- **Output**: SARIF format uploaded to GitHub Security tab

```yaml
# Manually run Trivy scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image codelupe-trainer:latest
```

### 2. **Snyk** - Dependency Vulnerability Scanning
- **Purpose**: Detects vulnerabilities in Go modules and Python packages
- **Threshold**: High severity and above
- **Languages**: Go, Python
- **Setup**: Requires `SNYK_TOKEN` secret

```bash
# Setup Snyk token
# 1. Sign up at https://snyk.io
# 2. Get API token from Account Settings
# 3. Add to GitHub Secrets as SNYK_TOKEN
```

### 3. **Semgrep** - Static Application Security Testing (SAST)
- **Purpose**: Finds security vulnerabilities and code quality issues
- **Rulesets**:
  - `p/security-audit` - Security best practices
  - `p/secrets` - Hardcoded secrets detection
  - `p/owasp-top-ten` - OWASP Top 10 vulnerabilities
  - `p/golang` - Go-specific security issues
  - `p/python` - Python-specific security issues
- **Output**: SARIF format with detailed findings

### 4. **CodeQL** - Advanced Code Analysis
- **Purpose**: Deep semantic code analysis
- **Languages**: Go, Python
- **Queries**: security-extended, security-and-quality
- **Features**:
  - Data flow analysis
  - Taint tracking
  - Control flow analysis
  - Cross-file analysis

### 5. **TruffleHog** - Secret Detection
- **Purpose**: Detects accidentally committed secrets
- **Scope**: Full git history
- **Verification**: Only reports verified secrets
- **Examples**: API keys, tokens, passwords, private keys

### 6. **Hadolint** - Dockerfile Linting
- **Purpose**: Best practices for Dockerfiles
- **Checks**:
  - Base image pinning
  - Layer optimization
  - Security best practices
  - Build efficiency

### 7. **Dependency Review** - PR Dependency Analysis
- **Purpose**: Reviews dependency changes in PRs
- **Checks**:
  - New vulnerabilities
  - License compliance
  - Dependency freshness
- **Blocked Licenses**: GPL-3.0, AGPL-3.0

### 8. **SBOM Generation** - Software Bill of Materials
- **Tool**: Syft + Grype
- **Format**: SPDX JSON
- **Purpose**: Complete inventory of dependencies
- **Vulnerability Scan**: Grype scans SBOM for vulnerabilities

## CI/CD Workflows

### Main CI Pipeline (`.github/workflows/ci.yml`)

Runs on every push and PR:

```
┌─────────────────────────────────────────────┐
│            CI/CD Pipeline                   │
├─────────────────────────────────────────────┤
│ 1. Go Tests                                 │
│    ├─ go vet                                │
│    ├─ golangci-lint                         │
│    ├─ Unit tests with coverage             │
│    └─ Upload coverage to Codecov           │
│                                             │
│ 2. Python Tests                             │
│    ├─ black (format check)                  │
│    ├─ ruff (linter)                         │
│    ├─ mypy (type check)                     │
│    ├─ pytest with coverage                  │
│    └─ Upload coverage to Codecov           │
│                                             │
│ 3. Migration Tests                          │
│    ├─ Start PostgreSQL                      │
│    ├─ Run migrations up                     │
│    ├─ Verify schema                         │
│    └─ Test rollback                         │
│                                             │
│ 4. Docker Build                             │
│    ├─ Build with Buildx                     │
│    ├─ Cache layers                          │
│    └─ Test image                            │
│                                             │
│ 5. Integration Tests                        │
│    ├─ Start services (Postgres, ES)        │
│    ├─ Run integration tests                 │
│    └─ Verify end-to-end                     │
│                                             │
│ 6. Build & Push (main branch only)         │
│    ├─ Build production image                │
│    ├─ Tag with commit SHA                   │
│    └─ Push to Docker Hub                    │
└─────────────────────────────────────────────┘
```

### Security Pipeline (`.github/workflows/security.yml`)

Comprehensive security scanning:

```
┌─────────────────────────────────────────────┐
│         Security Scanning Pipeline          │
├─────────────────────────────────────────────┤
│ Runs: Push, PR, Daily at 2 AM UTC          │
│                                             │
│ 1. Trivy Container Scan                     │
│ 2. Snyk Dependency Scan (Go + Python)      │
│ 3. Semgrep SAST Analysis                    │
│ 4. CodeQL Analysis (Go + Python)            │
│ 5. TruffleHog Secret Scan                   │
│ 6. License Compliance Check                 │
│ 7. SBOM Generation + Grype Scan             │
│ 8. Dockerfile Linting (Hadolint)            │
│ 9. Security Summary Report                  │
└─────────────────────────────────────────────┘
```

## Required GitHub Secrets

Add these secrets in GitHub Settings → Secrets → Actions:

| Secret | Purpose | Required |
|--------|---------|----------|
| `SNYK_TOKEN` | Snyk API authentication | Yes |
| `DOCKER_USERNAME` | Docker Hub username | For push |
| `DOCKER_PASSWORD` | Docker Hub password/token | For push |
| `CODECOV_TOKEN` | Codecov upload (optional) | No |

## Setup Instructions

### 1. Enable GitHub Security Features

```bash
# In your repository settings, enable:
# - Dependabot alerts
# - Dependabot security updates
# - Code scanning (CodeQL)
# - Secret scanning
# - Dependency graph
```

### 2. Configure Snyk

```bash
# 1. Sign up at https://snyk.io
# 2. Get API token
# 3. Add to GitHub Secrets
gh secret set SNYK_TOKEN --body "your-snyk-token"
```

### 3. Configure Docker Hub (for production)

```bash
# Add Docker Hub credentials
gh secret set DOCKER_USERNAME --body "your-username"
gh secret set DOCKER_PASSWORD --body "your-token"
```

### 4. Enable Dependabot

Dependabot is configured in `.github/dependabot.yml` and will:
- Check dependencies weekly (Mondays at 9 AM)
- Open PRs for:
  - Go modules
  - Python packages
  - Docker base images
  - GitHub Actions
- Limit 3-5 PRs per ecosystem

## Viewing Security Results

### GitHub Security Tab

All security findings are aggregated in:
```
Repository → Security → Code scanning alerts
```

View by:
- Tool (Trivy, Semgrep, CodeQL, etc.)
- Severity (Critical, High, Medium, Low)
- Status (Open, Fixed, Dismissed)

### Pull Request Checks

Each PR shows:
- ✅ Security scans passed
- ❌ Security issues found (with details)
- 📊 Dependency changes reviewed

### Artifacts

Download detailed reports:
- Trivy container scan report
- License compliance report
- SBOM (Software Bill of Materials)

## Best Practices

### 1. **Fix Security Issues Before Merging**

```bash
# Check locally before pushing
docker build -t test .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image test
```

### 2. **Review Dependabot PRs Promptly**

- Check for breaking changes
- Review changelogs
- Test locally if unsure
- Merge security updates quickly

### 3. **Don't Commit Secrets**

```bash
# Use git-secrets or pre-commit hooks
pip install pre-commit
pre-commit install

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/trufflesecurity/trufflehog
    rev: main
    hooks:
      - id: trufflehog
```

### 4. **Regular Security Audits**

```bash
# Go dependencies
go list -m all | nancy sleuth

# Python dependencies
pip install safety
safety check

# Docker images
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --severity HIGH,CRITICAL codelupe-trainer
```

## Troubleshooting

### Trivy Scan Failing

```bash
# Common issues:
# 1. Base image has critical vulnerabilities
#    → Update base image in Dockerfile
# 2. OS packages are outdated
#    → Run apt-get update && apt-get upgrade
# 3. Python packages have issues
#    → Update requirements.txt
```

### Snyk Failing

```bash
# Fix vulnerabilities:
go get -u ./...  # Update Go modules
pip install --upgrade package  # Update Python package

# Ignore false positives:
snyk ignore --id=SNYK-XXX --reason="Not applicable"
```

### CodeQL Slow

```bash
# CodeQL can take 10-30 minutes for large codebases
# To speed up:
# 1. Enable caching
# 2. Run only on main branch for scheduled scans
# 3. Use matrix strategy for parallel language scans
```

### Secret Detected

```bash
# If a secret is found in history:
# 1. Rotate the secret immediately
# 2. Remove from git history:
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/file" \
  --prune-empty --tag-name-filter cat -- --all

# 3. Or use BFG Repo-Cleaner (faster):
bfg --delete-files secret.key
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Compliance and Reporting

### Generate Security Report

```bash
# Get all security findings
gh api /repos/:owner/:repo/code-scanning/alerts > security-report.json

# Summary
gh api /repos/:owner/:repo/vulnerability-alerts --jq '.[] | {package, severity, title}'
```

### License Compliance

```bash
# Check licenses
go-licenses report ./... > licenses.txt
pip-licenses > python-licenses.txt

# Ensure compliance with your organization's policy
```

## Integration with External Tools

### Slack Notifications

```yaml
# Add to workflow
- name: Notify Slack
  uses: 8398a7/action-slack@v3
  if: failure()
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### JIRA Integration

```yaml
# Create JIRA ticket for critical findings
- name: Create JIRA issue
  if: steps.scan.outputs.critical_count > 0
  uses: atlassian/gajira-create@v3
```

## Metrics and Monitoring

Track security metrics over time:
- Number of vulnerabilities by severity
- Time to fix critical issues
- Dependency freshness
- Code coverage trends
- Security debt

## References

- [GitHub Actions Security](https://docs.github.com/en/actions/security-guides)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Snyk Documentation](https://docs.snyk.io/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)

---

**Last Updated**: 2025-10-14
