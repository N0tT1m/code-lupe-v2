# Database Migrations Guide

## Overview

CodeLupe uses [golang-migrate](https://github.com/golang-migrate/migrate) for database schema versioning and migrations. This ensures consistent database state across environments and allows for easy rollbacks.

## Migration Files

Migrations are stored in `/migrations/` directory with the naming convention:
```
NNNNNN_description.up.sql    # Apply migration
NNNNNN_description.down.sql  # Rollback migration
```

## Current Migrations

| Version | Name | Description |
|---------|------|-------------|
| 000001 | initial_schema | Core tables (processing_jobs, processed_files, processing_checkpoints) |
| 000002 | add_repositories_table | Repositories tracking table |
| 000003 | add_training_state_table | Training state management |

## Installation

### Install golang-migrate CLI

**macOS**:
```bash
brew install golang-migrate
```

**Linux**:
```bash
curl -L https://github.com/golang-migrate/migrate/releases/download/v4.16.2/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/
```

**Windows**:
```bash
choco install migrate
```

**Docker** (no installation needed):
```bash
docker run --rm -v $(pwd)/migrations:/migrations --network host migrate/migrate \
  -path=/migrations -database "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable" up
```

## Usage

### Using the Shell Script (Recommended)

```bash
# Run all pending migrations
./scripts/migrate.sh up

# Rollback last migration
./scripts/migrate.sh down 1

# Rollback all migrations (requires confirmation)
./scripts/migrate.sh down

# Check current version
./scripts/migrate.sh version

# Force version (fix dirty state)
./scripts/migrate.sh force 3

# Drop all tables (requires confirmation)
./scripts/migrate.sh drop

# Create new migration
./scripts/migrate.sh create add_new_feature
```

### Using golang-migrate CLI Directly

```bash
# Set database URL
export DATABASE_URL="postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"

# Run migrations up
migrate -path migrations -database "$DATABASE_URL" up

# Rollback one step
migrate -path migrations -database "$DATABASE_URL" down 1

# Check version
migrate -path migrations -database "$DATABASE_URL" version

# Force version (recover from dirty state)
migrate -path migrations -database "$DATABASE_URL" force 2
```

### Using Go Migration Tool

```bash
# Build migration tool
go build -o bin/migrate cmd/migrate/main.go

# Run migrations
./bin/migrate -command up

# Rollback migrations
./bin/migrate -command down -steps 1

# Check version
./bin/migrate -command version

# Custom database URL
./bin/migrate -database "postgres://user:pass@host:port/db?sslmode=disable" -command up
```

### Using Docker

```bash
# Migrate up
docker-compose exec postgres psql -U coding_user -d coding_db -f /migrations/000001_initial_schema.up.sql

# Or using docker run
docker run --rm -v $(pwd)/migrations:/migrations --network codelupe-network \
  migrate/migrate -path=/migrations \
  -database "postgres://coding_user:coding_pass@postgres:5432/coding_db?sslmode=disable" up
```

## Creating New Migrations

### Step 1: Create Migration Files

```bash
./scripts/migrate.sh create add_new_feature
```

This creates two files:
- `migrations/NNNNNN_add_new_feature.up.sql`
- `migrations/NNNNNN_add_new_feature.down.sql`

### Step 2: Write Migration SQL

**Example - Add column**:

`000004_add_user_column.up.sql`:
```sql
ALTER TABLE processing_jobs ADD COLUMN user_id INTEGER;
CREATE INDEX idx_jobs_user ON processing_jobs(user_id);
```

`000004_add_user_column.down.sql`:
```sql
DROP INDEX IF EXISTS idx_jobs_user;
ALTER TABLE processing_jobs DROP COLUMN IF EXISTS user_id;
```

### Step 3: Test Migration

```bash
# Apply migration
./scripts/migrate.sh up

# Verify
docker-compose exec postgres psql -U coding_user -d coding_db -c "\d processing_jobs"

# Rollback if needed
./scripts/migrate.sh down 1
```

## Best Practices

### 1. **Always Create Both Up and Down**
Every migration must have both `.up.sql` and `.down.sql` files.

### 2. **Use IF EXISTS/IF NOT EXISTS**
```sql
-- Good
CREATE TABLE IF NOT EXISTS new_table (...);
DROP TABLE IF EXISTS new_table;

-- Bad
CREATE TABLE new_table (...);  -- Will fail if exists
DROP TABLE new_table;          -- Will fail if not exists
```

### 3. **Test Rollbacks**
Always test that `down` migrations work:
```bash
./scripts/migrate.sh up
./scripts/migrate.sh down 1
./scripts/migrate.sh up
```

### 4. **One Logical Change Per Migration**
Don't mix unrelated changes in one migration file.

### 5. **Never Edit Applied Migrations**
Once a migration is applied in production, create a new migration instead.

### 6. **Add Comments**
Document complex migrations:
```sql
-- Migration: Add user tracking
-- Purpose: Track which user initiated each processing job
-- Related: Issue #123
ALTER TABLE processing_jobs ADD COLUMN user_id INTEGER;
```

## Troubleshooting

### Dirty Database State

If a migration fails halfway, the database is in a "dirty" state:

```bash
# Check current state
./scripts/migrate.sh version
# Output: 2 (dirty)

# Option 1: Force to last known good version
./scripts/migrate.sh force 2

# Option 2: Manual fix in database, then force
docker-compose exec postgres psql -U coding_user -d coding_db
# Fix manually, then:
./scripts/migrate.sh force 2
```

### Migration Out of Sync

If migrations are out of sync between code and database:

```bash
# Check current version
./scripts/migrate.sh version

# Force to specific version
./scripts/migrate.sh force 3

# Then run up to apply new migrations
./scripts/migrate.sh up
```

### Cannot Connect to Database

```bash
# Check database is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U coding_user -d coding_db -c "SELECT 1"

# Check DATABASE_URL
echo $DATABASE_URL
```

## Integration with Application

### Option 1: Manual Migration (Recommended for Production)

Run migrations separately before deploying:
```bash
./scripts/migrate.sh up
docker-compose up -d
```

### Option 2: Automatic Migration (Development)

Add to Docker entrypoint:
```dockerfile
# In Dockerfile
COPY migrations /migrations
COPY scripts/migrate.sh /migrate.sh
CMD ["/bin/bash", "-c", "/migrate.sh up && /app/resumable_processor"]
```

### Option 3: Go Code Migration (Not Recommended)

Embed migrations in Go code (adds complexity):
```go
import (
    "github.com/golang-migrate/migrate/v4"
    _ "github.com/golang-migrate/migrate/v4/source/file"
)

func runMigrations() error {
    m, err := migrate.New("file://migrations", databaseURL)
    if err != nil {
        return err
    }
    return m.Up()
}
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Migrations
on: [push]
jobs:
  test-migrations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start PostgreSQL
        run: docker-compose up -d postgres

      - name: Install golang-migrate
        run: |
          curl -L https://github.com/golang-migrate/migrate/releases/download/v4.16.2/migrate.linux-amd64.tar.gz | tar xvz
          sudo mv migrate /usr/local/bin/

      - name: Run migrations
        run: ./scripts/migrate.sh up

      - name: Test rollback
        run: |
          ./scripts/migrate.sh down 1
          ./scripts/migrate.sh up
```

### Docker Compose

Add init container:
```yaml
services:
  migrate:
    image: migrate/migrate
    volumes:
      - ./migrations:/migrations
    command: ["-path=/migrations", "-database", "postgres://coding_user:coding_pass@postgres:5432/coding_db?sslmode=disable", "up"]
    depends_on:
      - postgres

  processor:
    depends_on:
      - migrate
    # ...
```

## Migration Checklist

Before applying migrations to production:

- [ ] Tested `up` migration on dev/staging
- [ ] Tested `down` migration (rollback works)
- [ ] Backed up production database
- [ ] Reviewed SQL for performance (indexes, large tables)
- [ ] Checked for breaking changes
- [ ] Notified team of schema changes
- [ ] Updated application code if needed
- [ ] Documented migration purpose and changes

## Examples

### Example 1: Add Index

`000004_add_performance_index.up.sql`:
```sql
-- Add index for faster quality score queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_files_quality_language
ON processed_files(quality_score DESC, language);

COMMENT ON INDEX idx_files_quality_language IS 'Improves query performance for quality filtering by language';
```

`000004_add_performance_index.down.sql`:
```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_files_quality_language;
```

### Example 2: Add Column with Default

`000005_add_processing_priority.up.sql`:
```sql
-- Add priority column for job scheduling
ALTER TABLE processing_jobs ADD COLUMN priority INTEGER DEFAULT 0;

-- Update existing rows
UPDATE processing_jobs SET priority = 5 WHERE status = 'pending';

-- Add index
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON processing_jobs(priority DESC, created_at);

COMMENT ON COLUMN processing_jobs.priority IS 'Job priority (0-10, higher is more important)';
```

`000005_add_processing_priority.down.sql`:
```sql
DROP INDEX IF EXISTS idx_jobs_priority;
ALTER TABLE processing_jobs DROP COLUMN IF EXISTS priority;
```

### Example 3: Data Migration

`000006_normalize_languages.up.sql`:
```sql
-- Normalize language names
UPDATE processed_files SET language = 'TypeScript' WHERE language IN ('typescript', 'ts', 'Typescript');
UPDATE processed_files SET language = 'JavaScript' WHERE language IN ('javascript', 'js', 'Javascript');
UPDATE processed_files SET language = 'Python' WHERE language IN ('python', 'py');

-- Add constraint
ALTER TABLE processed_files ADD CONSTRAINT chk_language_format
CHECK (language ~ '^[A-Z][a-zA-Z+#]*$');
```

`000006_normalize_languages.down.sql`:
```sql
ALTER TABLE processed_files DROP CONSTRAINT IF EXISTS chk_language_format;
-- Note: Cannot undo data changes, but can remove constraint
```

## References

- [golang-migrate Documentation](https://github.com/golang-migrate/migrate)
- [PostgreSQL Migration Best Practices](https://www.postgresql.org/docs/current/ddl-alter.html)
- [Database Versioning Guide](https://www.liquibase.com/resources/database-schema-versioning)

---

**Last Updated**: 2025-10-14
