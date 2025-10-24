package main

import (
	"bufio"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
	"unicode/utf8"
)

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// FileResult represents a processed code file
type FileResult struct {
	Content  string `json:"text"`
	Language string `json:"language"`
	Lines    int    `json:"lines"`
	Size     int64  `json:"size"`
	Hash     string `json:"hash"`
	Path     string `json:"path"`
}

// TrainingData represents the final training format
type TrainingData struct {
	Text string `json:"text"`
	Meta struct {
		Language string `json:"language"`
		Lines    int    `json:"lines"`
		Path     string `json:"path"`
		Size     int64  `json:"size"`
	} `json:"meta"`
}

// ProcessorStats tracks processing statistics
type ProcessorStats struct {
	FilesProcessed int64
	BytesProcessed int64
	ReposProcessed int64
	ErrorCount     int64
	StartTime      time.Time
	LanguageCount  map[string]int64
	mu             sync.RWMutex
}

// UltraFastProcessor optimized for Ryzen 9 3900X
type UltraFastProcessor struct {
	reposDir       string
	workerCount    int
	stats          *ProcessorStats
	codeExtensions map[string]string
	skipDirs       map[string]bool
	maxFileSize    int64
	minFileSize    int64
}

// NewUltraFastProcessor creates optimized processor
func NewUltraFastProcessor(reposDir string) *UltraFastProcessor {
	// Optimize for Ryzen 9 3900X (24 threads)
	workerCount := runtime.GOMAXPROCS(0) * 4 // 96 workers for maximum throughput
	if workerCount > 128 {
		workerCount = 128 // Cap at 128 to avoid resource exhaustion
	}

	fmt.Printf("🚀 Ultra-Fast Go Processor - %d CPU cores detected\n", runtime.GOMAXPROCS(0))
	fmt.Printf("🔥 Using %d worker goroutines for MAXIMUM SPEED\n", workerCount)

	return &UltraFastProcessor{
		reposDir:    reposDir,
		workerCount: workerCount,
		stats: &ProcessorStats{
			StartTime:     time.Now(),
			LanguageCount: make(map[string]int64),
		},
		codeExtensions: map[string]string{
			".py":    "Python",
			".js":    "JavaScript",
			".ts":    "TypeScript",
			".jsx":   "JavaScript",
			".tsx":   "TypeScript",
			".java":  "Java",
			".cpp":   "C++",
			".c":     "C",
			".h":     "C/C++",
			".cs":    "C#",
			".php":   "PHP",
			".rb":    "Ruby",
			".go":    "Go",
			".rs":    "Rust",
			".swift": "Swift",
			".kt":    "Kotlin",
			".scala": "Scala",
			".sh":    "Shell",
			".sql":   "SQL",
			".r":     "R",
			".m":     "Objective-C",
			".pl":    "Perl",
			".lua":   "Lua",
			".dart":  "Dart",
			".vim":   "Vim",
			".sol":   "Solidity",
			".asm":   "Assembly",
		},
		skipDirs: map[string]bool{
			".git":          true,
			".svn":          true,
			".hg":           true,
			"node_modules":  true,
			"__pycache__":   true,
			".pytest_cache": true,
			"target":        true,
			"build":         true,
			"dist":          true,
			".gradle":       true,
			"bin":           true,
			"obj":           true,
			".idea":         true,
			".vscode":       true,
			"vendor":        true,
			"Pods":          true,
			".pub-cache":    true,
		},
		maxFileSize: 1024 * 1024, // 1MB max
		minFileSize: 100,         // 100 bytes min
	}
}

// scanRepositories scans for repositories with ultra-fast goroutines
func (p *UltraFastProcessor) scanRepositories(ctx context.Context) ([]string, error) {
	fmt.Printf("🔍 Scanning %s for repositories...\n", p.reposDir)
	start := time.Now()

	var repos []string
	var mu sync.Mutex

	// Channel for directory paths to process
	dirChan := make(chan string, p.workerCount*2)
	var wg sync.WaitGroup

	// Start scanner goroutines
	for i := 0; i < p.workerCount/4; i++ { // Use 1/4 workers for scanning
		wg.Add(1)
		go func() {
			defer wg.Done()
			for dir := range dirChan {
				if p.isValidRepository(dir) {
					mu.Lock()
					repos = append(repos, dir)
					mu.Unlock()
				}
			}
		}()
	}

	// Scan top-level directories
	entries, err := os.ReadDir(p.reposDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read repos directory: %w", err)
	}

	// Send directories to workers
	go func() {
		defer close(dirChan)
		for _, entry := range entries {
			if entry.IsDir() && !strings.HasPrefix(entry.Name(), ".") {
				select {
				case dirChan <- filepath.Join(p.reposDir, entry.Name()):
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	wg.Wait()

	scanTime := time.Since(start)
	fmt.Printf("📁 Found %d repositories in %.2fs\n", len(repos), scanTime.Seconds())

	return repos, nil
}

// isValidRepository checks if directory contains code files
func (p *UltraFastProcessor) isValidRepository(repoPath string) bool {
	// Quick git check
	if _, err := os.Stat(filepath.Join(repoPath, ".git")); err == nil {
		return true
	}

	// Fast code file check - sample a few files
	codeFileCount := 0
	err := filepath.WalkDir(repoPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil || codeFileCount >= 5 {
			return filepath.SkipDir
		}

		if d.IsDir() {
			if p.skipDirs[d.Name()] {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(d.Name()))
		if _, exists := p.codeExtensions[ext]; exists {
			codeFileCount++
			if codeFileCount >= 3 {
				return filepath.SkipAll // Found enough code files
			}
		}

		return nil
	})

	return err == nil && codeFileCount >= 3
}

// processFile processes a single file with ultra-fast optimization
func (p *UltraFastProcessor) processFile(filePath string) (*FileResult, error) {
	// Fast extension check
	ext := strings.ToLower(filepath.Ext(filePath))
	language, exists := p.codeExtensions[ext]
	if !exists {
		return nil, fmt.Errorf("unsupported extension")
	}

	// Fast file size check
	info, err := os.Stat(filePath)
	if err != nil {
		return nil, err
	}

	size := info.Size()
	if size < p.minFileSize || size > p.maxFileSize {
		return nil, fmt.Errorf("file size out of range: %d", size)
	}

	// Ultra-fast file reading
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	// Fast UTF-8 validation
	if !utf8.Valid(content) {
		return nil, fmt.Errorf("invalid UTF-8")
	}

	text := string(content)
	if len(strings.TrimSpace(text)) == 0 {
		return nil, fmt.Errorf("empty file")
	}

	// Fast line counting
	lines := strings.Count(text, "\n") + 1
	if lines < 5 || lines > 2000 {
		return nil, fmt.Errorf("line count out of range: %d", lines)
	}

	// Ultra-fast hash calculation
	hash := md5.Sum(content)
	hashStr := hex.EncodeToString(hash[:])

	// Update statistics atomically
	atomic.AddInt64(&p.stats.FilesProcessed, 1)
	atomic.AddInt64(&p.stats.BytesProcessed, size)

	p.stats.mu.Lock()
	p.stats.LanguageCount[language]++
	p.stats.mu.Unlock()

	// Get relative path
	relPath, err := filepath.Rel(p.reposDir, filePath)
	if err != nil {
		relPath = filePath
	}

	return &FileResult{
		Content:  text,
		Language: language,
		Lines:    lines,
		Size:     size,
		Hash:     hashStr,
		Path:     filepath.ToSlash(relPath), // Use forward slashes for JSON
	}, nil
}

// processRepository processes all files in a repository
func (p *UltraFastProcessor) processRepository(ctx context.Context, repoPath string) ([]*FileResult, error) {
	var results []*FileResult
	var mu sync.Mutex
	var wg sync.WaitGroup

	// Channel for file paths
	fileChan := make(chan string, p.workerCount)

	// Start file processing workers
	for i := 0; i < p.workerCount; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for filePath := range fileChan {
				if result, err := p.processFile(filePath); err == nil {
					mu.Lock()
					results = append(results, result)
					mu.Unlock()
				} else {
					atomic.AddInt64(&p.stats.ErrorCount, 1)
				}
			}
		}()
	}

	// Walk repository and send files to workers
	go func() {
		defer close(fileChan)
		filepath.WalkDir(repoPath, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return nil
			}

			select {
			case <-ctx.Done():
				return filepath.SkipAll
			default:
			}

			if d.IsDir() {
				if p.skipDirs[d.Name()] {
					return filepath.SkipDir
				}
				return nil
			}

			ext := strings.ToLower(filepath.Ext(d.Name()))
			if _, exists := p.codeExtensions[ext]; exists {
				select {
				case fileChan <- path:
				case <-ctx.Done():
					return filepath.SkipAll
				}
			}

			return nil
		})
	}()

	wg.Wait()
	atomic.AddInt64(&p.stats.ReposProcessed, 1)

	return results, nil
}

// processAllRepositories processes all repositories with maximum parallelism
func (p *UltraFastProcessor) processAllRepositories(ctx context.Context) ([]*FileResult, error) {
	repos, err := p.scanRepositories(ctx)
	if err != nil {
		return nil, err
	}

	if len(repos) == 0 {
		return nil, fmt.Errorf("no repositories found")
	}

	fmt.Printf("🔥 Processing %d repositories with MAXIMUM PARALLELISM\n", len(repos))
	start := time.Now()

	var allResults []*FileResult
	var mu sync.Mutex
	var wg sync.WaitGroup

	// Channel for repositories
	repoChan := make(chan string, len(repos))

	// Start repository processing workers
	workers := p.workerCount / 8 // Use fewer workers for repo-level processing
	if workers < 1 {
		workers = 1
	}

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for repoPath := range repoChan {
				results, err := p.processRepository(ctx, repoPath)
				if err == nil && len(results) > 0 {
					mu.Lock()
					allResults = append(allResults, results...)
					mu.Unlock()

					fmt.Printf("✅ Processed %s: %d files\n", filepath.Base(repoPath), len(results))
				}

				// Progress update
				processed := atomic.LoadInt64(&p.stats.ReposProcessed)
				if processed%50 == 0 {
					p.printProgress(int(processed), len(repos))
				}
			}
		}()
	}

	// Send repositories to workers
	go func() {
		defer close(repoChan)
		for _, repo := range repos {
			select {
			case repoChan <- repo:
			case <-ctx.Done():
				return
			}
		}
	}()

	wg.Wait()

	processingTime := time.Since(start)
	fmt.Printf("\n🎉 ULTRA-FAST PROCESSING COMPLETE!\n")
	fmt.Printf("⚡ Processing time: %.2fs\n", processingTime.Seconds())
	fmt.Printf("📊 Repositories: %d\n", len(repos))
	fmt.Printf("📄 Files found: %d\n", len(allResults))
	fmt.Printf("🚀 Rate: %.0f files/sec\n", float64(len(allResults))/processingTime.Seconds())

	return allResults, nil
}

// printProgress prints current processing statistics
func (p *UltraFastProcessor) printProgress(completed, total int) {
	elapsed := time.Since(p.stats.StartTime)
	rate := float64(completed) / elapsed.Seconds()
	filesProcessed := atomic.LoadInt64(&p.stats.FilesProcessed)
	bytesProcessed := atomic.LoadInt64(&p.stats.BytesProcessed)

	fmt.Printf("🚀 Progress: %d/%d repos (%.1f%%) | %d files | %.1fMB | %.1f repos/sec\n",
		completed, total, float64(completed)/float64(total)*100,
		filesProcessed, float64(bytesProcessed)/(1024*1024), rate)
}

// saveDataset saves results as JSON training dataset
func (p *UltraFastProcessor) saveDataset(results []*FileResult, outputFile string) error {
	fmt.Printf("💾 Saving %d files to %s...\n", len(results), outputFile)
	start := time.Now()

	file, err := os.Create(outputFile)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := bufio.NewWriter(file)
	defer writer.Flush()

	// Write JSON array start
	writer.WriteString("[\n")

	// Deduplicate by hash
	seen := make(map[string]bool)
	written := 0

	for i, result := range results {
		if seen[result.Hash] {
			continue
		}
		seen[result.Hash] = true

		// Convert to training format
		trainingData := TrainingData{
			Text: result.Content,
		}
		trainingData.Meta.Language = result.Language
		trainingData.Meta.Lines = result.Lines
		trainingData.Meta.Path = result.Path
		trainingData.Meta.Size = result.Size

		// Write JSON
		data, err := json.Marshal(trainingData)
		if err != nil {
			continue
		}

		writer.Write(data)
		if i < len(results)-1 {
			writer.WriteString(",")
		}
		writer.WriteString("\n")
		written++

		// Progress for large datasets
		if written%10000 == 0 {
			fmt.Printf("💾 Saved %d/%d files\n", written, len(results))
		}
	}

	writer.WriteString("]\n")

	saveTime := time.Since(start)
	fmt.Printf("✅ Saved %d unique files in %.2fs (%.0f files/sec)\n",
		written, saveTime.Seconds(), float64(written)/saveTime.Seconds())

	return nil
}

// printFinalStats prints comprehensive statistics
func (p *UltraFastProcessor) printFinalStats() {
	elapsed := time.Since(p.stats.StartTime)
	filesProcessed := atomic.LoadInt64(&p.stats.FilesProcessed)
	bytesProcessed := atomic.LoadInt64(&p.stats.BytesProcessed)
	reposProcessed := atomic.LoadInt64(&p.stats.ReposProcessed)
	errorCount := atomic.LoadInt64(&p.stats.ErrorCount)

	fmt.Printf("\n🏆 FINAL STATISTICS - RYZEN 9 3900X BEAST MODE\n")
	fmt.Printf("============================================================\n")
	fmt.Printf("⏱️  Total time: %.2fs\n", elapsed.Seconds())
	fmt.Printf("📁 Repositories processed: %d\n", reposProcessed)
	fmt.Printf("📄 Files processed: %d\n", filesProcessed)
	fmt.Printf("💾 Data processed: %.2fMB\n", float64(bytesProcessed)/(1024*1024))
	fmt.Printf("🚀 Processing rate: %.0f files/sec\n", float64(filesProcessed)/elapsed.Seconds())
	fmt.Printf("❌ Errors: %d\n", errorCount)

	fmt.Printf("\n🔤 Language Distribution:\n")
	p.stats.mu.RLock()
	for lang, count := range p.stats.LanguageCount {
		percentage := float64(count) / float64(filesProcessed) * 100
		fmt.Printf("   %s: %d files (%.1f%%)\n", lang, count, percentage)
	}
	p.stats.mu.RUnlock()
}

func main() {
	fmt.Printf("🚀 ULTRA-FAST GO REPOSITORY PROCESSOR\n")
	fmt.Printf("🔥 OPTIMIZED FOR RYZEN 9 3900X + 24 THREADS\n")
	fmt.Printf("============================================================\n")

	// Set GOMAXPROCS to use all cores
	runtime.GOMAXPROCS(runtime.NumCPU())
	fmt.Printf("💻 Using %d CPU cores\n", runtime.GOMAXPROCS(0))

	reposDir := getEnv("REPOS_DIR", `P:\\codelupe\\repos`)
	if len(os.Args) > 1 {
		reposDir = os.Args[1]
	}

	// Check if directory exists
	if _, err := os.Stat(reposDir); os.IsNotExist(err) {
		log.Fatalf("❌ Directory %s does not exist!", reposDir)
	}

	// Create processor
	processor := NewUltraFastProcessor(reposDir)

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()

	// Process all repositories
	results, err := processor.processAllRepositories(ctx)
	if err != nil {
		log.Fatalf("❌ Processing failed: %v", err)
	}

	if len(results) == 0 {
		log.Fatal("❌ No files processed!")
	}

	// Save dataset
	outputFile := fmt.Sprintf("%s/ultra_fast_go_dataset_%d.json", filepath.Dir(reposDir), time.Now().Unix())
	if err := processor.saveDataset(results, outputFile); err != nil {
		log.Fatalf("❌ Failed to save dataset: %v", err)
	}

	// Print final statistics
	processor.printFinalStats()

	fmt.Printf("\n🏆 MISSION ACCOMPLISHED!\n")
	fmt.Printf("📁 Dataset: %s\n", outputFile)
}
