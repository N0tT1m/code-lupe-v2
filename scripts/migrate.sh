#!/bin/bash
# Database migration script for CodeLupe

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DATABASE_URL="${DATABASE_URL:-postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable}"
MIGRATIONS_PATH="${MIGRATIONS_PATH:-./migrations}"
COMMAND="${1:-up}"

echo -e "${BLUE}🔄 CodeLupe Database Migrations${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Function to run migrations using Docker
run_with_docker() {
    echo -e "${YELLOW}Running migrations in Docker container...${NC}"
    docker-compose exec -T postgres psql -U coding_user -d coding_db -f /tmp/migration.sql
}

# Function to run migrations using golang-migrate binary
run_with_migrate() {
    local cmd=$1
    local steps=$2

    if ! command -v migrate &> /dev/null; then
        echo -e "${RED}❌ golang-migrate not installed${NC}"
        echo -e "${YELLOW}Install with:${NC}"
        echo -e "  macOS:   brew install golang-migrate"
        echo -e "  Linux:   curl -L https://github.com/golang-migrate/migrate/releases/download/v4.16.2/migrate.linux-amd64.tar.gz | tar xvz && sudo mv migrate /usr/local/bin/"
        echo -e "  Windows: choco install migrate"
        exit 1
    fi

    case $cmd in
        up)
            echo -e "${GREEN}⬆️  Running migrations up...${NC}"
            migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" up
            ;;
        down)
            if [ -n "$steps" ]; then
                echo -e "${YELLOW}⬇️  Rolling back $steps migration(s)...${NC}"
                migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" down $steps
            else
                echo -e "${RED}⬇️  Rolling back ALL migrations...${NC}"
                read -p "Are you sure? (yes/no): " confirm
                if [ "$confirm" == "yes" ]; then
                    migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" down
                else
                    echo "Cancelled"
                    exit 0
                fi
            fi
            ;;
        version)
            echo -e "${BLUE}📊 Getting current migration version...${NC}"
            migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" version
            ;;
        force)
            if [ -z "$steps" ]; then
                echo -e "${RED}❌ Must specify version for force command${NC}"
                exit 1
            fi
            echo -e "${YELLOW}⚠️  Forcing version to $steps...${NC}"
            migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" force $steps
            ;;
        drop)
            echo -e "${RED}⚠️  This will DROP ALL TABLES${NC}"
            read -p "Are you sure? (yes/no): " confirm
            if [ "$confirm" == "yes" ]; then
                migrate -path "$MIGRATIONS_PATH" -database "$DATABASE_URL" drop
                echo -e "${GREEN}✅ All tables dropped${NC}"
            else
                echo "Cancelled"
                exit 0
            fi
            ;;
        create)
            if [ -z "$steps" ]; then
                echo -e "${RED}❌ Must specify migration name${NC}"
                echo "Usage: $0 create migration_name"
                exit 1
            fi
            echo -e "${GREEN}📝 Creating new migration: $steps${NC}"
            migrate create -ext sql -dir "$MIGRATIONS_PATH" -seq "$steps"
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $cmd${NC}"
            echo "Usage: $0 {up|down|version|force|drop|create} [steps/name]"
            exit 1
            ;;
    esac
}

# Run migrations
run_with_migrate "$COMMAND" "$2"

echo -e "${GREEN}✅ Migration operation completed${NC}"
