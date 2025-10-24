# Database Migrations

This directory contains database migration files for CodeLupe.

## Structure

```
migrations/
└── postgres/
    ├── 001_initial_schema.up.sql
    ├── 001_initial_schema.down.sql
    └── ...
```

## Using golang-migrate

### Installation

```bash
# macOS
brew install golang-migrate

# Linux
curl -L https://github.com/golang-migrate/migrate/releases/latest/download/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/migrate

# Go install
go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest
```

### Running Migrations

```bash
# Set database URL
export DATABASE_URL="postgres://coding_user:coding_pass@localhost:5433/coding_db?sslmode=disable"

# Run all pending migrations
migrate -path migrations/postgres -database "${DATABASE_URL}" up

# Rollback last migration
migrate -path migrations/postgres -database "${DATABASE_URL}" down 1

# Rollback all migrations
migrate -path migrations/postgres -database "${DATABASE_URL}" down

# Check migration status
migrate -path migrations/postgres -database "${DATABASE_URL}" version

# Force a specific version (use with caution)
migrate -path migrations/postgres -database "${DATABASE_URL}" force 1
```

### Creating New Migrations

```bash
# Create a new migration
migrate create -ext sql -dir migrations/postgres -seq add_user_table

# This creates two files:
# - 002_add_user_table.up.sql
# - 002_add_user_table.down.sql
```

## Migration Best Practices

1. **Always create both up and down migrations**
   - up.sql: Apply the change
   - down.sql: Revert the change

2. **Make migrations idempotent**
   - Use `IF EXISTS` and `IF NOT EXISTS` clauses
   - Check for existing data before modifications

3. **Test migrations thoroughly**
   - Test both up and down migrations
   - Test on a copy of production data

4. **Keep migrations atomic**
   - Each migration should be a single, logical change
   - Don't mix DDL and DML changes when possible

5. **Document breaking changes**
   - Add comments explaining why changes are needed
   - Document any data transformations

6. **Never modify existing migrations**
   - Once a migration is in production, never change it
   - Create a new migration to fix issues

## Integration with Docker

The migrations can be run automatically on container startup by adding to your Dockerfile or docker-compose.yml:

```yaml
services:
  postgres:
    # ... postgres config ...

  migrator:
    image: migrate/migrate
    volumes:
      - ./migrations/postgres:/migrations
    command: >
      -path=/migrations
      -database postgres://coding_user:coding_pass@postgres:5432/coding_db?sslmode=disable
      up
    depends_on:
      postgres:
        condition: service_healthy
```

## Migration Files

### 001_initial_schema

Creates the base schema:
- `repositories`: GitHub repository metadata
- `processed_files`: Extracted code files
- `processing_jobs`: Batch processing job tracking
- `processing_checkpoints`: Resumable processing state
- `training_state`: AI model training state

Helper functions:
- `get_download_stats()`: Repository download statistics
- `get_repos_by_language(lang)`: Filter repositories by language
- `update_updated_at_column()`: Auto-update timestamps

## Troubleshooting

### Dirty Migration State

If a migration fails partway through, the database may be in a "dirty" state:

```bash
# Check current version and dirty state
migrate -path migrations/postgres -database "${DATABASE_URL}" version

# Force to a specific version (use with caution!)
migrate -path migrations/postgres -database "${DATABASE_URL}" force 1

# Then fix and retry
migrate -path migrations/postgres -database "${DATABASE_URL}" up
```

### Connection Issues

```bash
# Test database connection
psql "${DATABASE_URL}"

# Check if postgres is running
docker-compose ps postgres
docker-compose logs postgres
```

## CI/CD Integration

Add to your CI/CD pipeline:

```yaml
- name: Run migrations
  run: |
    migrate -path migrations/postgres \\
            -database "${DATABASE_URL}" \\
            up
```
