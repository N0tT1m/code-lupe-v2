package secrets

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadSecret_FromFile(t *testing.T) {
	// Create temporary secret file
	tmpDir := t.TempDir()
	secretFile := filepath.Join(tmpDir, "test_secret.txt")
	secretValue := "my-secret-value"

	if err := os.WriteFile(secretFile, []byte(secretValue), 0600); err != nil {
		t.Fatal(err)
	}

	// Set environment variable pointing to file
	os.Setenv("TEST_SECRET_FILE", secretFile)
	defer os.Unsetenv("TEST_SECRET_FILE")

	value, err := ReadSecret("TEST_SECRET")
	if err != nil {
		t.Fatalf("ReadSecret failed: %v", err)
	}

	if value != secretValue {
		t.Errorf("Expected %q, got %q", secretValue, value)
	}
}

func TestReadSecret_FromEnv(t *testing.T) {
	secretValue := "env-secret-value"
	os.Setenv("TEST_SECRET", secretValue)
	defer os.Unsetenv("TEST_SECRET")

	value, err := ReadSecret("TEST_SECRET")
	if err != nil {
		t.Fatalf("ReadSecret failed: %v", err)
	}

	if value != secretValue {
		t.Errorf("Expected %q, got %q", secretValue, value)
	}
}

func TestReadSecret_NotFound(t *testing.T) {
	_, err := ReadSecret("NONEXISTENT_SECRET")
	if err == nil {
		t.Error("Expected error for non-existent secret")
	}
}

func TestReadSecretOrDefault(t *testing.T) {
	defaultValue := "default-value"

	// Test with non-existent secret
	value := ReadSecretOrDefault("NONEXISTENT_SECRET", defaultValue)
	if value != defaultValue {
		t.Errorf("Expected default %q, got %q", defaultValue, value)
	}

	// Test with existing secret
	os.Setenv("EXISTING_SECRET", "actual-value")
	defer os.Unsetenv("EXISTING_SECRET")

	value = ReadSecretOrDefault("EXISTING_SECRET", defaultValue)
	if value != "actual-value" {
		t.Errorf("Expected %q, got %q", "actual-value", value)
	}
}

func TestDatabaseConfig_ConnectionString(t *testing.T) {
	config := &DatabaseConfig{
		Host:     "localhost",
		Port:     "5432",
		User:     "testuser",
		Password: "testpass",
		Database: "testdb",
	}

	connStr := config.ConnectionString()
	expected := "host=localhost port=5432 user=testuser password=testpass dbname=testdb sslmode=disable"

	if connStr != expected {
		t.Errorf("Expected:\n%s\nGot:\n%s", expected, connStr)
	}
}

func TestLoadDatabaseConfig(t *testing.T) {
	// Create temporary secret files
	tmpDir := t.TempDir()

	userFile := filepath.Join(tmpDir, "db_user.txt")
	if err := os.WriteFile(userFile, []byte("testuser"), 0600); err != nil {
		t.Fatal(err)
	}

	passFile := filepath.Join(tmpDir, "db_pass.txt")
	if err := os.WriteFile(passFile, []byte("testpass"), 0600); err != nil {
		t.Fatal(err)
	}

	// Set environment variables
	os.Setenv("POSTGRES_HOST", "dbhost")
	os.Setenv("POSTGRES_PORT", "5433")
	os.Setenv("POSTGRES_DB", "mydb")
	os.Setenv("POSTGRES_USER_FILE", userFile)
	os.Setenv("POSTGRES_PASSWORD_FILE", passFile)

	defer func() {
		os.Unsetenv("POSTGRES_HOST")
		os.Unsetenv("POSTGRES_PORT")
		os.Unsetenv("POSTGRES_DB")
		os.Unsetenv("POSTGRES_USER_FILE")
		os.Unsetenv("POSTGRES_PASSWORD_FILE")
	}()

	config, err := LoadDatabaseConfig()
	if err != nil {
		t.Fatalf("LoadDatabaseConfig failed: %v", err)
	}

	if config.Host != "dbhost" {
		t.Errorf("Expected host 'dbhost', got %q", config.Host)
	}
	if config.User != "testuser" {
		t.Errorf("Expected user 'testuser', got %q", config.User)
	}
	if config.Password != "testpass" {
		t.Errorf("Expected password 'testpass', got %q", config.Password)
	}
}
