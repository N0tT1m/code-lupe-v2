package main

import (
	"database/sql"
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	_ "github.com/lib/pq"
)

func main() {
	var (
		migrationsPath string
		dbURL          string
		command        string
		steps          int
	)

	flag.StringVar(&migrationsPath, "path", "./migrations", "Path to migrations directory")
	flag.StringVar(&dbURL, "database", "", "PostgreSQL connection string")
	flag.StringVar(&command, "command", "up", "Migration command: up, down, force, version, create")
	flag.IntVar(&steps, "steps", 0, "Number of migration steps (for down command)")
	flag.Parse()

	// Get database URL from environment if not provided
	if dbURL == "" {
		dbURL = os.Getenv("DATABASE_URL")
		if dbURL == "" {
			dbURL = "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"
		}
	}

	log.Printf("🔄 Database Migrations Tool")
	log.Printf("📁 Migrations path: %s", migrationsPath)
	log.Printf("💾 Database: %s", maskPassword(dbURL))
	log.Printf("⚙️  Command: %s", command)

	// Connect to database
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	// Test connection
	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}

	// Create postgres driver instance
	driver, err := postgres.WithInstance(db, &postgres.Config{})
	if err != nil {
		log.Fatalf("Failed to create postgres driver: %v", err)
	}

	// Create migrate instance
	m, err := migrate.NewWithDatabaseInstance(
		fmt.Sprintf("file://%s", migrationsPath),
		"postgres",
		driver,
	)
	if err != nil {
		log.Fatalf("Failed to create migrate instance: %v", err)
	}

	// Execute command
	switch command {
	case "up":
		log.Println("⬆️  Running migrations up...")
		if err := m.Up(); err != nil {
			if err == migrate.ErrNoChange {
				log.Println("✅ No migrations to run (already up to date)")
			} else {
				log.Fatalf("❌ Failed to run migrations up: %v", err)
			}
		} else {
			log.Println("✅ Migrations completed successfully")
		}

	case "down":
		if steps == 0 {
			log.Println("⬇️  Rolling back all migrations...")
			if err := m.Down(); err != nil {
				if err == migrate.ErrNoChange {
					log.Println("✅ No migrations to rollback")
				} else {
					log.Fatalf("❌ Failed to rollback migrations: %v", err)
				}
			} else {
				log.Println("✅ Rollback completed successfully")
			}
		} else {
			log.Printf("⬇️  Rolling back %d migration steps...", steps)
			if err := m.Steps(-steps); err != nil {
				log.Fatalf("❌ Failed to rollback %d steps: %v", steps, err)
			} else {
				log.Printf("✅ Rolled back %d steps successfully", steps)
			}
		}

	case "version":
		version, dirty, err := m.Version()
		if err != nil {
			log.Fatalf("❌ Failed to get version: %v", err)
		}
		if dirty {
			log.Printf("📊 Current version: %d (DIRTY - migration failed)", version)
		} else {
			log.Printf("📊 Current version: %d", version)
		}

	case "force":
		if steps == 0 {
			log.Fatal("❌ Must specify version with -steps flag for force command")
		}
		log.Printf("⚠️  Forcing version to %d...", steps)
		if err := m.Force(steps); err != nil {
			log.Fatalf("❌ Failed to force version: %v", err)
		}
		log.Printf("✅ Forced version to %d", steps)

	case "drop":
		log.Println("⚠️  Dropping all tables...")
		if err := m.Drop(); err != nil {
			log.Fatalf("❌ Failed to drop tables: %v", err)
		}
		log.Println("✅ All tables dropped successfully")

	default:
		log.Fatalf("❌ Unknown command: %s (use: up, down, version, force, drop)", command)
	}
}

// maskPassword masks the password in the connection string for logging
func maskPassword(dbURL string) string {
	// Simple mask: replace password between :// and @
	start := 0
	end := len(dbURL)

	// Find ://
	for i := 0; i < len(dbURL)-3; i++ {
		if dbURL[i:i+3] == "://" {
			start = i + 3
			break
		}
	}

	// Find @ after ://
	for i := start; i < len(dbURL); i++ {
		if dbURL[i] == '@' {
			end = i
			break
		}
	}

	if start > 0 && end < len(dbURL) {
		// Find : before @
		for i := start; i < end; i++ {
			if dbURL[i] == ':' {
				return dbURL[:i+1] + "****" + dbURL[end:]
			}
		}
	}

	return dbURL
}
