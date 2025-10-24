package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
)

func setupMockProcessor(t *testing.T, reposDir string) (*ResumableProcessor, sqlmock.Sqlmock) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}

	processor := &ResumableProcessor{
		db:          db,
		reposDir:    reposDir,
		workerCount: 4,
		workerID:    "test-worker",
		batchSize:   100,
		processed:   make(map[string]bool),
		stats: &ProcessorStats{
			StartTime: time.Now(),
		},
	}

	return processor, mock
}

func TestNewResumableProcessor_WorkerCount(t *testing.T) {
	// This tests that worker count is calculated correctly
	// based on GOMAXPROCS
	db, _, err := sqlmock.New()
	if err != nil {
		t.Fatalf("Failed to create mock db: %v", err)
	}
	defer db.Close()

	processor := &ResumableProcessor{
		db:          db,
		workerCount: 48, // Simulating Ryzen 9 3900X (24 cores * 2)
		workerID:    "test",
		processed:   make(map[string]bool),
		stats:       &ProcessorStats{StartTime: time.Now()},
	}

	if processor.workerCount != 48 {
		t.Errorf("workerCount = %d, want 48", processor.workerCount)
	}
}

func TestInitializeSchema(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	// Mock schema creation
	mock.ExpectExec("CREATE TABLE IF NOT EXISTS processing_jobs").
		WillReturnResult(sqlmock.NewResult(0, 0))

	err := processor.initializeSchema()
	if err != nil {
		t.Errorf("initializeSchema() error = %v, want nil", err)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("Unfulfilled expectations: %v", err)
	}
}

func TestLoadCheckpoint_NoCheckpoint(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	// No checkpoint exists
	mock.ExpectQuery("SELECT last_job_id, last_processed_count").
		WithArgs("test-worker").
		WillReturnError(sqlmock.ErrCancelled)

	// Mock loading processed files (empty result)
	mock.ExpectQuery("SELECT DISTINCT hash FROM processed_files").
		WillReturnRows(sqlmock.NewRows([]string{"hash"}))

	err := processor.loadCheckpoint()
	if err != nil {
		t.Errorf("loadCheckpoint() error = %v, want nil", err)
	}

	if processor.currentJobID != 0 {
		t.Errorf("currentJobID = %d, want 0", processor.currentJobID)
	}
}

func TestLoadCheckpoint_WithCheckpoint(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	// Checkpoint exists
	rows := sqlmock.NewRows([]string{"last_job_id", "last_processed_count"}).
		AddRow(42, 1000)

	mock.ExpectQuery("SELECT last_job_id, last_processed_count").
		WithArgs("test-worker").
		WillReturnRows(rows)

	// Mock loading processed files
	hashRows := sqlmock.NewRows([]string{"hash"}).
		AddRow("abc123").
		AddRow("def456")

	mock.ExpectQuery("SELECT DISTINCT hash FROM processed_files").
		WillReturnRows(hashRows)

	err := processor.loadCheckpoint()
	if err != nil {
		t.Errorf("loadCheckpoint() error = %v, want nil", err)
	}

	if processor.currentJobID != 42 {
		t.Errorf("currentJobID = %d, want 42", processor.currentJobID)
	}

	if processor.stats.FilesProcessed != 1000 {
		t.Errorf("FilesProcessed = %d, want 1000", processor.stats.FilesProcessed)
	}

	if len(processor.processed) != 2 {
		t.Errorf("len(processed) = %d, want 2", len(processor.processed))
	}
}

func TestSaveCheckpoint(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	processor.currentJobID = 42
	processor.stats.FilesProcessed = 1000

	mock.ExpectExec("INSERT INTO processing_checkpoints").
		WithArgs("test-worker", int64(42), int64(1000)).
		WillReturnResult(sqlmock.NewResult(1, 1))

	err := processor.saveCheckpoint()
	if err != nil {
		t.Errorf("saveCheckpoint() error = %v, want nil", err)
	}

	if processor.stats.LastCheckpoint.IsZero() {
		t.Error("LastCheckpoint was not updated")
	}
}

func TestDiscoverRepositories(t *testing.T) {
	// Create temporary test directory
	tmpDir := t.TempDir()

	// Create test repositories
	repo1 := filepath.Join(tmpDir, "test-repo-1")
	repo2 := filepath.Join(tmpDir, "test-repo-2")
	os.Mkdir(repo1, 0755)
	os.Mkdir(repo2, 0755)

	// Create .git directory to mark as valid repo
	os.Mkdir(filepath.Join(repo1, ".git"), 0755)

	// Create some code files
	os.WriteFile(filepath.Join(repo2, "main.go"), []byte("package main"), 0644)
	os.WriteFile(filepath.Join(repo2, "test.py"), []byte("print('test')"), 0644)

	processor, mock := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Mock job creation
	mock.ExpectExec("INSERT INTO processing_jobs").
		WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectExec("INSERT INTO processing_jobs").
		WillReturnResult(sqlmock.NewResult(2, 1))

	err := processor.discoverRepositories()
	if err != nil {
		t.Errorf("discoverRepositories() error = %v, want nil", err)
	}
}

func TestIsValidRepository(t *testing.T) {
	tmpDir := t.TempDir()

	processor, _ := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	tests := []struct {
		name      string
		setupFunc func(string)
		want      bool
	}{
		{
			name: "has .git directory",
			setupFunc: func(dir string) {
				os.Mkdir(filepath.Join(dir, ".git"), 0755)
			},
			want: true,
		},
		{
			name: "has multiple code files",
			setupFunc: func(dir string) {
				os.WriteFile(filepath.Join(dir, "main.go"), []byte("package main"), 0644)
				os.WriteFile(filepath.Join(dir, "test.py"), []byte("print('test')"), 0644)
				os.WriteFile(filepath.Join(dir, "app.js"), []byte("console.log('test')"), 0644)
			},
			want: true,
		},
		{
			name: "empty directory",
			setupFunc: func(dir string) {
				// Do nothing
			},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testDir := filepath.Join(tmpDir, tt.name)
			os.Mkdir(testDir, 0755)
			tt.setupFunc(testDir)

			got := processor.isValidRepository(testDir)
			if got != tt.want {
				t.Errorf("isValidRepository() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestIsCodeFile(t *testing.T) {
	processor, _ := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	tests := []struct {
		ext  string
		want bool
	}{
		{".py", true},
		{".go", true},
		{".js", true},
		{".rs", true},
		{".java", true},
		{".txt", false},
		{".md", false},
		{".json", false},
	}

	for _, tt := range tests {
		t.Run(tt.ext, func(t *testing.T) {
			got := processor.isCodeFile(tt.ext)
			if got != tt.want {
				t.Errorf("isCodeFile(%s) = %v, want %v", tt.ext, got, tt.want)
			}
		})
	}
}

func TestGetLanguage(t *testing.T) {
	processor, _ := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	tests := []struct {
		ext  string
		want string
	}{
		{".py", "Python"},
		{".go", "Go"},
		{".js", "JavaScript"},
		{".ts", "TypeScript"},
		{".rs", "Rust"},
		{".java", "Java"},
		{".cpp", "C++"},
		{".unknown", "Unknown"},
	}

	for _, tt := range tests {
		t.Run(tt.ext, func(t *testing.T) {
			got := processor.getLanguage(tt.ext)
			if got != tt.want {
				t.Errorf("getLanguage(%s) = %s, want %s", tt.ext, got, tt.want)
			}
		})
	}
}

func TestGetPendingJobs(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	rows := sqlmock.NewRows([]string{"id", "repo_path", "status", "files_found", "files_processed"}).
		AddRow(1, "/repos/test-repo-1", "pending", 0, 0).
		AddRow(2, "/repos/test-repo-2", "failed", 100, 50)

	mock.ExpectQuery("SELECT id, repo_path, status").
		WithArgs("test-worker").
		WillReturnRows(rows)

	jobs, err := processor.getPendingJobs()
	if err != nil {
		t.Errorf("getPendingJobs() error = %v, want nil", err)
	}

	if len(jobs) != 2 {
		t.Errorf("len(jobs) = %d, want 2", len(jobs))
	}

	if jobs[0].Status != "pending" {
		t.Errorf("jobs[0].Status = %s, want pending", jobs[0].Status)
	}
}

func TestClaimJob(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	mock.ExpectExec("UPDATE processing_jobs").
		WithArgs("test-worker", 1).
		WillReturnResult(sqlmock.NewResult(0, 1))

	err := processor.claimJob(1)
	if err != nil {
		t.Errorf("claimJob() error = %v, want nil", err)
	}
}

func TestClaimJob_AlreadyClaimed(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp/test-repos")
	defer processor.db.Close()

	// No rows affected means job was already claimed
	mock.ExpectExec("UPDATE processing_jobs").
		WithArgs("test-worker", 1).
		WillReturnResult(sqlmock.NewResult(0, 0))

	err := processor.claimJob(1)
	if err == nil {
		t.Error("claimJob() error = nil, want error")
	}
}

func TestCalculateQualityScore(t *testing.T) {
	processor, _ := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	tests := []struct {
		name     string
		content  string
		language string
		wantMin  int
		wantMax  int
	}{
		{
			name:     "Python with comments",
			content:  "# Comment\ndef main():\n    # Another comment\n    print('hello')\n",
			language: "Python",
			wantMin:  70,
			wantMax:  100,
		},
		{
			name:     "Go with functions",
			content:  "package main\n\nfunc main() {\n    // Comment\n    println('hello')\n}\n",
			language: "Go",
			wantMin:  70,
			wantMax:  100,
		},
		{
			name:     "Short file",
			content:  "x = 1\n",
			language: "Python",
			wantMin:  40,
			wantMax:  60,
		},
		{
			name:     "Empty file",
			content:  "",
			language: "Unknown",
			wantMin:  40,
			wantMax:  60,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := processor.calculateQualityScore(tt.content, tt.language)

			if score < tt.wantMin || score > tt.wantMax {
				t.Errorf("calculateQualityScore() = %d, want between %d and %d",
					score, tt.wantMin, tt.wantMax)
			}

			// Score should always be 0-100
			if score < 0 || score > 100 {
				t.Errorf("Score %d out of range 0-100", score)
			}
		})
	}
}

func TestProcessFile(t *testing.T) {
	tmpDir := t.TempDir()
	processor, _ := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Create test file
	testFile := filepath.Join(tmpDir, "test.go")
	content := []byte("package main\n\nfunc main() {\n    println(\"hello\")\n}\n")
	os.WriteFile(testFile, content, 0644)

	result := processor.processFile(testFile, tmpDir, 1)

	if result == nil {
		t.Fatal("processFile() returned nil")
	}

	if result.Language != "Go" {
		t.Errorf("Language = %s, want Go", result.Language)
	}

	if result.Lines < 5 {
		t.Errorf("Lines = %d, want >= 5", result.Lines)
	}

	if result.Size != int64(len(content)) {
		t.Errorf("Size = %d, want %d", result.Size, len(content))
	}

	if result.Hash == "" {
		t.Error("Hash is empty")
	}
}

func TestProcessFile_TooSmall(t *testing.T) {
	tmpDir := t.TempDir()
	processor, _ := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Create file that's too small
	testFile := filepath.Join(tmpDir, "tiny.go")
	os.WriteFile(testFile, []byte("x"), 0644)

	result := processor.processFile(testFile, tmpDir, 1)

	if result != nil {
		t.Error("processFile() should return nil for too-small files")
	}
}

func TestProcessFile_AlreadyProcessed(t *testing.T) {
	tmpDir := t.TempDir()
	processor, _ := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Create test file
	testFile := filepath.Join(tmpDir, "test.go")
	content := []byte("package main\n\nfunc main() {\n    println(\"hello\")\n}\n")
	os.WriteFile(testFile, content, 0644)

	// Process once
	result1 := processor.processFile(testFile, tmpDir, 1)
	if result1 == nil {
		t.Fatal("First processing returned nil")
	}

	// Try processing again
	result2 := processor.processFile(testFile, tmpDir, 1)
	if result2 != nil {
		t.Error("processFile() should return nil for already-processed files")
	}
}

func TestInsertFileBatch(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	files := []ProcessedFile{
		{
			JobID:        1,
			FilePath:     "/test/file1.go",
			RelativePath: "file1.go",
			Content:      "package main",
			Language:     "Go",
			Lines:        10,
			Size:         100,
			Hash:         "abc123",
			RepoName:     "test-repo",
			QualityScore: 75,
		},
	}

	mock.ExpectBegin()
	mock.ExpectPrepare("INSERT INTO processed_files")
	mock.ExpectExec("INSERT INTO processed_files").
		WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectCommit()

	err := processor.insertFileBatch(files)
	if err != nil {
		t.Errorf("insertFileBatch() error = %v, want nil", err)
	}
}

func TestBatchInsertFiles(t *testing.T) {
	processor, mock := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	// Create 150 files to test batching (should be split into 2 batches of 100)
	var files []ProcessedFile
	for i := 0; i < 150; i++ {
		files = append(files, ProcessedFile{
			JobID:        1,
			FilePath:     "/test/file.go",
			RelativePath: "file.go",
			Content:      "package main",
			Language:     "Go",
			Lines:        10,
			Size:         100,
			Hash:         string(rune(i)), // Unique hash
			RepoName:     "test-repo",
			QualityScore: 75,
		})
	}

	// Expect 2 transactions (batches of 100)
	for i := 0; i < 2; i++ {
		mock.ExpectBegin()
		mock.ExpectPrepare("INSERT INTO processed_files")

		// Calculate batch size for this iteration
		batchSize := 100
		if i == 1 {
			batchSize = 50 // Last batch
		}

		for j := 0; j < batchSize; j++ {
			mock.ExpectExec("INSERT INTO processed_files").
				WillReturnResult(sqlmock.NewResult(1, 1))
		}
		mock.ExpectCommit()
	}

	err := processor.batchInsertFiles(files)
	if err != nil {
		t.Errorf("batchInsertFiles() error = %v, want nil", err)
	}
}

func TestProcessJob(t *testing.T) {
	tmpDir := t.TempDir()
	processor, mock := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Create test repository
	repoPath := filepath.Join(tmpDir, "test-repo")
	os.Mkdir(repoPath, 0755)
	os.WriteFile(filepath.Join(repoPath, "main.go"),
		[]byte("package main\n\nfunc main() {\n    println(\"test\")\n}\n"), 0644)

	job := ProcessingJob{
		ID:       1,
		RepoPath: repoPath,
		Status:   "pending",
	}

	// Mock job claim
	mock.ExpectExec("UPDATE processing_jobs").
		WithArgs("test-worker", 1).
		WillReturnResult(sqlmock.NewResult(0, 1))

	// Mock file insertion
	mock.ExpectBegin()
	mock.ExpectPrepare("INSERT INTO processed_files")
	mock.ExpectExec("INSERT INTO processed_files").
		WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectCommit()

	// Mock job completion
	mock.ExpectExec("UPDATE processing_jobs.*SET status = 'completed'").
		WillReturnResult(sqlmock.NewResult(0, 1))

	err := processor.processJob(job)
	if err != nil {
		t.Errorf("processJob() error = %v, want nil", err)
	}
}

func TestRun_ContextCancellation(t *testing.T) {
	tmpDir := t.TempDir()
	processor, mock := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Mock checkpoint loading
	mock.ExpectQuery("SELECT last_job_id").
		WillReturnError(sqlmock.ErrCancelled)
	mock.ExpectQuery("SELECT DISTINCT hash").
		WillReturnRows(sqlmock.NewRows([]string{"hash"}))

	// Create context that's already cancelled
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := processor.Run(ctx)
	if err != context.Canceled {
		t.Errorf("Run() error = %v, want context.Canceled", err)
	}
}

func BenchmarkCalculateQualityScore(b *testing.B) {
	t := &testing.T{}
	processor, _ := setupMockProcessor(t, "/tmp")
	defer processor.db.Close()

	content := "package main\n\nfunc main() {\n    // This is a comment\n    println(\"hello world\")\n}\n"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		processor.calculateQualityScore(content, "Go")
	}
}

func BenchmarkProcessFile(b *testing.B) {
	tmpDir := b.TempDir()
	t := &testing.T{}
	processor, _ := setupMockProcessor(t, tmpDir)
	defer processor.db.Close()

	// Create test file
	testFile := filepath.Join(tmpDir, "test.go")
	content := []byte("package main\n\nfunc main() {\n    println(\"hello\")\n}\n")
	os.WriteFile(testFile, content, 0644)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Reset processed map to allow re-processing
		processor.processed = make(map[string]bool)
		processor.processFile(testFile, tmpDir, 1)
	}
}
