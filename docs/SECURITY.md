# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in CodeLupe, please follow these steps:

1. **DO NOT** open a public GitHub issue
2. Email security details to: [security@yourdomain.com] (or use GitHub Security Advisories)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and aim to release a fix within 7 days for critical vulnerabilities.

## Security Measures

### Automated Scanning

CodeLupe uses multiple automated security scanning tools:

- **Trivy**: Container vulnerability scanning
- **Snyk**: Dependency vulnerability detection
- **Semgrep**: Static application security testing (SAST)
- **CodeQL**: Advanced code analysis
- **TruffleHog**: Secret detection
- **Hadolint**: Dockerfile security linting

### CI/CD Security

All code changes go through:
1. Automated security scans
2. Dependency review
3. License compliance checks
4. SBOM generation
5. Code review by maintainers

### Dependency Management

- Automated dependency updates via Dependabot
- Weekly security audits
- License compliance checks
- Minimal dependency footprint

### Container Security

- Base images from official sources (NVIDIA CUDA)
- Regular base image updates
- Minimal container attack surface
- Non-root user execution where possible
- Read-only filesystems where applicable

### Data Security

- No hardcoded credentials
- Environment variable-based configuration
- PostgreSQL connection encryption support
- API token rotation support

## Security Best Practices for Users

### 1. Environment Variables

Never commit sensitive data:

```bash
# ✅ Good - use environment variables
export GITHUB_TOKEN="your_token"
export DATABASE_URL="postgres://user:pass@host/db"

# ❌ Bad - hardcoded in code
token = "ghp_xxx"
```

### 2. Network Security

```yaml
# docker-compose.yml - restrict network access
services:
  postgres:
    networks:
      - internal
networks:
  internal:
    internal: true  # No external access
```

### 3. Database Security

```bash
# Use strong passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Enable SSL connections
POSTGRES_SSL_MODE=require
```

### 4. Docker Security

```dockerfile
# Run as non-root user
USER appuser

# Read-only root filesystem
--read-only
--tmpfs /tmp

# Drop capabilities
--cap-drop=ALL
```

## Known Security Considerations

### GitHub Token Permissions

The GitHub token used for crawling should have:
- ✅ `public_repo` (read-only)
- ❌ No write permissions
- ❌ No admin permissions

### Database Access

- Use dedicated database users with minimal permissions
- Enable SSL/TLS for database connections in production
- Rotate credentials regularly
- Use connection pooling with limits

### API Rate Limiting

- Implement rate limiting for all external APIs
- Use circuit breakers to prevent cascading failures
- Monitor rate limit usage

## Security Checklist for Production

- [ ] All environment variables set via secrets management
- [ ] Database SSL/TLS enabled
- [ ] Strong, unique passwords for all services
- [ ] Network access restricted to necessary services only
- [ ] Regular security scans enabled
- [ ] Log aggregation and monitoring configured
- [ ] Backup and disaster recovery plan in place
- [ ] Incident response plan documented
- [ ] Regular security audits scheduled

## Security Audit History

| Date | Auditor | Findings | Status |
|------|---------|----------|--------|
| 2025-10-14 | Internal | Security tooling implemented | Completed |

## Updates and Patches

We follow semantic versioning and provide security updates as:
- **Critical**: Immediate patch release
- **High**: Patch within 7 days
- **Medium**: Included in next minor release
- **Low**: Included in next release

Subscribe to GitHub releases to stay informed of security updates.

## Compliance

CodeLupe follows security best practices from:
- OWASP Top 10
- CIS Docker Benchmark
- NIST Cybersecurity Framework

## Contact

For security concerns:
- Email: security@yourdomain.com
- GitHub Security Advisories: https://github.com/yourusername/codelupe/security/advisories

---

**Last Updated**: 2025-10-14
