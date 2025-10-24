package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

// LanguageStats represents statistics for a programming language
type LanguageStats struct {
	Language       string
	FileCount      int64
	TotalSize      int64
	AvgSize        float64
	AvgQuality     float64
	AvgLines       float64
	TopRepos       []RepoStat
	Percentage     float64
	SizePercentage float64
}

// RepoStat represents repository statistics for a language
type RepoStat struct {
	RepoName  string
	FileCount int64
	TotalSize int64
}

// OverallStats represents overall dataset statistics
type OverallStats struct {
	TotalFiles      int64
	TotalSize       int64
	TotalRepos      int64
	AvgQuality      float64
	AvgFileSize     float64
	AvgLinesPerFile float64
	ProcessingTime  time.Duration
	Languages       []LanguageStats
}

type DatasetAnalyzer struct {
	db *sql.DB
}

func NewDatasetAnalyzer(dbURL string) (*DatasetAnalyzer, error) {
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &DatasetAnalyzer{db: db}, nil
}

func (da *DatasetAnalyzer) GetOverallStats() (*OverallStats, error) {
	stats := &OverallStats{}

	// Get overall statistics
	err := da.db.QueryRow(`
		SELECT 
			COUNT(*) as total_files,
			COALESCE(SUM(size), 0) as total_size,
			COUNT(DISTINCT repo_name) as total_repos,
			COALESCE(AVG(quality_score), 0) as avg_quality,
			COALESCE(AVG(size), 0) as avg_file_size,
			COALESCE(AVG(lines), 0) as avg_lines_per_file
		FROM processed_files
	`).Scan(
		&stats.TotalFiles,
		&stats.TotalSize,
		&stats.TotalRepos,
		&stats.AvgQuality,
		&stats.AvgFileSize,
		&stats.AvgLinesPerFile,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get overall stats: %w", err)
	}

	// Get processing time range
	var startTime, endTime sql.NullTime
	err = da.db.QueryRow(`
		SELECT 
			MIN(processed_at) as start_time,
			MAX(processed_at) as end_time
		FROM processed_files
	`).Scan(&startTime, &endTime)
	if err == nil && startTime.Valid && endTime.Valid {
		stats.ProcessingTime = endTime.Time.Sub(startTime.Time)
	}

	return stats, nil
}

func (da *DatasetAnalyzer) GetLanguageStats(totalFiles, totalSize int64) ([]LanguageStats, error) {
	// Get language statistics
	rows, err := da.db.Query(`
		SELECT 
			language,
			COUNT(*) as file_count,
			COALESCE(SUM(size), 0) as total_size,
			COALESCE(AVG(size), 0) as avg_size,
			COALESCE(AVG(quality_score), 0) as avg_quality,
			COALESCE(AVG(lines), 0) as avg_lines
		FROM processed_files
		GROUP BY language
		ORDER BY file_count DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to get language stats: %w", err)
	}
	defer rows.Close()

	var languages []LanguageStats
	for rows.Next() {
		var lang LanguageStats
		err := rows.Scan(
			&lang.Language,
			&lang.FileCount,
			&lang.TotalSize,
			&lang.AvgSize,
			&lang.AvgQuality,
			&lang.AvgLines,
		)
		if err != nil {
			continue
		}

		// Calculate percentages
		lang.Percentage = float64(lang.FileCount) / float64(totalFiles) * 100
		lang.SizePercentage = float64(lang.TotalSize) / float64(totalSize) * 100

		// Get top repositories for this language
		lang.TopRepos = da.getTopReposForLanguage(lang.Language, 5)

		languages = append(languages, lang)
	}

	return languages, nil
}

func (da *DatasetAnalyzer) getTopReposForLanguage(language string, limit int) []RepoStat {
	rows, err := da.db.Query(`
		SELECT 
			repo_name,
			COUNT(*) as file_count,
			COALESCE(SUM(size), 0) as total_size
		FROM processed_files
		WHERE language = $1
		GROUP BY repo_name
		ORDER BY file_count DESC
		LIMIT $2
	`, language, limit)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var repos []RepoStat
	for rows.Next() {
		var repo RepoStat
		if err := rows.Scan(&repo.RepoName, &repo.FileCount, &repo.TotalSize); err != nil {
			continue
		}
		repos = append(repos, repo)
	}

	return repos
}

func (da *DatasetAnalyzer) GetQualityDistribution() (map[string]int64, error) {
	rows, err := da.db.Query(`
		SELECT 
			CASE 
				WHEN quality_score >= 90 THEN 'Excellent (90-100)'
				WHEN quality_score >= 80 THEN 'Good (80-89)'
				WHEN quality_score >= 70 THEN 'Fair (70-79)'
				WHEN quality_score >= 60 THEN 'Poor (60-69)'
				ELSE 'Very Poor (0-59)'
			END as quality_tier,
			COUNT(*) as file_count
		FROM processed_files
		GROUP BY quality_tier
		ORDER BY 
			CASE 
				WHEN quality_score >= 90 THEN 1
				WHEN quality_score >= 80 THEN 2
				WHEN quality_score >= 70 THEN 3
				WHEN quality_score >= 60 THEN 4
				ELSE 5
			END
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	distribution := make(map[string]int64)
	for rows.Next() {
		var tier string
		var count int64
		if err := rows.Scan(&tier, &count); err != nil {
			continue
		}
		distribution[tier] = count
	}

	return distribution, nil
}

func (da *DatasetAnalyzer) GetRecentActivity(hours int) ([]map[string]interface{}, error) {
	rows, err := da.db.Query(`
		SELECT 
			DATE_TRUNC('hour', processed_at) as hour,
			language,
			COUNT(*) as files_processed,
			COALESCE(SUM(size), 0) as bytes_processed
		FROM processed_files
		WHERE processed_at >= NOW() - INTERVAL '%d hours'
		GROUP BY hour, language
		ORDER BY hour DESC, files_processed DESC
		LIMIT 20
	`, hours)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var activity []map[string]interface{}
	for rows.Next() {
		var hour time.Time
		var language string
		var filesProcessed, bytesProcessed int64

		if err := rows.Scan(&hour, &language, &filesProcessed, &bytesProcessed); err != nil {
			continue
		}

		activity = append(activity, map[string]interface{}{
			"hour":            hour.Format("2006-01-02 15:04"),
			"language":        language,
			"files_processed": filesProcessed,
			"bytes_processed": bytesProcessed,
		})
	}

	return activity, nil
}

func formatBytes(bytes int64) string {
	const unit = 1024
	if bytes < unit {
		return fmt.Sprintf("%d B", bytes)
	}
	div, exp := int64(unit), 0
	for n := bytes / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(bytes)/float64(div), "KMGTPE"[exp])
}

func formatNumber(n int64) string {
	str := fmt.Sprintf("%d", n)
	var result []string
	for i, char := range str {
		if i > 0 && (len(str)-i)%3 == 0 {
			result = append(result, ",")
		}
		result = append(result, string(char))
	}
	return strings.Join(result, "")
}

func printBar(percentage float64, width int) string {
	filled := int(percentage / 100 * float64(width))
	bar := strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
	return fmt.Sprintf("[%s] %.1f%%", bar, percentage)
}

func (da *DatasetAnalyzer) PrintDetailedReport() error {
	fmt.Printf("🔍 CODELUPE DATASET ANALYZER\n")
	fmt.Printf("============================================================\n\n")

	// Get overall statistics
	stats, err := da.GetOverallStats()
	if err != nil {
		return err
	}

	// Get language statistics
	languages, err := da.GetLanguageStats(stats.TotalFiles, stats.TotalSize)
	if err != nil {
		return err
	}
	stats.Languages = languages

	// Print overall summary
	fmt.Printf("📊 DATASET OVERVIEW\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	fmt.Printf("Total Files:        %s\n", formatNumber(stats.TotalFiles))
	fmt.Printf("Total Size:         %s\n", formatBytes(stats.TotalSize))
	fmt.Printf("Total Repositories: %s\n", formatNumber(stats.TotalRepos))
	fmt.Printf("Languages:          %d\n", len(languages))
	fmt.Printf("Avg Quality Score:  %.1f/100\n", stats.AvgQuality)
	fmt.Printf("Avg File Size:      %s\n", formatBytes(int64(stats.AvgFileSize)))
	fmt.Printf("Avg Lines/File:     %.0f\n", stats.AvgLinesPerFile)
	if stats.ProcessingTime > 0 {
		fmt.Printf("Processing Time:    %v\n", stats.ProcessingTime.Truncate(time.Second))
		rate := float64(stats.TotalFiles) / stats.ProcessingTime.Seconds()
		fmt.Printf("Processing Rate:    %.0f files/sec\n", rate)
	}
	fmt.Printf("\n")

	// Print language distribution
	fmt.Printf("🔤 LANGUAGE DISTRIBUTION\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	fmt.Printf("%-15s %12s %8s %12s %8s %8s\n",
		"Language", "Files", "Percent", "Size", "Quality", "Avg Lines")
	fmt.Printf("──────────────────────────────────────────────────────────\n")

	for i, lang := range languages {
		if i >= 15 { // Show top 15 languages
			break
		}
		fmt.Printf("%-15s %12s %8.1f%% %12s %8.0f %8.0f\n",
			lang.Language,
			formatNumber(lang.FileCount),
			lang.Percentage,
			formatBytes(lang.TotalSize),
			lang.AvgQuality,
			lang.AvgLines,
		)
	}

	// Show visual bars for top languages
	fmt.Printf("\n📈 TOP LANGUAGES (Visual)\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	for i, lang := range languages {
		if i >= 10 { // Show top 10 with bars
			break
		}
		fmt.Printf("%-12s %s\n", lang.Language, printBar(lang.Percentage, 40))
	}

	// Print quality distribution
	fmt.Printf("\n🏆 QUALITY DISTRIBUTION\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	qualityDist, err := da.GetQualityDistribution()
	if err == nil {
		// Sort quality tiers
		tiers := []string{
			"Excellent (90-100)",
			"Good (80-89)",
			"Fair (70-79)",
			"Poor (60-69)",
			"Very Poor (0-59)",
		}

		for _, tier := range tiers {
			if count, exists := qualityDist[tier]; exists {
				percentage := float64(count) / float64(stats.TotalFiles) * 100
				fmt.Printf("%-20s %10s %s\n",
					tier,
					formatNumber(count),
					printBar(percentage, 30))
			}
		}
	}

	// Print top repositories for each major language
	fmt.Printf("\n🏗️  TOP REPOSITORIES BY LANGUAGE\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	for i, lang := range languages {
		if i >= 5 || lang.FileCount < 100 { // Top 5 languages with significant files
			break
		}

		fmt.Printf("\n%s (%s files):\n", lang.Language, formatNumber(lang.FileCount))
		for j, repo := range lang.TopRepos {
			if j >= 3 { // Top 3 repos per language
				break
			}
			fmt.Printf("  %d. %-30s %8s files (%s)\n",
				j+1, repo.RepoName, formatNumber(repo.FileCount), formatBytes(repo.TotalSize))
		}
	}

	// Print recent activity
	fmt.Printf("\n⏰ RECENT PROCESSING ACTIVITY (Last 24 Hours)\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")
	activity, err := da.GetRecentActivity(24)
	if err == nil && len(activity) > 0 {
		fmt.Printf("%-16s %-12s %12s %12s\n", "Time", "Language", "Files", "Size")
		fmt.Printf("──────────────────────────────────────────────────────────\n")
		for i, act := range activity {
			if i >= 10 { // Show last 10 hours
				break
			}
			fmt.Printf("%-16s %-12s %12s %12s\n",
				act["hour"].(string),
				act["language"].(string),
				formatNumber(act["files_processed"].(int64)),
				formatBytes(act["bytes_processed"].(int64)),
			)
		}
	} else {
		fmt.Printf("No recent activity found.\n")
	}

	fmt.Printf("\n🎯 TRAINING DATASET INSIGHTS\n")
	fmt.Printf("──────────────────────────────────────────────────────────\n")

	// Calculate insights
	pythonPercentage := 0.0
	jsPercentage := 0.0
	totalHighQuality := int64(0)

	for _, lang := range languages {
		if lang.Language == "Python" {
			pythonPercentage = lang.Percentage
		} else if lang.Language == "JavaScript" || lang.Language == "TypeScript" {
			jsPercentage += lang.Percentage
		}
	}

	if dist, err := da.GetQualityDistribution(); err == nil {
		totalHighQuality = dist["Excellent (90-100)"] + dist["Good (80-89)"]
	}

	fmt.Printf("• Python dominance: %.1f%% of dataset\n", pythonPercentage)
	fmt.Printf("• JS/TS combined: %.1f%% of dataset\n", jsPercentage)
	fmt.Printf("• High quality files: %s (%.1f%%)\n",
		formatNumber(totalHighQuality),
		float64(totalHighQuality)/float64(stats.TotalFiles)*100)
	fmt.Printf("• Average repo size: %s\n", formatBytes(stats.TotalSize/stats.TotalRepos))
	fmt.Printf("• Estimated training size: %s\n", formatBytes(stats.TotalSize))

	if stats.TotalFiles > 1000000 {
		fmt.Printf("• Dataset scale: LARGE (>1M files) - Excellent for training\n")
	} else if stats.TotalFiles > 100000 {
		fmt.Printf("• Dataset scale: MEDIUM (>100K files) - Good for training\n")
	} else {
		fmt.Printf("• Dataset scale: SMALL (<100K files) - Consider more data\n")
	}

	fmt.Printf("\n✅ Analysis complete! This dataset is ready for training.\n")

	return nil
}

func main() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://coding_user:coding_pass@localhost:5432/coding_db?sslmode=disable"
	}

	fmt.Printf("🔗 Connecting to database...\n")
	analyzer, err := NewDatasetAnalyzer(dbURL)
	if err != nil {
		log.Fatalf("❌ Failed to create analyzer: %v", err)
	}
	defer analyzer.db.Close()

	// Check if we have data
	var count int64
	err = analyzer.db.QueryRow("SELECT COUNT(*) FROM processed_files").Scan(&count)
	if err != nil {
		log.Fatalf("❌ Failed to check database: %v", err)
	}

	if count == 0 {
		fmt.Printf("⚠️  No processed files found in database.\n")
		fmt.Printf("   Run the processor first to analyze data.\n")
		return
	}

	fmt.Printf("✅ Found %s processed files. Analyzing...\n\n", formatNumber(count))

	// Generate detailed report
	if err := analyzer.PrintDetailedReport(); err != nil {
		log.Fatalf("❌ Failed to generate report: %v", err)
	}
}
