package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/joho/godotenv"
	"github.com/lib/pq"
	_ "github.com/lib/pq"
)

type QualityAnalyzer struct {
	db               *sql.DB
	securityPatterns map[string]*regexp.Regexp
	excludePatterns  []*regexp.Regexp
	languageWeights  map[string]float64
	minQualityScore  float64
	maxFilesPerRepo  int
}

type RepoQuality struct {
	ID               string
	FullName         string
	LocalPath        string
	QualityScore     float64
	SecurityScore    float64
	CodeFiles        []CodeFile
	TotalFiles       int
	ValidFiles       int
	TotalLines       int
	ValidLines       int
	Languages        map[string]int
	SecurityPatterns map[string]int
	Issues           []string
	Metrics          QualityMetrics
	CreatedAt        time.Time
}

type CodeFile struct {
	Path             string
	Language         string
	Lines            int
	SecurityPatterns []string
	QualityScore     float64
	Complexity       int
	IsHighQuality    bool
	Content          string
}

type QualityMetrics struct {
	AvgLinesPerFile     float64
	FunctionDensity     float64
	CommentRatio        float64
	SecurityDensity     float64
	LanguageConsistency float64
	DocumentationRatio  float64
	TestCoverage        float64
	ComplexityScore     float64
}

var (
	// Files/directories to completely exclude
	excludePatterns = []string{
		// Documentation and metadata
		`(?i)readme\.md$`, `(?i)changelog\.md$`, `(?i)license\.?.*$`, `(?i)contributing\.md$`,
		`(?i)code_of_conduct\.md$`, `(?i)security\.md$`, `(?i)authors\.md$`, `(?i)maintainers\.md$`,
		`(?i)\.github/`, `(?i)docs?/`, `(?i)documentation/`, `(?i)wiki/`,

		// Generated files
		`(?i)\.pb\.go$`, `(?i)\.pb\.py$`, `(?i)_pb2\.py$`, `(?i)\.proto$`,
		`(?i)\.generated\.`, `(?i)\.gen\.`, `(?i)autogen`, `(?i)codegen`,
		`(?i)vendor/`, `(?i)node_modules/`, `(?i)\.git/`, `(?i)\.svn/`,
		`(?i)build/`, `(?i)dist/`, `(?i)target/`, `(?i)bin/`, `(?i)obj/`,

		// Config and data files
		`(?i)\.json$`, `(?i)\.xml$`, `(?i)\.yaml$`, `(?i)\.yml$`, `(?i)\.toml$`,
		`(?i)\.ini$`, `(?i)\.cfg$`, `(?i)\.conf$`, `(?i)config\.`, `(?i)\.env$`,
		`(?i)\.txt$`, `(?i)\.log$`, `(?i)\.csv$`, `(?i)\.tsv$`,

		// Media and binary files
		`(?i)\.(png|jpg|jpeg|gif|svg|ico|pdf|zip|tar|gz|bz2|xz)$`,
		`(?i)\.(exe|dll|so|dylib|bin|dat|db|sqlite)$`,

		// Lock files and package management
		`(?i)package-lock\.json$`, `(?i)yarn\.lock$`, `(?i)composer\.lock$`,
		`(?i)pipfile\.lock$`, `(?i)poetry\.lock$`, `(?i)go\.sum$`,

		// Test fixtures and samples that aren't quality code
		`(?i)fixtures?/`, `(?i)samples?/`, `(?i)examples?/.*\.(txt|dat|bin)$`,
		`(?i)test.*\.(json|xml|yaml|yml)$`, `(?i)mock.*\.(json|xml|yaml|yml)$`,

		// Minified and compressed code
		`(?i)\.min\.js$`, `(?i)\.min\.css$`, `(?i)-min\.`, `(?i)\.bundle\.`,

		// IDE and editor files
		`(?i)\.vscode/`, `(?i)\.idea/`, `(?i)\.eclipse/`, `(?i)\.(DS_Store|gitignore|gitkeep)$`,
	}

	// High-value coding patterns for target technologies
	codingPatterns = map[string]string{
		"angular":       `(?i)(angular|@angular|component|service|module|directive|pipe|injectable|ngrx|rxjs)`,
		"python":        `(?i)(python|django|flask|fastapi|pandas|numpy|pytest|pip|requirements\.txt|__init__|def\s+\w+)`,
		"go":            `(?i)(golang|go\.mod|go\.sum|func\s+\w+|package\s+\w+|import\s+|goroutine|channel|defer)`,
		"rust":          `(?i)(rust|cargo\.toml|cargo\.lock|fn\s+\w+|struct\s+\w+|impl\s+|use\s+|Result|Option)`,
		"csharp":        `(?i)(csharp|\.net|namespace\s+|class\s+\w+|public\s+|private\s+|async\s+Task|using\s+)`,
		"typescript":    `(?i)(typescript|\.ts$|interface\s+\w+|type\s+\w+|export\s+|import\s+|async\s+|Promise)`,
		"mssql":         `(?i)(sql.*server|mssql|t-sql|sqlcmd|select\s+|insert\s+|update\s+|delete\s+|create\s+table)`,
		"mongodb":       `(?i)(mongodb|mongo|mongoose|collection|document|find\(|aggregate|insertOne|updateOne)`,
		"postgresql":    `(?i)(postgresql|postgres|pg|psql|select\s+|insert\s+|update\s+|delete\s+|create\s+table)`,
		"elasticsearch": `(?i)(elasticsearch|elastic|kibana|logstash|index|search|query|mapping|aggregation)`,
		"flutter":       `(?i)(flutter|widget|stateless|stateful|scaffold|material|cupertino|build\s+context)`,
		"dart":          `(?i)(dart|class\s+\w+|void\s+main|async\s+|await\s+|Future|Stream|List<)`,
	}

	// Language quality weights (focused on target technologies in priority order)
	languageWeights = map[string]float64{
		"python":     1.0,  // #1 - Python development
		"go":         0.95, // #2 - Go development
		"rust":       0.90, // #3 - Rust development
		"typescript": 0.85, // #4 - TypeScript and Angular
		"dart":       0.80, // #5 - Flutter/Dart development
		"csharp":     0.75, // C# development
		"javascript": 0.70, // Supporting Angular development
		"sql":        0.65, // SQL databases
		"json":       0.50, // Configuration and data
		"yaml":       0.45, // Configuration files
		"toml":       0.45, // Rust configuration
	}

	// High-quality code indicators for target technologies
	qualityIndicators = []string{
		// Testing patterns
		`(?i)func.*test.*\(`, `(?i)def.*test.*\(`, `(?i)it\(['"].*['"]`, `(?i)describe\(`,
		`(?i)@Test`, `(?i)unittest`, `(?i)pytest`, `(?i)spec\.ts`,

		// Framework patterns
		`(?i)@Component`, `(?i)@Service`, `(?i)@Injectable`, `(?i)@Module`, // Angular
		`(?i)Widget`, `(?i)StatelessWidget`, `(?i)StatefulWidget`, // Flutter
		`(?i)class\s+\w+Controller`, `(?i)class\s+\w+Service`, // General patterns

		// Language-specific quality indicators
		`(?i)interface\s+\w+`, `(?i)type\s+\w+`, `(?i)abstract`, // TypeScript/C#
		`(?i)struct\s+\w+`, `(?i)impl\s+`, `(?i)trait\s+\w+`, // Rust
		`(?i)package\s+\w+`, `(?i)func\s+\w+`, `(?i)goroutine`, // Go
		`(?i)async\s+def`, `(?i)class\s+\w+`, `(?i)__init__`, // Python

		// Database and configuration
		`(?i)select\s+`, `(?i)insert\s+`, `(?i)create\s+table`, // SQL
		`(?i)collection`, `(?i)aggregate`, `(?i)find\(`, // MongoDB
		`(?i)index`, `(?i)mapping`, `(?i)search`, // Elasticsearch
	}
)

func NewQualityAnalyzer() (*QualityAnalyzer, error) {
	if err := godotenv.Load(); err != nil {
		log.Printf("Warning: .env file not found: %v", err)
	}

	db, err := connectPostgreSQL()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to PostgreSQL: %w", err)
	}

	// Compile coding patterns
	compiledPatterns := make(map[string]*regexp.Regexp)
	for name, pattern := range codingPatterns {
		compiledPatterns[name] = regexp.MustCompile(pattern)
	}

	// Compile exclude patterns
	var compiledExcludes []*regexp.Regexp
	for _, pattern := range excludePatterns {
		compiledExcludes = append(compiledExcludes, regexp.MustCompile(pattern))
	}

	return &QualityAnalyzer{
		db:               db,
		securityPatterns: compiledPatterns, // Now contains coding patterns
		excludePatterns:  compiledExcludes,
		languageWeights:  languageWeights,
		minQualityScore:  0.7,  // Only keep high-quality code
		maxFilesPerRepo:  1000, // Prevent processing massive repos
	}, nil
}

func (qa *QualityAnalyzer) AnalyzeRepository(repoPath, repoID, fullName string) (*RepoQuality, error) {
	log.Printf("Analyzing repository quality: %s", fullName)

	quality := &RepoQuality{
		ID:               repoID,
		FullName:         fullName,
		LocalPath:        repoPath,
		Languages:        make(map[string]int),
		SecurityPatterns: make(map[string]int), // Now contains coding patterns
		CreatedAt:        time.Now(),
	}

	// Walk through repository files
	err := filepath.WalkDir(repoPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil // Skip files we can't read
		}

		// Skip if we've hit the file limit
		if quality.TotalFiles >= qa.maxFilesPerRepo {
			return filepath.SkipDir
		}

		// Skip directories and excluded files
		if d.IsDir() || qa.shouldExcludeFile(path) {
			return nil
		}

		quality.TotalFiles++

		// Analyze the file
		if codeFile, err := qa.analyzeFile(path, repoPath); err == nil && codeFile != nil {
			quality.CodeFiles = append(quality.CodeFiles, *codeFile)
			quality.ValidFiles++
			quality.ValidLines += codeFile.Lines
			quality.Languages[codeFile.Language]++

			// Count coding patterns
			for _, pattern := range codeFile.SecurityPatterns { // Field name kept for compatibility
				quality.SecurityPatterns[pattern]++
			}
		}

		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to walk repository: %w", err)
	}

	// Calculate quality metrics
	qa.calculateQualityMetrics(quality)

	// Store results in database
	if err := qa.storeQualityResults(quality); err != nil {
		log.Printf("Failed to store quality results: %v", err)
	}

	log.Printf("Repository %s: Quality=%.2f, Security=%.2f, Files=%d/%d",
		fullName, quality.QualityScore, quality.SecurityScore, quality.ValidFiles, quality.TotalFiles)

	return quality, nil
}

func (qa *QualityAnalyzer) shouldExcludeFile(path string) bool {
	for _, pattern := range qa.excludePatterns {
		if pattern.MatchString(path) {
			return true
		}
	}
	return false
}

func (qa *QualityAnalyzer) analyzeFile(filePath, repoRoot string) (*CodeFile, error) {
	// Get relative path
	relPath, err := filepath.Rel(repoRoot, filePath)
	if err != nil {
		relPath = filePath
	}

	// Detect language
	language := qa.detectLanguage(filePath)
	if language == "" {
		return nil, fmt.Errorf("unsupported language")
	}

	// Read file content
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	// Skip binary files and very large files
	if len(content) == 0 || len(content) > 1024*1024 || qa.isBinaryContent(content) {
		return nil, fmt.Errorf("binary or oversized file")
	}

	contentStr := string(content)
	lines := strings.Count(contentStr, "\n") + 1

	// Skip very small files (likely not meaningful)
	if lines < 10 {
		return nil, fmt.Errorf("file too small")
	}

	codeFile := &CodeFile{
		Path:     relPath,
		Language: language,
		Lines:    lines,
		Content:  contentStr,
	}

	// Find coding patterns
	codeFile.SecurityPatterns = qa.findCodingPatterns(contentStr) // Field name kept for compatibility

	// Calculate code quality
	codeFile.QualityScore = qa.calculateFileQuality(codeFile)
	codeFile.Complexity = qa.calculateComplexity(contentStr, language)

	// Determine if this is high-quality code worth keeping
	codeFile.IsHighQuality = codeFile.QualityScore >= qa.minQualityScore

	return codeFile, nil
}

func (qa *QualityAnalyzer) detectLanguage(filePath string) string {
	ext := strings.ToLower(filepath.Ext(filePath))
	base := strings.ToLower(filepath.Base(filePath))

	langMap := map[string]string{
		".go":  "go",
		".py":  "python",
		".rs":  "rust",
		".c":   "c",
		".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
		".java": "java",
		".js":   "javascript", ".mjs": "javascript",
		".ts":  "typescript",
		".cs":  "csharp",
		".rb":  "ruby",
		".php": "php",
		".sh":  "shell", ".bash": "shell",
		".ps1":   "powershell",
		".pl":    "perl",
		".swift": "swift",
		".kt":    "kotlin",
		".scala": "scala",
		".hs":    "haskell",
		".asm":   "assembly", ".s": "assembly",
	}

	if lang, ok := langMap[ext]; ok {
		return lang
	}

	// Special cases
	if base == "makefile" || base == "dockerfile" {
		return "shell"
	}

	return ""
}

func (qa *QualityAnalyzer) findCodingPatterns(content string) []string {
	var patterns []string
	for name, regex := range qa.securityPatterns { // Field name kept for compatibility
		if regex.MatchString(content) {
			patterns = append(patterns, name)
		}
	}
	return patterns
}

func (qa *QualityAnalyzer) calculateFileQuality(file *CodeFile) float64 {
	score := 0.0

	// Language weight
	if weight, ok := qa.languageWeights[file.Language]; ok {
		score += weight * 0.3
	}

	// Coding pattern bonus
	codingBonus := float64(len(file.SecurityPatterns)) * 0.15 // Field name kept for compatibility
	if codingBonus > 0.5 {
		codingBonus = 0.5 // Cap the bonus
	}
	score += codingBonus

	// File size sweet spot (not too small, not too large)
	if file.Lines >= 50 && file.Lines <= 500 {
		score += 0.2
	} else if file.Lines >= 20 && file.Lines <= 1000 {
		score += 0.1
	}

	// Quality indicators
	qualityCount := 0
	for _, indicator := range qualityIndicators {
		if matched, _ := regexp.MatchString(indicator, file.Content); matched {
			qualityCount++
		}
	}
	score += float64(qualityCount) * 0.05

	// Penalize files with obvious code smells
	if qa.hasCodeSmells(file.Content) {
		score -= 0.3
	}

	// Ensure score is between 0 and 1
	if score > 1.0 {
		score = 1.0
	}
	if score < 0.0 {
		score = 0.0
	}

	return score
}

func (qa *QualityAnalyzer) hasCodeSmells(content string) bool {
	smells := []string{
		`(?i)print\(.*debug`, `(?i)console\.log`, // Debug prints
		`(?i)todo.*hack`, `(?i)fixme.*hack`, // Hack comments
		`(?i)copy.*paste`, `(?i)duplicate`, // Copy-paste indicators
		`(?i)lorem.*ipsum`,     // Placeholder text
		`(?i)test.*test.*test`, // Repetitive test names
	}

	for _, smell := range smells {
		if matched, _ := regexp.MatchString(smell, content); matched {
			return true
		}
	}
	return false
}

func (qa *QualityAnalyzer) calculateComplexity(content, language string) int {
	complexity := 0

	// Count control flow statements
	controlFlow := []string{
		`if\s*\(`, `else`, `while\s*\(`, `for\s*\(`, `switch\s*\(`,
		`case\s+`, `catch\s*\(`, `try\s*{`, `finally\s*{`,
	}

	for _, pattern := range controlFlow {
		matches := regexp.MustCompile(pattern).FindAllString(content, -1)
		complexity += len(matches)
	}

	return complexity
}

func (qa *QualityAnalyzer) isBinaryContent(content []byte) bool {
	// Simple binary detection
	if len(content) == 0 {
		return true
	}

	// Check for null bytes
	nullCount := 0
	for _, b := range content[:min(512, len(content))] {
		if b == 0 {
			nullCount++
		}
	}

	return float64(nullCount)/float64(min(512, len(content))) > 0.01
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (qa *QualityAnalyzer) calculateQualityMetrics(quality *RepoQuality) {
	if quality.ValidFiles == 0 {
		return
	}

	// Basic metrics
	quality.TotalLines = quality.ValidLines
	quality.Metrics.AvgLinesPerFile = float64(quality.ValidLines) / float64(quality.ValidFiles)

	// Calculate language consistency (prefer repos focused on one language)
	maxLangCount := 0
	for _, count := range quality.Languages {
		if count > maxLangCount {
			maxLangCount = count
		}
	}
	quality.Metrics.LanguageConsistency = float64(maxLangCount) / float64(quality.ValidFiles)

	// Coding pattern density
	totalCodingPatterns := 0
	for _, count := range quality.SecurityPatterns { // Field name kept for compatibility
		totalCodingPatterns += count
	}
	quality.Metrics.SecurityDensity = float64(totalCodingPatterns) / float64(quality.ValidFiles) // Field name kept for compatibility

	// Quality score calculation
	qualitySum := 0.0
	securitySum := 0.0
	complexitySum := 0

	for _, file := range quality.CodeFiles {
		qualitySum += file.QualityScore
		securitySum += float64(len(file.SecurityPatterns))
		complexitySum += file.Complexity
	}

	quality.QualityScore = qualitySum / float64(len(quality.CodeFiles))
	quality.SecurityScore = securitySum / float64(len(quality.CodeFiles))
	quality.Metrics.ComplexityScore = float64(complexitySum) / float64(len(quality.CodeFiles))

	// Boost score for repos with strong coding pattern usage
	if quality.SecurityScore > 2.0 { // Field name kept for compatibility
		quality.QualityScore += 0.1
	}

	// Boost score for language consistency
	if quality.Metrics.LanguageConsistency > 0.8 {
		quality.QualityScore += 0.1
	}

	// Cap the quality score
	if quality.QualityScore > 1.0 {
		quality.QualityScore = 1.0
	}
}

func (qa *QualityAnalyzer) storeQualityResults(quality *RepoQuality) error {
	// Store main quality record
	query := `
		INSERT INTO analysis_results (
			repository_id, analysis_type, title, description, confidence_score,
			raw_result, created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7)`

	description := fmt.Sprintf("Quality: %.2f, Coding Patterns: %.2f, Files: %d/%d, Lines: %d",
		quality.QualityScore, quality.SecurityScore, quality.ValidFiles, quality.TotalFiles, quality.ValidLines)

	rawResult, _ := json.Marshal(quality)

	_, err := qa.db.Exec(query,
		quality.ID, "quality_analysis", "Repository Coding Quality Analysis",
		description, quality.QualityScore, rawResult, quality.CreatedAt)

	if err != nil {
		return fmt.Errorf("failed to store quality results: %w", err)
	}

	// Update repository with quality metrics
	updateQuery := `
		UPDATE repositories 
		SET metadata = metadata || $1
		WHERE id = $2`

	metadata := map[string]interface{}{
		"quality_score":     quality.QualityScore,
		"security_score":    quality.SecurityScore,
		"valid_files":       quality.ValidFiles,
		"total_files":       quality.TotalFiles,
		"valid_lines":       quality.ValidLines,
		"languages":         quality.Languages,
		"security_patterns": quality.SecurityPatterns,
		"analyzed_at":       quality.CreatedAt,
	}

	metadataJSON, _ := json.Marshal(metadata)
	_, err = qa.db.Exec(updateQuery, metadataJSON, quality.ID)

	return err
}

func (qa *QualityAnalyzer) GetTopQualityRepos(limit int, minQualityScore float64) ([]RepoQuality, error) {
	query := `
		SELECT r.id, r.full_name, r.local_path, 
		       COALESCE((r.metadata->>'quality_score')::float, 0) as quality_score,
		       COALESCE((r.metadata->>'security_score')::float, 0) as security_score,
		       COALESCE((r.metadata->>'valid_files')::int, 0) as valid_files,
		       COALESCE((r.metadata->>'total_files')::int, 0) as total_files
		FROM repositories r
		WHERE r.download_status = 'downloaded' 
		  AND r.local_path IS NOT NULL
		  AND COALESCE((r.metadata->>'quality_score')::float, 0) >= $1
		ORDER BY 
		  COALESCE((r.metadata->>'quality_score')::float, 0) DESC,
		  COALESCE((r.metadata->>'security_score')::float, 0) DESC,
		  r.stars DESC
		LIMIT $2`

	rows, err := qa.db.Query(query, minQualityScore, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var repos []RepoQuality
	for rows.Next() {
		var repo RepoQuality
		err := rows.Scan(&repo.ID, &repo.FullName, &repo.LocalPath,
			&repo.QualityScore, &repo.SecurityScore, &repo.ValidFiles, &repo.TotalFiles)
		if err != nil {
			continue
		}
		repos = append(repos, repo)
	}

	return repos, nil
}

func (qa *QualityAnalyzer) Close() error {
	if qa.db != nil {
		return qa.db.Close()
	}
	return nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatal("Usage: go run quality_analyzer.go analyze|extract|report [options]")
	}

	analyzer, err := NewQualityAnalyzer()
	if err != nil {
		log.Fatal("Failed to create analyzer:", err)
	}
	defer analyzer.Close()

	command := os.Args[1]

	switch command {
	case "analyze":
		if err := analyzeAllRepos(analyzer); err != nil {
			log.Fatal("Analysis failed:", err)
		}
	case "extract":
		minScore := 0.8
		if len(os.Args) > 2 {
			if _, err := fmt.Sscanf(os.Args[2], "%f", &minScore); err != nil {
				log.Fatal("Invalid quality score:", err)
			}
		}
		if err := extractHighQualityDataset(analyzer, minScore); err != nil {
			log.Fatal("Extraction failed:", err)
		}
	case "report":
		if err := generateQualityReport(analyzer); err != nil {
			log.Fatal("Report generation failed:", err)
		}
	default:
		log.Fatal("Invalid command. Use 'analyze', 'extract', or 'report'")
	}
}

func analyzeAllRepos(analyzer *QualityAnalyzer) error {
	// Get all downloaded repositories
	query := `SELECT id, full_name, local_path FROM repositories 
			  WHERE download_status = 'downloaded' AND local_path IS NOT NULL`

	rows, err := analyzer.db.Query(query)
	if err != nil {
		return err
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		var id, fullName, localPath string
		if err := rows.Scan(&id, &fullName, &localPath); err != nil {
			continue
		}

		// Check if already analyzed
		var analyzed bool
		checkQuery := `SELECT EXISTS(SELECT 1 FROM analysis_results 
					   WHERE repository_id = $1 AND analysis_type = 'quality_analysis')`
		analyzer.db.QueryRow(checkQuery, id).Scan(&analyzed)

		if analyzed {
			log.Printf("Skipping already analyzed repo: %s", fullName)
			continue
		}

		if _, err := analyzer.AnalyzeRepository(localPath, id, fullName); err != nil {
			log.Printf("Failed to analyze %s: %v", fullName, err)
			continue
		}

		count++
		if count%10 == 0 {
			log.Printf("Analyzed %d repositories", count)
		}
	}

	log.Printf("Analysis complete. Processed %d repositories", count)
	return nil
}

func extractHighQualityDataset(analyzer *QualityAnalyzer, minScore float64) error {
	log.Printf("Extracting high-quality dataset with minimum score: %.2f", minScore)

	repos, err := analyzer.GetTopQualityRepos(1000, minScore)
	if err != nil {
		return err
	}

	outputDir := fmt.Sprintf("high_quality_dataset_%.1f", minScore)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return err
	}

	totalFiles := 0
	totalLines := 0

	for _, repo := range repos {
		log.Printf("Processing %s (Quality: %.2f)", repo.FullName, repo.QualityScore)

		// Create output directory for this repo
		repoDir := filepath.Join(outputDir, strings.ReplaceAll(repo.FullName, "/", "_"))
		if err := os.MkdirAll(repoDir, 0755); err != nil {
			continue
		}

		// Re-analyze to get file details
		quality, err := analyzer.AnalyzeRepository(repo.LocalPath, repo.ID, repo.FullName)
		if err != nil {
			log.Printf("Failed to re-analyze %s: %v", repo.FullName, err)
			continue
		}

		// Extract only high-quality files
		fileCount := 0
		for _, file := range quality.CodeFiles {
			if !file.IsHighQuality {
				continue
			}

			outputPath := filepath.Join(repoDir, strings.ReplaceAll(file.Path, "/", "_"))
			if err := os.WriteFile(outputPath, []byte(file.Content), 0644); err != nil {
				continue
			}

			fileCount++
			totalLines += file.Lines
		}

		totalFiles += fileCount
		log.Printf("Extracted %d high-quality files from %s", fileCount, repo.FullName)
	}

	// Create dataset summary
	summary := map[string]interface{}{
		"total_repositories": len(repos),
		"total_files":        totalFiles,
		"total_lines":        totalLines,
		"min_quality_score":  minScore,
		"created_at":         time.Now(),
	}

	summaryJSON, _ := json.MarshalIndent(summary, "", "  ")
	os.WriteFile(filepath.Join(outputDir, "dataset_summary.json"), summaryJSON, 0644)

	log.Printf("Dataset extraction complete: %d repos, %d files, %d lines",
		len(repos), totalFiles, totalLines)

	return nil
}

func generateQualityReport(analyzer *QualityAnalyzer) error {
	// Get quality statistics
	query := `
		SELECT 
			COUNT(*) as total_repos,
			AVG(COALESCE((metadata->>'quality_score')::float, 0)) as avg_quality,
			AVG(COALESCE((metadata->>'security_score')::float, 0)) as avg_security,
			SUM(COALESCE((metadata->>'valid_files')::int, 0)) as total_files,
			SUM(COALESCE((metadata->>'valid_lines')::int, 0)) as total_lines
		FROM repositories 
		WHERE download_status = 'downloaded' 
		  AND metadata IS NOT NULL`

	var stats struct {
		TotalRepos  int
		AvgQuality  float64
		AvgSecurity float64
		TotalFiles  int
		TotalLines  int
	}

	err := analyzer.db.QueryRow(query).Scan(
		&stats.TotalRepos, &stats.AvgQuality, &stats.AvgSecurity,
		&stats.TotalFiles, &stats.TotalLines)

	if err != nil {
		return err
	}

	// Print report
	fmt.Printf("\n=== CODING DATASET QUALITY REPORT ===\n")
	fmt.Printf("Total Repositories Analyzed: %d\n", stats.TotalRepos)
	fmt.Printf("Average Quality Score: %.3f\n", stats.AvgQuality)
	fmt.Printf("Average Coding Pattern Score: %.3f\n", stats.AvgSecurity)
	fmt.Printf("Total Code Files: %d\n", stats.TotalFiles)
	fmt.Printf("Total Lines of Code: %d\n", stats.TotalLines)

	// Get top repositories
	topRepos, err := analyzer.GetTopQualityRepos(20, 0.0)
	if err != nil {
		return err
	}

	fmt.Printf("\n=== TOP 20 HIGHEST QUALITY REPOSITORIES ===\n")
	for i, repo := range topRepos {
		fmt.Printf("%2d. %s (Quality: %.3f, Coding Patterns: %.3f, Files: %d)\n",
			i+1, repo.FullName, repo.QualityScore, repo.SecurityScore, repo.ValidFiles)
	}

	return nil
}
