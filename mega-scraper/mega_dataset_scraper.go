package main

import (
	"archive/zip"
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/plumbing/transport/http"
)

// RepoInfo holds repository metadata
type RepoInfo struct {
	URL           string `json:"url"`
	FullName      string `json:"full_name"`
	Stars         int    `json:"stargazers_count"`
	Language      string `json:"language"`
	Size          int    `json:"size"`
	DefaultBranch string `json:"default_branch"`
}

// WorkerPool manages concurrent repository processing
type WorkerPool struct {
	workerCount  int
	jobQueue     chan RepoInfo
	resultQueue  chan ProcessResult
	wg           *sync.WaitGroup
	ctx          context.Context
	cancel       context.CancelFunc
	tokenManager *TokenManager
	stats        *Stats
	config       *Config
}

// TokenManager handles GitHub token rotation
type TokenManager struct {
	tokens       []string
	currentIndex int64
	rateLimits   map[string]*RateLimit
	mutex        sync.RWMutex
}

// RateLimit tracks API rate limiting per token
type RateLimit struct {
	Remaining int
	ResetTime time.Time
	mutex     sync.Mutex
}

// ProcessResult holds the result of processing a repository
type ProcessResult struct {
	RepoURL       string
	FilesAdded    int
	FilesRejected int
	Stars         int
	Error         error
	Duration      time.Duration
}

// Stats tracks overall processing statistics
type Stats struct {
	ReposProcessed  int64
	FilesProcessed  int64
	FilesAccepted   int64
	FilesRejected   int64
	DuplicatesFound int64
	TotalSize       int64
	Languages       map[string]int64
	mutex           sync.RWMutex
}

// Config holds configuration options
type Config struct {
	OutputDir    string
	MinStars     int
	MaxWorkers   int
	MinFileSize  int
	MaxFileSize  int
	QualityScore float64
	TargetFiles  int64
	TokenFile    string
	RepoListFile string
	CloneTimeout time.Duration
	APITimeout   time.Duration
}

// FileQuality represents quality metrics for a code file
type FileQuality struct {
	Language        string
	LinesOfCode     int
	CommentRatio    float64
	ComplexityScore float64
	HasDocs         bool
	HasTests        bool
	StyleScore      float64
	QualityScore    float64
}

// NewTokenManager creates a new token manager
func NewTokenManager(tokenFile string) (*TokenManager, error) {
	tokens, err := loadTokens(tokenFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load tokens: %w", err)
	}

	if len(tokens) == 0 {
		return nil, fmt.Errorf("no valid tokens found in %s", tokenFile)
	}

	tm := &TokenManager{
		tokens:     tokens,
		rateLimits: make(map[string]*RateLimit),
	}

	// Initialize rate limits for each token
	for _, token := range tokens {
		tm.rateLimits[token] = &RateLimit{
			Remaining: 5000, // GitHub API limit
			ResetTime: time.Now().Add(time.Hour),
		}
	}

	log.Printf("🔑 Loaded %d GitHub tokens", len(tokens))
	return tm, nil
}

// GetToken returns the next available token with rate limit consideration
func (tm *TokenManager) GetToken() string {
	tm.mutex.RLock()
	defer tm.mutex.RUnlock()

	// Find token with available rate limit
	for i := 0; i < len(tm.tokens); i++ {
		index := (int(atomic.LoadInt64(&tm.currentIndex)) + i) % len(tm.tokens)
		token := tm.tokens[index]

		if rl, exists := tm.rateLimits[token]; exists {
			rl.mutex.Lock()
			if rl.Remaining > 10 || time.Now().After(rl.ResetTime) {
				rl.mutex.Unlock()
				atomic.StoreInt64(&tm.currentIndex, int64((index+1)%len(tm.tokens)))
				return token
			}
			rl.mutex.Unlock()
		}
	}

	// If no token available, return the next one anyway (will hit rate limit)
	index := int(atomic.AddInt64(&tm.currentIndex, 1)) % len(tm.tokens)
	return tm.tokens[index]
}

// UpdateRateLimit updates the rate limit for a specific token
func (tm *TokenManager) UpdateRateLimit(token string, remaining int, resetTime time.Time) {
	tm.mutex.RLock()
	if rl, exists := tm.rateLimits[token]; exists {
		rl.mutex.Lock()
		rl.Remaining = remaining
		rl.ResetTime = resetTime
		rl.mutex.Unlock()
	}
	tm.mutex.RUnlock()
}

// loadTokens loads GitHub tokens from file
func loadTokens(filename string) ([]string, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var tokens []string
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			// Validate token format (basic check)
			if strings.HasPrefix(line, "ghp_") && len(line) == 40 {
				tokens = append(tokens, line)
			}
		}
	}

	return tokens, scanner.Err()
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(workerCount int, tm *TokenManager, config *Config) *WorkerPool {
	ctx, cancel := context.WithCancel(context.Background())

	return &WorkerPool{
		workerCount:  workerCount,
		jobQueue:     make(chan RepoInfo, workerCount*2),
		resultQueue:  make(chan ProcessResult, workerCount*2),
		wg:           &sync.WaitGroup{},
		ctx:          ctx,
		cancel:       cancel,
		tokenManager: tm,
		stats:        NewStats(),
		config:       config,
	}
}

// NewStats creates a new stats tracker
func NewStats() *Stats {
	return &Stats{
		Languages: make(map[string]int64),
	}
}

// Start starts the worker pool
func (wp *WorkerPool) Start() {
	for i := 0; i < wp.workerCount; i++ {
		wp.wg.Add(1)
		go wp.worker(i)
	}

	log.Printf("🚀 Started %d workers", wp.workerCount)
}

// Stop stops the worker pool
func (wp *WorkerPool) Stop() {
	close(wp.jobQueue)
	wp.wg.Wait()
	close(wp.resultQueue)
	wp.cancel()
}

// AddJob adds a repository to the processing queue
func (wp *WorkerPool) AddJob(repo RepoInfo) {
	select {
	case wp.jobQueue <- repo:
	case <-wp.ctx.Done():
		return
	}
}

// worker processes repositories
func (wp *WorkerPool) worker(id int) {
	defer wp.wg.Done()

	for {
		select {
		case repo, ok := <-wp.jobQueue:
			if !ok {
				return
			}

			start := time.Now()
			result := wp.processRepository(repo)
			result.Duration = time.Since(start)

			select {
			case wp.resultQueue <- result:
			case <-wp.ctx.Done():
				return
			}

		case <-wp.ctx.Done():
			return
		}
	}
}

// processRepository processes a single repository
func (wp *WorkerPool) processRepository(repo RepoInfo) ProcessResult {
	log.Printf("🔍 Worker processing: %s (%d stars)", repo.FullName, repo.Stars)

	// Skip if not enough stars
	if repo.Stars < wp.config.MinStars {
		return ProcessResult{
			RepoURL: repo.URL,
			Error:   fmt.Errorf("insufficient stars: %d", repo.Stars),
		}
	}

	// Create temporary directory
	tempDir := filepath.Join(os.TempDir(), fmt.Sprintf("repo_%d", time.Now().UnixNano()))
	defer os.RemoveAll(tempDir)

	// Clone repository
	token := wp.tokenManager.GetToken()
	if err := wp.cloneRepository(repo.URL, tempDir, token); err != nil {
		return ProcessResult{
			RepoURL: repo.URL,
			Error:   fmt.Errorf("clone failed: %w", err),
		}
	}

	// Process files
	filesAdded, filesRejected := wp.processFiles(tempDir, repo)

	// Update stats
	atomic.AddInt64(&wp.stats.ReposProcessed, 1)

	return ProcessResult{
		RepoURL:       repo.URL,
		FilesAdded:    filesAdded,
		FilesRejected: filesRejected,
		Stars:         repo.Stars,
	}
}

// cloneRepository clones a repository using git with aggressive parallelization
func (wp *WorkerPool) cloneRepository(repoURL, tempDir string, token string) error {
	ctx, cancel := context.WithTimeout(wp.ctx, wp.config.CloneTimeout)
	defer cancel()

	// Try multiple clone strategies in parallel for maximum speed
	type cloneResult struct {
		err    error
		method string
	}

	resultChan := make(chan cloneResult, 3)

	// Method 1: go-git (most reliable)
	go func() {
		err := wp.cloneWithGoGit(ctx, repoURL, tempDir, token)
		resultChan <- cloneResult{err: err, method: "go-git"}
	}()

	// Method 2: git command (often faster for large repos)
	go func() {
		err := wp.cloneWithGitCommand(ctx, repoURL, tempDir, token)
		resultChan <- cloneResult{err: err, method: "git-cmd"}
	}()

	// Method 3: curl + unzip for GitHub repos (fastest for small repos)
	go func() {
		err := wp.cloneWithArchive(ctx, repoURL, tempDir, token)
		resultChan <- cloneResult{err: err, method: "archive"}
	}()

	// Return first successful result
	for i := 0; i < 3; i++ {
		select {
		case result := <-resultChan:
			if result.err == nil {
				return nil // Success!
			}
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	// If all methods failed, try one more time with go-git
	return wp.cloneWithGoGit(ctx, repoURL, tempDir, token)
}

// cloneWithGoGit uses go-git library
func (wp *WorkerPool) cloneWithGoGit(ctx context.Context, repoURL, tempDir, token string) error {
	_, err := git.PlainCloneContext(ctx, tempDir, false, &git.CloneOptions{
		URL:   repoURL,
		Depth: 1,
		Auth: &http.BasicAuth{
			Username: "token",
			Password: token,
		},
		SingleBranch: true,
		Progress:     nil,
	})
	return err
}

// cloneWithGitCommand uses git CLI (often faster)
func (wp *WorkerPool) cloneWithGitCommand(ctx context.Context, repoURL, tempDir, token string) error {
	// Create authenticated URL
	authURL := strings.Replace(repoURL, "https://", fmt.Sprintf("https://token:%s@", token), 1)

	cmd := exec.CommandContext(ctx, "git", "clone", "--depth", "1", "--single-branch", authURL, tempDir)
	cmd.Env = append(os.Environ(),
		"GIT_TERMINAL_PROMPT=0",
		"GIT_ASKPASS=echo",
	)

	return cmd.Run()
}

// cloneWithArchive downloads repository as ZIP (fastest for small repos)
func (wp *WorkerPool) cloneWithArchive(ctx context.Context, repoURL, tempDir, token string) error {
	// Extract owner/repo from URL
	parts := strings.Split(strings.TrimPrefix(repoURL, "https://github.com/"), "/")
	if len(parts) < 2 {
		return fmt.Errorf("invalid GitHub URL")
	}

	// Download ZIP archive
	zipURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/zipball", parts[0], parts[1])

	client := &http.Client{Timeout: wp.config.APITimeout}
	req, err := http.NewRequestWithContext(ctx, "GET", zipURL, nil)
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", fmt.Sprintf("token %s", token))
	req.Header.Set("Accept", "application/vnd.github.v3+json")

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed: %s", resp.Status)
	}

	// Create temp zip file
	zipFile := tempDir + ".zip"
	out, err := os.Create(zipFile)
	if err != nil {
		return err
	}
	defer os.Remove(zipFile)

	_, err = io.Copy(out, resp.Body)
	out.Close()
	if err != nil {
		return err
	}

	// Extract zip
	return wp.extractZip(zipFile, tempDir)
}

// extractZip extracts a zip file to destination directory
func (wp *WorkerPool) extractZip(zipFile, destDir string) error {
	reader, err := zip.OpenReader(zipFile)
	if err != nil {
		return err
	}
	defer reader.Close()

	// Create destination directory
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return err
	}

	// Extract files
	for _, file := range reader.File {
		path := filepath.Join(destDir, file.Name)

		// Security check
		if !strings.HasPrefix(path, filepath.Clean(destDir)+string(os.PathSeparator)) {
			continue
		}

		if file.FileInfo().IsDir() {
			os.MkdirAll(path, file.FileInfo().Mode())
			continue
		}

		// Create file directories
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			continue
		}

		// Extract file
		fileReader, err := file.Open()
		if err != nil {
			continue
		}

		targetFile, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, file.FileInfo().Mode())
		if err != nil {
			fileReader.Close()
			continue
		}

		_, err = io.Copy(targetFile, fileReader)
		fileReader.Close()
		targetFile.Close()

		if err != nil {
			continue
		}
	}

	return nil
}

// processFiles processes all code files in a repository
func (wp *WorkerPool) processFiles(repoDir string, repo RepoInfo) (int, int) {
	filesAdded := 0
	filesRejected := 0

	err := filepath.Walk(repoDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Continue on errors
		}

		if !info.Mode().IsRegular() {
			return nil
		}

		// Skip if file doesn't meet basic criteria
		if !wp.shouldProcessFile(path, info) {
			return nil
		}

		// Read and analyze file
		content, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		quality := wp.analyzeCodeQuality(path, string(content))
		if quality == nil {
			filesRejected++
			return nil
		}

		// Check quality threshold
		if quality.QualityScore < wp.config.QualityScore {
			filesRejected++
			return nil
		}

		// Save high-quality file
		if wp.saveQualityFile(path, string(content), quality, repo) {
			filesAdded++
			atomic.AddInt64(&wp.stats.FilesAccepted, 1)

			// Update language stats
			wp.stats.mutex.Lock()
			wp.stats.Languages[quality.Language]++
			wp.stats.mutex.Unlock()
		} else {
			filesRejected++
		}

		atomic.AddInt64(&wp.stats.FilesProcessed, 1)
		return nil
	})

	if err != nil {
		log.Printf("⚠️ Error walking directory %s: %v", repoDir, err)
	}

	return filesAdded, filesRejected
}

// shouldProcessFile determines if a file should be processed
func (wp *WorkerPool) shouldProcessFile(path string, info os.FileInfo) bool {
	// Size checks
	if info.Size() < int64(wp.config.MinFileSize) || info.Size() > int64(wp.config.MaxFileSize) {
		return false
	}

	// Skip certain directories
	skipDirs := []string{".git", "node_modules", "target", "build", "dist", "__pycache__", "vendor", ".venv", "venv"}
	for _, dir := range skipDirs {
		if strings.Contains(path, dir) {
			return false
		}
	}

	// Check file extension
	ext := filepath.Ext(path)
	supportedExts := []string{".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".h", ".hpp", ".cs", ".php", ".rb", ".swift", ".kt", ".scala"}

	for _, supportedExt := range supportedExts {
		if ext == supportedExt {
			return true
		}
	}

	return false
}

// analyzeCodeQuality analyzes the quality of a code file
func (wp *WorkerPool) analyzeCodeQuality(path, content string) *FileQuality {
	ext := filepath.Ext(path)
	language := detectLanguage(ext)
	if language == "" {
		return nil
	}

	lines := strings.Split(content, "\n")
	linesOfCode := 0
	commentLines := 0

	// Count actual code lines and comments
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" {
			continue
		}

		if isComment(trimmed, language) {
			commentLines++
		} else {
			linesOfCode++
		}
	}

	// Skip files that are too small or too large
	if linesOfCode < 10 || linesOfCode > 3000 {
		return nil
	}

	commentRatio := float64(commentLines) / float64(linesOfCode+commentLines)
	complexityScore := calculateComplexity(content, language)
	hasDocs := hasDocumentation(content, language)
	hasTests := hasTestCode(content, language)
	styleScore := calculateStyleScore(content, language)

	// Calculate overall quality score
	qualityScore := calculateQualityScore(linesOfCode, commentRatio, complexityScore, hasDocs, hasTests, styleScore)

	return &FileQuality{
		Language:        language,
		LinesOfCode:     linesOfCode,
		CommentRatio:    commentRatio,
		ComplexityScore: complexityScore,
		HasDocs:         hasDocs,
		HasTests:        hasTests,
		StyleScore:      styleScore,
		QualityScore:    qualityScore,
	}
}

// detectLanguage detects programming language from file extension
func detectLanguage(ext string) string {
	langMap := map[string]string{
		".py":    "python",
		".js":    "javascript",
		".jsx":   "javascript",
		".ts":    "typescript",
		".tsx":   "typescript",
		".go":    "go",
		".rs":    "rust",
		".java":  "java",
		".cpp":   "cpp",
		".c":     "c",
		".h":     "c",
		".hpp":   "cpp",
		".cs":    "csharp",
		".php":   "php",
		".rb":    "ruby",
		".swift": "swift",
		".kt":    "kotlin",
		".scala": "scala",
	}

	return langMap[ext]
}

// isComment checks if a line is a comment
func isComment(line, language string) bool {
	commentPrefixes := map[string][]string{
		"python":     {"#"},
		"javascript": {"//", "/*"},
		"typescript": {"//", "/*"},
		"go":         {"//", "/*"},
		"rust":       {"//", "/*"},
		"java":       {"//", "/*"},
		"cpp":        {"//", "/*"},
		"c":          {"//", "/*"},
		"csharp":     {"//", "/*"},
		"php":        {"//", "/*", "#"},
		"ruby":       {"#"},
		"swift":      {"//", "/*"},
		"kotlin":     {"//", "/*"},
		"scala":      {"//", "/*"},
	}

	prefixes := commentPrefixes[language]
	for _, prefix := range prefixes {
		if strings.HasPrefix(line, prefix) {
			return true
		}
	}

	return false
}

// calculateComplexity calculates code complexity
func calculateComplexity(content, language string) float64 {
	complexity := 0.0
	lines := strings.Split(content, "\n")

	// Count decision points and structures
	patterns := map[string][]string{
		"python":     {"def ", "class ", "if ", "for ", "while ", "try ", "except ", "with "},
		"javascript": {"function ", "if ", "for ", "while ", "try ", "catch ", "switch "},
		"typescript": {"function ", "if ", "for ", "while ", "try ", "catch ", "switch "},
		"go":         {"func ", "if ", "for ", "switch ", "select "},
		"rust":       {"fn ", "if ", "for ", "while ", "match ", "loop "},
		"java":       {"public ", "private ", "if ", "for ", "while ", "try ", "catch ", "switch "},
		"cpp":        {"if ", "for ", "while ", "try ", "catch ", "switch "},
		"c":          {"if ", "for ", "while ", "switch "},
	}

	languagePatterns := patterns[language]
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		for _, pattern := range languagePatterns {
			if strings.Contains(trimmed, pattern) {
				complexity += 1.0
				break
			}
		}
	}

	return complexity / float64(len(lines)) * 100
}

// hasDocumentation checks if the code has documentation
func hasDocumentation(content, language string) bool {
	docPatterns := map[string][]string{
		"python":     {`"""`, `'''`, "# TODO", "# FIXME"},
		"javascript": {`/**`, `@param`, `@return`},
		"typescript": {`/**`, `@param`, `@return`},
		"go":         {`//`, `/*`},
		"rust":       {`///`, `//!`},
		"java":       {`/**`, `@param`, `@return`, `@author`},
		"cpp":        {`/**`, `///`, `@brief`},
		"c":          {`/*`, `//`},
	}

	patterns := docPatterns[language]
	for _, pattern := range patterns {
		if strings.Contains(content, pattern) {
			return true
		}
	}

	return false
}

// hasTestCode checks if the code contains test patterns
func hasTestCode(content, language string) bool {
	testPatterns := map[string][]string{
		"python":     {"def test_", "class Test", "import unittest", "import pytest", "assert "},
		"javascript": {"describe(", "it(", "test(", "expect(", "assert"},
		"typescript": {"describe(", "it(", "test(", "expect(", "assert"},
		"go":         {"func Test", "testing.T", "t.Error", "t.Fatal"},
		"rust":       {"#[test]", "#[cfg(test)]", "assert!", "assert_eq!"},
		"java":       {"@Test", "import.*junit", "Assert.", "assertEquals"},
		"cpp":        {"TEST(", "EXPECT_", "ASSERT_", "#include.*gtest"},
		"c":          {"assert(", "TEST_"},
	}

	patterns := testPatterns[language]
	for _, pattern := range patterns {
		if matched, _ := regexp.MatchString(pattern, content); matched {
			return true
		}
	}

	return false
}

// calculateStyleScore calculates code style score
func calculateStyleScore(content, language string) float64 {
	score := 50.0 // Base score

	// Check for good practices
	if hasDocumentation(content, language) {
		score += 20
	}

	if hasTestCode(content, language) {
		score += 15
	}

	// Check for bad patterns
	badPatterns := []string{"TODO", "FIXME", "XXX", "HACK", "console.log", "print(", "System.out"}
	for _, pattern := range badPatterns {
		if strings.Contains(content, pattern) {
			score -= 10
		}
	}

	return math.Max(0, math.Min(100, score))
}

// calculateQualityScore calculates overall quality score
func calculateQualityScore(loc int, commentRatio, complexity float64, hasDocs, hasTests bool, styleScore float64) float64 {
	score := 0.0

	// Base score from complexity and style
	score += complexity * 0.3
	score += styleScore * 0.4

	// Documentation bonus
	if hasDocs {
		score += 15
	}

	// Test bonus
	if hasTests {
		score += 15
	}

	// Comment ratio score (ideal around 15-25%)
	if commentRatio >= 0.15 && commentRatio <= 0.25 {
		score += 10
	} else if commentRatio >= 0.10 && commentRatio <= 0.35 {
		score += 5
	}

	// File size bonus (prefer substantial files)
	if loc >= 50 && loc <= 500 {
		score += 10
	} else if loc >= 20 && loc <= 1000 {
		score += 5
	}

	return math.Max(0, math.Min(100, score))
}

// saveQualityFile saves a high-quality file to the dataset
func (wp *WorkerPool) saveQualityFile(originalPath, content string, quality *FileQuality, repo RepoInfo) bool {
	// Create output directory structure
	outputDir := filepath.Join(wp.config.OutputDir, quality.Language)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		log.Printf("⚠️ Failed to create directory %s: %v", outputDir, err)
		return false
	}

	// Generate unique filename
	filename := fmt.Sprintf("%s_%d_%s",
		strings.ReplaceAll(repo.FullName, "/", "_"),
		time.Now().UnixNano(),
		filepath.Base(originalPath))

	outputPath := filepath.Join(outputDir, filename)

	// Write file
	if err := os.WriteFile(outputPath, []byte(content), 0644); err != nil {
		log.Printf("⚠️ Failed to write file %s: %v", outputPath, err)
		return false
	}

	// Write metadata
	metadata := map[string]interface{}{
		"original_path":    originalPath,
		"repo_url":         repo.URL,
		"repo_full_name":   repo.FullName,
		"repo_stars":       repo.Stars,
		"language":         quality.Language,
		"lines_of_code":    quality.LinesOfCode,
		"comment_ratio":    quality.CommentRatio,
		"complexity_score": quality.ComplexityScore,
		"has_docs":         quality.HasDocs,
		"has_tests":        quality.HasTests,
		"style_score":      quality.StyleScore,
		"quality_score":    quality.QualityScore,
		"created_at":       time.Now().Format(time.RFC3339),
	}

	metadataPath := outputPath + ".meta.json"
	metadataJSON, _ := json.MarshalIndent(metadata, "", "  ")
	os.WriteFile(metadataPath, metadataJSON, 0644)

	return true
}

// GetStats returns current processing statistics
func (wp *WorkerPool) GetStats() *Stats {
	return wp.stats
}

// PrintStats prints current statistics
func (s *Stats) PrintStats() {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	fmt.Printf("\n📊 MEGA DATASET SCRAPER STATS:\n")
	fmt.Printf("   🏭 Repositories processed: %d\n", s.ReposProcessed)
	fmt.Printf("   📄 Files processed: %d\n", s.FilesProcessed)
	fmt.Printf("   ✅ Files accepted: %d\n", s.FilesAccepted)
	fmt.Printf("   ❌ Files rejected: %d\n", s.FilesRejected)
	fmt.Printf("   🔄 Duplicates found: %d\n", s.DuplicatesFound)
	fmt.Printf("   💾 Total size: %.2f MB\n", float64(s.TotalSize)/(1024*1024))

	fmt.Printf("\n🔤 Language Distribution:\n")
	for lang, count := range s.Languages {
		fmt.Printf("   • %s: %d files\n", lang, count)
	}
}

// loadRepositories loads repository URLs from file
func loadRepositories(filename string) ([]RepoInfo, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var repos []RepoInfo
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			repos = append(repos, RepoInfo{
				URL: line,
				// Stars will be fetched via API
			})
		}
	}

	return repos, scanner.Err()
}

// fetchRepoMetadata fetches repository metadata from GitHub API
func (wp *WorkerPool) fetchRepoMetadata(repo *RepoInfo) error {
	token := wp.tokenManager.GetToken()

	// Extract owner/repo from URL
	parts := strings.Split(strings.TrimPrefix(repo.URL, "https://github.com/"), "/")
	if len(parts) < 2 {
		return fmt.Errorf("invalid repository URL: %s", repo.URL)
	}

	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s", parts[0], parts[1])

	client := &http.Client{Timeout: wp.config.APITimeout}
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", fmt.Sprintf("token %s", token))
	req.Header.Set("Accept", "application/vnd.github.v3+json")

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	// Update rate limit info
	if remaining := resp.Header.Get("X-RateLimit-Remaining"); remaining != "" {
		if r, err := strconv.Atoi(remaining); err == nil {
			if resetTime := resp.Header.Get("X-RateLimit-Reset"); resetTime != "" {
				if reset, err := strconv.ParseInt(resetTime, 10, 64); err == nil {
					wp.tokenManager.UpdateRateLimit(token, r, time.Unix(reset, 0))
				}
			}
		}
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("API request failed: %s", resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	return json.Unmarshal(body, repo)
}

func main() {
	// Configuration - RYZEN 3900X + RTX 4090 BEAST MODE
	cpuCores := runtime.GOMAXPROCS(0) // 24 threads on 3900X
	config := &Config{
		OutputDir:    "\\\\192.168.1.66\\plex3\\codelupe\\repos\\mega_dataset",
		MinStars:     5,
		MaxWorkers:   cpuCores * 8, // 192 workers (24 * 8) - INSANE PARALLELISM
		MinFileSize:  100,          // 100 bytes
		MaxFileSize:  500000,       // 500KB
		QualityScore: 30.0,         // Minimum quality score
		TargetFiles:  100000000,    // 100M files
		TokenFile:    "github_tokens.txt",
		RepoListFile: "repository_urls.txt",
		CloneTimeout: 15 * time.Second, // Even faster with your beast CPU
		APITimeout:   3 * time.Second,  // Lightning fast API calls
	}

	log.Printf("🔥 BEAST MODE: Ryzen 3900X detected - %d CPU threads", cpuCores)
	log.Printf("⚡ Launching %d concurrent workers (8x CPU threads)", config.MaxWorkers)

	// Parse command line arguments
	if len(os.Args) > 1 {
		config.RepoListFile = os.Args[1]
	}

	log.Printf("🚀 MEGA DATASET SCRAPER STARTING")
	log.Printf("🎯 Target: %d high-quality files", config.TargetFiles)
	log.Printf("⚙️ Workers: %d", config.MaxWorkers)

	// Initialize token manager
	tokenManager, err := NewTokenManager(config.TokenFile)
	if err != nil {
		log.Fatalf("❌ Failed to initialize token manager: %v", err)
	}

	// Load repositories
	repos, err := loadRepositories(config.RepoListFile)
	if err != nil {
		log.Fatalf("❌ Failed to load repositories: %v", err)
	}

	log.Printf("📋 Loaded %d repositories", len(repos))

	// Create worker pool
	wp := NewWorkerPool(config.MaxWorkers, tokenManager, config)
	wp.Start()

	// Start result processor
	go func() {
		for result := range wp.resultQueue {
			if result.Error != nil {
				log.Printf("⚠️ %s: %v", result.RepoURL, result.Error)
			} else {
				log.Printf("✅ %s: %d files added (%d rejected) in %v",
					result.RepoURL, result.FilesAdded, result.FilesRejected, result.Duration)
			}

			// Print stats every 100 repos
			if wp.stats.ReposProcessed%100 == 0 {
				wp.stats.PrintStats()
			}

			// Check if target reached
			if wp.stats.FilesAccepted >= config.TargetFiles {
				log.Printf("🎯 TARGET REACHED! %d files collected", wp.stats.FilesAccepted)
				wp.Stop()
				break
			}
		}
	}()

	// Process repositories
	startTime := time.Now()
	for i, repo := range repos {
		// Fetch metadata first
		if err := wp.fetchRepoMetadata(&repo); err != nil {
			log.Printf("⚠️ Failed to fetch metadata for %s: %v", repo.URL, err)
			continue
		}

		// Add to processing queue
		wp.AddJob(repo)

		// Progress update
		if i%1000 == 0 {
			elapsed := time.Since(startTime)
			rate := float64(wp.stats.FilesAccepted) / elapsed.Seconds()
			log.Printf("📈 Progress: %d/%d repos | %d files | %.1f files/sec",
				i, len(repos), wp.stats.FilesAccepted, rate)
		}
	}

	// Wait for completion
	wp.Stop()

	// Final statistics
	elapsed := time.Since(startTime)
	wp.stats.PrintStats()

	log.Printf("\n🎉 MEGA DATASET COLLECTION COMPLETE!")
	log.Printf("⏱️ Total time: %v", elapsed)
	log.Printf("🏆 Final count: %d high-quality files", wp.stats.FilesAccepted)
	log.Printf("📊 Average rate: %.1f files/second", float64(wp.stats.FilesAccepted)/elapsed.Seconds())

	// Compare to The Stack
	theStackFiles := int64(54000000)
	if wp.stats.FilesAccepted > theStackFiles {
		improvement := float64(wp.stats.FilesAccepted-theStackFiles) / float64(theStackFiles) * 100
		log.Printf("🥇 WORLD RECORD: %.1f%% larger than The Stack!", improvement)
	}
}
