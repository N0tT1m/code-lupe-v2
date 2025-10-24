package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"codelupe/pkg/metrics"

	"github.com/PuerkitoBio/goquery"
	"github.com/elastic/go-elasticsearch/v8"
	"github.com/elastic/go-elasticsearch/v8/esapi"
	"golang.org/x/time/rate"
)

type Repository struct {
	Name        string     `json:"name"`
	FullName    string     `json:"full_name"`
	Description string     `json:"description"`
	URL         string     `json:"url"`
	Language    string     `json:"language"`
	Stars       int        `json:"stars"`
	Forks       int        `json:"forks"`
	LastUpdated *time.Time `json:"last_updated"`
	Topics      []string   `json:"topics"`
	CrawledAt   time.Time  `json:"crawled_at"`
}

type Crawler struct {
	client      *http.Client
	esClient    *elasticsearch.Client
	rateLimiter *rate.Limiter
	mu          sync.Mutex
	crawled     map[string]bool
	shutdown    int32
	ctx         context.Context
	cancel      context.CancelFunc
	stats       *CrawlerStats
}

type CrawlerStats struct {
	mu             sync.RWMutex
	totalIndexed   int64
	totalErrors    int64
	termsProcessed int64
	pagesProcessed int64
	startTime      time.Time
	lastReported   time.Time
}

// cleanLanguageString removes percentage indicators and extra whitespace from language strings
// For multi-language repos like "Rust 80% Python 15% Shell 5%", it returns the primary language (first/highest %)
func cleanLanguageString(lang string) string {
	// Split by newlines and take the first part (before percentage)
	lines := strings.Split(lang, "\n")
	if len(lines) > 0 {
		lang = lines[0]
	}

	// Handle multi-language format like "Rust 80% Python 15% Shell 5%"
	// Find the first percentage and extract everything before it
	if idx := strings.Index(lang, "%"); idx > 0 {
		// Look backwards from % to find the start of percentage
		for i := idx - 1; i >= 0; i-- {
			if lang[i] < '0' || lang[i] > '9' {
				if lang[i] != '.' && lang[i] != ' ' {
					lang = strings.TrimSpace(lang[:i+1])
					break
				}
			}
		}
	}

	// Clean up common patterns
	lang = strings.TrimSpace(lang)

	// Remove trailing spaces and numbers/percentages
	for len(lang) > 0 {
		lastChar := lang[len(lang)-1]
		if lastChar == ' ' || lastChar == '%' || (lastChar >= '0' && lastChar <= '9') || lastChar == '.' {
			lang = lang[:len(lang)-1]
		} else {
			break
		}
	}

	return strings.TrimSpace(lang)
}

var codingSearchTerms = []string{
	// Core Programming Languages - Primary Focus
	"rust", "rust-lang", "rustlang", "cargo", "rust-programming", "rust-development",
	"golang", "go-lang", "go-programming", "go-development", "go-modules", "goroutines",
	"python", "python3", "python-programming", "python-development", "pip", "conda",
	"typescript", "ts", "typescript-programming", "deno", "bun",
	"javascript", "js", "nodejs", "node-js", "npm", "yarn", "pnpm",
	"dart", "dart-lang", "dart-programming", "flutter-dart",

	// AI & Machine Learning
	"artificial-intelligence", "ai", "machine-learning", "ml", "deep-learning", "dl",
	"neural-networks", "neural-network", "tensorflow", "pytorch", "keras", "scikit-learn",
	"sklearn", "pandas", "numpy", "matplotlib", "seaborn", "jupyter", "notebook",
	"data-science", "data-analysis", "data-mining", "data-visualization", "plotly",
	"opencv", "computer-vision", "nlp", "natural-language-processing", "huggingface",
	"transformers", "bert", "gpt", "llm", "large-language-model", "generative-ai",
	"reinforcement-learning", "supervised-learning", "unsupervised-learning",
	"gradient-boosting", "xgboost", "lightgbm", "catboost", "ensemble-methods",

	// Frontend Frameworks & Libraries
	"angular", "angular2", "angular-cli", "rxjs", "angular-material", "ngrx",
	"react", "reactjs", "react-hooks", "react-router", "redux", "next-js", "gatsby",
	"vue", "vuejs", "vue3", "nuxt", "vuex", "pinia",
	"svelte", "sveltekit", "solid-js", "alpine-js",
	"flutter", "flutter-framework", "flutter-ui", "flutter-mobile", "flutter-web",
	"react-native", "ionic", "cordova", "phonegap",

	// Backend Frameworks & Libraries
	"express", "express-js", "koa", "fastify", "nest-js", "hapi",
	"django", "flask", "fastapi", "tornado", "pyramid", "bottle",
	"spring", "spring-boot", "spring-framework", "hibernate", "jpa",
	"gin", "echo", "fiber", "beego", "iris", "gorilla-mux",
	"actix", "axum", "warp", "rocket", "tokio", "async-std",
	"rails", "ruby-on-rails", "sinatra", "hanami",
	"laravel", "symfony", "codeigniter", "cakephp", "zend",
	"asp-net", "dotnet", "entity-framework", "blazor",

	// Databases - Primary Focus
	"postgresql", "postgres", "pg", "postgis", "postgres-sql",
	"mssql", "sql-server", "microsoft-sql-server", "t-sql", "sqlcmd",
	"elasticsearch", "elastic", "kibana", "logstash", "elastic-stack", "elk",
	"mongodb", "mongo", "mongoose", "mongo-db", "nosql", "document-database",
	"mysql", "mariadb", "sqlite", "redis", "memcached", "cassandra",
	"neo4j", "graph-database", "dynamodb", "cosmosdb", "firestore",
	"influxdb", "timescaledb", "clickhouse", "bigquery", "snowflake",

	// Development Tools & Platforms
	"docker", "docker-compose", "dockerfile", "containers", "containerization",
	"kubernetes", "k8s", "helm", "kubectl", "minikube", "kind",
	"terraform", "ansible", "vagrant", "puppet", "chef", "salt",
	"jenkins", "github-actions", "gitlab-ci", "circleci", "travis-ci",
	"git", "github", "gitlab", "bitbucket", "version-control", "git-flow",
	"vscode", "visual-studio-code", "intellij", "sublime-text", "atom",
	"webpack", "vite", "rollup", "parcel", "esbuild", "turbopack",
	"babel", "prettier", "eslint", "tslint", "stylelint", "husky",

	// Cloud & Infrastructure
	"aws", "amazon-web-services", "s3", "ec2", "lambda", "dynamodb",
	"azure", "microsoft-azure", "azure-functions", "blob-storage",
	"gcp", "google-cloud", "google-cloud-platform", "firebase", "firestore",
	"heroku", "netlify", "vercel", "digital-ocean", "linode", "vultr",
	"serverless", "faas", "functions-as-a-service", "microservices",
	"graphql", "apollo", "relay", "prisma", "hasura", "supabase",

	// Testing & Quality Assurance
	"testing", "unit-testing", "integration-testing", "e2e-testing",
	"jest", "mocha", "chai", "jasmine", "karma", "protractor",
	"pytest", "unittest", "nose", "tox", "coverage", "mock",
	"junit", "testng", "mockito", "selenium", "webdriver",
	"cypress", "playwright", "puppeteer", "webdriverio",
	"test-driven-development", "tdd", "behavior-driven-development", "bdd",
	"continuous-integration", "ci", "continuous-deployment", "cd",

	// Architecture & Design Patterns
	"design-patterns", "solid-principles", "clean-architecture", "hexagonal-architecture",
	"mvc", "mvp", "mvvm", "observer-pattern", "singleton-pattern", "factory-pattern",
	"dependency-injection", "inversion-of-control", "repository-pattern",
	"event-driven-architecture", "event-sourcing", "cqrs", "saga-pattern",
	"microservices-architecture", "monolith", "distributed-systems",
	"load-balancing", "caching", "performance-optimization", "scalability",

	// Specific Programming Concepts
	"algorithms", "data-structures", "sorting-algorithms", "graph-algorithms",
	"dynamic-programming", "greedy-algorithms", "divide-and-conquer",
	"binary-search", "hash-tables", "linked-lists", "trees", "graphs",
	"concurrent-programming", "parallel-programming", "multithreading",
	"asynchronous-programming", "async-await", "promises", "futures",
	"functional-programming", "object-oriented-programming", "procedural-programming",

	// API & Communication
	"rest-api", "restful", "graphql", "grpc", "websockets", "sse",
	"json", "xml", "yaml", "protobuf", "avro", "msgpack",
	"swagger", "openapi", "postman", "insomnia", "api-testing",
	"oauth", "jwt", "authentication", "authorization", "security",

	// Mobile Development
	"android", "android-development", "kotlin", "java-android",
	"ios", "ios-development", "swift", "objective-c", "xcode",
	"flutter-mobile", "react-native", "xamarin", "ionic-mobile",
	"cordova", "phonegap", "native-script", "expo",

	// Game Development
	"game-development", "unity", "unreal-engine", "godot", "pygame",
	"game-engine", "3d-graphics", "opengl", "vulkan", "directx",
	"shader-programming", "game-physics", "collision-detection",

	// Data Engineering & Big Data
	"data-engineering", "etl", "data-pipeline", "apache-spark", "hadoop",
	"kafka", "apache-kafka", "stream-processing", "batch-processing",
	"airflow", "luigi", "prefect", "dagster", "dbt", "data-build-tool",
	"pandas", "dask", "polars", "pyspark", "scala-spark",

	// DevOps & Monitoring
	"devops", "sre", "site-reliability-engineering", "monitoring",
	"prometheus", "grafana", "jaeger", "zipkin", "new-relic", "datadog",
	"logging", "log-aggregation", "fluentd", "logstash", "beats",
	"infrastructure-as-code", "iac", "configuration-management",

	// Security & Cryptography
	"cryptography", "encryption", "hashing", "ssl", "tls", "certificates",
	"oauth2", "openid-connect", "saml", "ldap", "active-directory",
	"security-best-practices", "vulnerability-assessment", "penetration-testing",

	// Programming Paradigms & Methodologies
	"agile", "scrum", "kanban", "lean", "extreme-programming", "xp",
	"pair-programming", "code-review", "refactoring", "technical-debt",
	"clean-code", "code-quality", "static-analysis", "linting",

	// Emerging Technologies
	"blockchain", "smart-contracts", "ethereum", "solidity", "web3",
	"cryptocurrency", "defi", "nft", "decentralized-applications", "dapps",
	"quantum-computing", "quantum-algorithms", "qiskit",
	"augmented-reality", "ar", "virtual-reality", "vr", "mixed-reality",
	"iot", "internet-of-things", "embedded-systems", "raspberry-pi", "arduino",

	// Language-Specific Ecosystems
	"rust-actix", "rust-tokio", "rust-serde", "rust-diesel", "rust-wasm",
	"rust-embedded", "rust-async", "rust-web-assembly", "rust-cli",
	"go-gin", "go-echo", "go-gorilla", "go-gorm", "go-cobra", "go-viper",
	"go-microservices", "go-concurrency", "go-channels", "go-context",
	"python-django", "python-flask", "python-fastapi", "python-asyncio",
	"python-celery", "python-requests", "python-sqlalchemy", "python-pydantic",
	"typescript-node", "typescript-react", "typescript-angular", "typescript-vue",
	"typescript-express", "typescript-nestjs", "typescript-graphql",

	// Development Workflows
	"gitflow", "github-flow", "trunk-based-development", "feature-branches",
	"code-review", "pull-requests", "merge-requests", "pair-programming",
	"continuous-integration", "continuous-deployment", "automated-testing",
	"deployment-strategies", "blue-green-deployment", "canary-deployment",

	// Performance & Optimization
	"performance-optimization", "profiling", "benchmarking", "load-testing",
	"memory-management", "garbage-collection", "caching-strategies",
	"database-optimization", "query-optimization", "indexing",
	"cdn", "content-delivery-network", "edge-computing",

	// Documentation & Communication
	"documentation", "technical-writing", "api-documentation", "readme",
	"markdown", "gitbook", "confluence", "notion", "wiki",
	"code-comments", "inline-documentation", "docstrings",

	// Learning & Education
	"coding-bootcamp", "programming-tutorial", "coding-interview",
	"algorithm-practice", "competitive-programming", "leetcode",
	"coding-challenges", "programming-exercises", "code-kata",
	"open-source", "open-source-contribution", "hacktoberfest",

	// Specific Tools & Libraries
	"axios", "fetch", "lodash", "moment", "date-fns", "uuid",
	"bcrypt", "jsonwebtoken", "passport", "helmet", "cors",
	"express-validator", "joi", "yup", "formik", "react-hook-form",
	"styled-components", "emotion", "tailwindcss", "bootstrap", "material-ui",
	"ant-design", "chakra-ui", "semantic-ui", "bulma", "foundation",
}

func NewCrawler() (*Crawler, error) {
	// Get Elasticsearch URL from environment with retry logic
	esURL := os.Getenv("ELASTICSEARCH_URL")
	if esURL == "" {
		esURL = "http://elasticsearch:9200"
	}

	log.Printf("Connecting to Elasticsearch at: %s", esURL)

	var esClient *elasticsearch.Client
	var err error

	// Retry connection with exponential backoff
	for i := 0; i < 10; i++ {
		esClient, err = elasticsearch.NewClient(elasticsearch.Config{
			Addresses:     []string{esURL},
			RetryOnStatus: []int{502, 503, 504, 429},
			MaxRetries:    5,
		})
		if err == nil {
			// Test the connection
			_, err = esClient.Info()
			if err == nil {
				log.Printf("Successfully connected to Elasticsearch")
				break
			}
		}

		waitTime := time.Duration(1<<uint(i)) * time.Second
		if waitTime > 30*time.Second {
			waitTime = 30 * time.Second
		}
		log.Printf("Elasticsearch not ready (attempt %d/10), waiting %v: %v", i+1, waitTime, err)
		time.Sleep(waitTime)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to create Elasticsearch client after retries: %w", err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	// Create HTTP client with connection pooling for better performance
	httpClient := &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     90 * time.Second,
			DisableKeepAlives:   false,
			ForceAttemptHTTP2:   true,
		},
	}

	return &Crawler{
		client:      httpClient,
		esClient:    esClient,
		rateLimiter: rate.NewLimiter(rate.Every(3*time.Second), 1),
		crawled:     make(map[string]bool),
		ctx:         ctx,
		cancel:      cancel,
		stats:       &CrawlerStats{startTime: time.Now(), lastReported: time.Now()},
	}, nil
}

func parseNumber(s string) (int, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0, fmt.Errorf("empty string")
	}

	s = strings.ReplaceAll(s, ",", "")

	if strings.HasSuffix(strings.ToLower(s), "k") {
		numStr := strings.TrimSuffix(strings.ToLower(s), "k")
		if num, err := strconv.ParseFloat(numStr, 64); err == nil {
			return int(num * 1000), nil
		}
	}

	if strings.HasSuffix(strings.ToLower(s), "m") {
		numStr := strings.TrimSuffix(strings.ToLower(s), "m")
		if num, err := strconv.ParseFloat(numStr, 64); err == nil {
			return int(num * 1000000), nil
		}
	}

	return strconv.Atoi(s)
}

func (c *Crawler) searchGitHub(term string, page int) ([]*Repository, error) {
	if atomic.LoadInt32(&c.shutdown) == 1 {
		return nil, fmt.Errorf("crawler is shutting down")
	}

	if err := c.rateLimiter.Wait(c.ctx); err != nil {
		return nil, err
	}

	searchURL := fmt.Sprintf("https://github.com/search?q=%s&type=repositories&p=%d",
		url.QueryEscape(term), page)

	req, err := http.NewRequestWithContext(c.ctx, "GET", searchURL, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; CodeCrawler/1.0)")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 429 {
		return nil, c.handleRateLimit(resp)
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return nil, err
	}

	return c.parseRepositories(doc)
}

func (c *Crawler) parseRepositories(doc *goquery.Document) ([]*Repository, error) {
	var repos []*Repository

	repoElements := doc.Find("div.search-title")
	if repoElements.Length() == 0 {
		repoElements = doc.Find("h3.f4")
	}
	if repoElements.Length() == 0 {
		repoElements = doc.Find("article.Box-row, div.Box-row")
	}

	if repoElements.Length() == 0 {
		return nil, fmt.Errorf("no repository elements found on page")
	}

	repoElements.Each(func(i int, s *goquery.Selection) {
		var repoLink *goquery.Selection

		if s.Is("div.search-title") {
			repoLink = s.Find("a").First()
		} else {
			repoLink = s.Find("a[data-testid='results-list-repo-path']").First()
			if repoLink.Length() == 0 {
				repoLink = s.Find("a").First()
			}
		}

		href, exists := repoLink.Attr("href")
		if !exists {
			return
		}

		c.mu.Lock()
		if c.crawled[href] {
			c.mu.Unlock()
			return
		}
		c.crawled[href] = true
		c.mu.Unlock()

		fullName := strings.TrimPrefix(href, "/")
		parts := strings.Split(fullName, "/")
		if len(parts) != 2 {
			return
		}

		repo := &Repository{
			Name:      parts[1],
			FullName:  fullName,
			URL:       "https://github.com" + href,
			CrawledAt: time.Now(),
		}

		parent := s.Parent()
		for parent.Length() > 0 && !parent.Is("div.Box-row") && !parent.HasClass("search-result-item") {
			parent = parent.Parent()
			if parent.Is("body") || parent.HasClass("application-main") {
				parent = s.Parent()
				break
			}
		}

		desc := parent.Find("p, .text-gray").First().Text()
		repo.Description = strings.TrimSpace(desc)

		// Try multiple selectors for language in search results
		langSelectors := []string{
			"span[itemprop='programmingLanguage']",
			".ml-0.mr-3",
			"[data-search-type='code'] span",
			".text-gray span:first-child",
			".f6 span:first-child",
		}

		for _, selector := range langSelectors {
			langSpan := parent.Find(selector).First()
			if langSpan.Length() > 0 {
				lang := strings.TrimSpace(langSpan.Text())
				if lang != "" && !strings.Contains(lang, "Update") && !strings.Contains(lang, "ago") {
					// Clean up language string - remove percentages and extra whitespace
					lang = cleanLanguageString(lang)
					if lang != "" {
						repo.Language = lang
						break
					}
				}
			}
		}

		repos = append(repos, repo)
	})

	return repos, nil
}

func (c *Crawler) scrapeRepoDetails(repo *Repository) error {
	startTime := time.Now()

	if atomic.LoadInt32(&c.shutdown) == 1 {
		return fmt.Errorf("crawler is shutting down")
	}

	if err := c.rateLimiter.Wait(c.ctx); err != nil {
		metrics.IncrCounter("crawler_scrape_errors_total", 1)
		return err
	}

	req, err := http.NewRequestWithContext(c.ctx, "GET", repo.URL, nil)
	if err != nil {
		return err
	}

	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; CodeCrawler/1.0)")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 429 {
		return c.handleRateLimit(resp)
	}

	if resp.StatusCode != 200 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return err
	}

	description := doc.Find("p.f4.my-3, [data-pjax] p").First().Text()
	if description != "" {
		repo.Description = strings.TrimSpace(description)
	}

	starsText := ""
	starsSelectors := []string{
		"#repo-stars-counter-star",
		"a[href*='/stargazers'] strong",
		"a[href*='/stargazers'] .Counter",
		".social-count",
	}

	for _, selector := range starsSelectors {
		elem := doc.Find(selector).First()
		if elem.Length() > 0 {
			starsText = strings.TrimSpace(elem.Text())
			break
		}
	}

	if starsText != "" {
		if stars, err := parseNumber(starsText); err == nil {
			repo.Stars = stars
		}
	}

	forksText := ""
	forksSelectors := []string{
		"#repo-network-counter",
		"a[href*='/forks'] strong",
		"a[href*='/network'] strong",
		"a[href*='/forks'] .Counter",
		"a[href*='/network'] .Counter",
	}

	for _, selector := range forksSelectors {
		elem := doc.Find(selector).First()
		if elem.Length() > 0 {
			forksText = strings.TrimSpace(elem.Text())
			break
		}
	}

	if forksText != "" {
		if forks, err := parseNumber(forksText); err == nil {
			repo.Forks = forks
		}
	}

	topics := []string{}
	doc.Find("a.topic-tag, .topic-tag").Each(func(i int, s *goquery.Selection) {
		topic := strings.TrimSpace(s.Text())
		if topic != "" {
			topics = append(topics, topic)
		}
	})
	repo.Topics = topics

	// Try multiple selectors for language detection
	langSelectors := []string{
		"span[itemprop='programmingLanguage']",
		".BorderGrid-cell .ml-0.mr-3",
		".f6.color-fg-muted .ml-0.mr-3",
		"[data-testid='repository-topics'] + div span",
		".repository-lang-stats-graph .d-inline-block",
		".repository-lang-stats-graph + .mt-2 span",
		"[data-ga-click*='language']",
		".Layout-sidebar .BorderGrid .BorderGrid-cell:first-child span.color-fg-default",
	}

	for _, selector := range langSelectors {
		langElem := doc.Find(selector).First()
		if langElem.Length() > 0 {
			lang := strings.TrimSpace(langElem.Text())
			if lang != "" && !strings.Contains(lang, "Update") && !strings.Contains(lang, "ago") {
				// Clean up language string - remove percentages and extra whitespace
				lang = cleanLanguageString(lang)
				if lang != "" {
					repo.Language = lang
					log.Printf("DEBUG: Found language '%s' for %s using selector: %s", lang, repo.FullName, selector)
					break
				}
			}
		}
	}

	log.Printf("DEBUG: Scraped %s - Stars: %d, Forks: %d, Topics: %v",
		repo.FullName, repo.Stars, repo.Forks, repo.Topics)

	// Record metrics
	duration := time.Since(startTime).Seconds()
	metrics.ObserveHistogram("crawler_scrape_duration_seconds", duration)
	metrics.IncrCounter("crawler_repos_scraped_total", 1)

	return nil
}

func (c *Crawler) handleRateLimit(resp *http.Response) error {
	retryAfter := resp.Header.Get("Retry-After")
	if retryAfter == "" {
		retryAfter = "60"
	}

	waitTime, err := strconv.Atoi(retryAfter)
	if err != nil {
		waitTime = 60
	}

	log.Printf("Rate limited. Waiting %d seconds before retry...", waitTime)
	c.printStats()

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	select {
	case <-time.After(time.Duration(waitTime) * time.Second):
		return fmt.Errorf("rate limited, waited %d seconds", waitTime)
	case <-ticker.C:
		c.printStats()
		return fmt.Errorf("rate limited, stats printed")
	case <-c.ctx.Done():
		return c.ctx.Err()
	}
}

func (c *Crawler) exponentialBackoff(attempt int) time.Duration {
	base := 2.0
	maxDelay := 300 * time.Second
	delay := time.Duration(math.Pow(base, float64(attempt))) * time.Second
	if delay > maxDelay {
		delay = maxDelay
	}
	return delay
}

func (c *Crawler) printStats() {
	c.stats.mu.RLock()
	elapsed := time.Since(c.stats.startTime)
	sinceLastReport := time.Since(c.stats.lastReported)
	totalIndexed := c.stats.totalIndexed
	totalErrors := c.stats.totalErrors
	termsProcessed := c.stats.termsProcessed
	pagesProcessed := c.stats.pagesProcessed
	c.stats.mu.RUnlock()

	log.Printf("📊 CRAWLER STATS - Elapsed: %v, Since last report: %v", elapsed.Round(time.Second), sinceLastReport.Round(time.Second))
	log.Printf("   Repositories indexed: %d", totalIndexed)
	log.Printf("   Total errors: %d", totalErrors)
	log.Printf("   Terms processed: %d", termsProcessed)
	log.Printf("   Pages processed: %d", pagesProcessed)
	if elapsed > 0 {
		rate := float64(totalIndexed) / elapsed.Minutes()
		log.Printf("   Average rate: %.2f repos/min", rate)
	}

	c.stats.mu.Lock()
	c.stats.lastReported = time.Now()
	c.stats.mu.Unlock()
}

func (c *Crawler) indexRepository(repo *Repository) error {
	data, err := json.Marshal(repo)
	if err != nil {
		metrics.IncrCounter("crawler_index_errors_total", 1)
		return err
	}

	req := esapi.IndexRequest{
		Index:      "github-coding-repos",
		DocumentID: strings.ReplaceAll(repo.FullName, "/", "-"),
		Body:       strings.NewReader(string(data)),
		Refresh:    "true",
	}

	res, err := req.Do(context.Background(), c.esClient)
	if err != nil {
		metrics.IncrCounter("crawler_index_errors_total", 1)
		return err
	}
	defer res.Body.Close()

	if res.IsError() {
		metrics.IncrCounter("crawler_index_errors_total", 1)
		return fmt.Errorf("failed to index repository: %s", res.Status())
	}

	// Record success metrics
	metrics.IncrCounter("crawler_repos_indexed_total", 1)
	metrics.SetGauge("crawler_last_repo_stars", float64(repo.Stars))

	return nil
}

func (c *Crawler) crawlCodingRepos() error {
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, 2) // Reduced from 3 to 2 for lower resource usage

	for _, term := range codingSearchTerms {
		for page := 1; page <= 5; page++ {
			select {
			case <-c.ctx.Done():
				log.Println("Crawling cancelled")
				return c.ctx.Err()
			default:
			}

			wg.Add(1)
			go func(searchTerm string, pageNum int) {
				defer wg.Done()
				semaphore <- struct{}{}
				defer func() { <-semaphore }()

				log.Printf("Crawling page %d for term: %s", pageNum, searchTerm)

				var repos []*Repository
				var err error
				maxRetries := 5

				for attempt := 0; attempt < maxRetries; attempt++ {
					if atomic.LoadInt32(&c.shutdown) == 1 {
						return
					}

					repos, err = c.searchGitHub(searchTerm, pageNum)
					if err == nil {
						break
					}

					if strings.Contains(err.Error(), "429") {
						backoffTime := c.exponentialBackoff(attempt)
						log.Printf("Rate limited on attempt %d for %s page %d. Backing off for %v", attempt+1, searchTerm, pageNum, backoffTime)

						select {
						case <-time.After(backoffTime):
							continue
						case <-c.ctx.Done():
							return
						}
					} else {
						log.Printf("Error searching GitHub for term %s, page %d: %v", searchTerm, pageNum, err)
						return
					}
				}

				if err != nil {
					log.Printf("Failed to search after %d attempts for term %s, page %d: %v", maxRetries, searchTerm, pageNum, err)
					return
				}

				for _, repo := range repos {
					// Scrape detailed information from the repo page
					if err := c.scrapeRepoDetails(repo); err != nil {
						log.Printf("Error scraping details for %s: %v", repo.FullName, err)
						c.stats.mu.Lock()
						c.stats.totalErrors++
						c.stats.mu.Unlock()
						continue
					}

					if err := c.indexRepository(repo); err != nil {
						log.Printf("Error indexing repository %s: %v", repo.FullName, err)
						c.stats.mu.Lock()
						c.stats.totalErrors++
						c.stats.mu.Unlock()
					} else {
						log.Printf("Indexed: %s (Stars: %d, Forks: %d)", repo.FullName, repo.Stars, repo.Forks)
						c.stats.mu.Lock()
						c.stats.totalIndexed++
						c.stats.mu.Unlock()
					}
				}

				c.stats.mu.Lock()
				c.stats.pagesProcessed++
				c.stats.mu.Unlock()

				time.Sleep(2 * time.Second)
			}(term, page)
		}

		c.stats.mu.Lock()
		c.stats.termsProcessed++
		c.stats.mu.Unlock()
	}

	wg.Wait()
	return nil
}

func (c *Crawler) createIndex() error {
	mapping := `{
		"mappings": {
			"properties": {
				"name": {"type": "text"},
				"full_name": {"type": "keyword"},
				"description": {"type": "text"},
				"url": {"type": "keyword"},
				"language": {"type": "keyword"},
				"stars": {"type": "integer"},
				"forks": {"type": "integer"},
				"last_updated": {"type": "date"},
				"topics": {"type": "keyword"},
				"crawled_at": {"type": "date"}
			}
		}
	}`

	createReq := esapi.IndicesCreateRequest{
		Index: "github-coding-repos",
		Body:  strings.NewReader(mapping),
	}

	res, err := createReq.Do(context.Background(), c.esClient)
	if err != nil {
		return err
	}
	defer res.Body.Close()

	if res.IsError() {
		if res.StatusCode == 400 || strings.Contains(res.Status(), "already_exists") {
			log.Printf("Index already exists, attempting to update mapping...")

			updateReq := esapi.IndicesPutMappingRequest{
				Index: []string{"github-coding-repos"},
				Body: strings.NewReader(`{
					"properties": {
						"name": {"type": "text"},
						"full_name": {"type": "keyword"},
						"description": {"type": "text"},
						"url": {"type": "keyword"},
						"language": {"type": "keyword"},
						"stars": {"type": "integer"},
						"forks": {"type": "integer"},
						"last_updated": {"type": "date"},
						"topics": {"type": "keyword"},
						"crawled_at": {"type": "date"}
					}
				}`),
			}

			updateRes, updateErr := updateReq.Do(context.Background(), c.esClient)
			if updateErr != nil {
				return fmt.Errorf("failed to update mapping: %w", updateErr)
			}
			defer updateRes.Body.Close()

			if updateRes.IsError() {
				log.Printf("Warning: failed to update mapping: %s", updateRes.Status())
			} else {
				log.Println("Successfully updated index mapping")
			}
		} else {
			return fmt.Errorf("failed to create index: %s", res.Status())
		}
	} else {
		log.Println("Successfully created new index")
	}

	return nil
}

func main() {
	log.Println("Starting GitHub Coding Repository Crawler")

	// Start metrics HTTP server
	go func() {
		http.Handle("/metrics", metrics.Handler())
		log.Printf("📊 Crawler metrics available at http://localhost:9092/metrics")
		if err := http.ListenAndServe(":9092", nil); err != nil {
			log.Printf("Metrics server error: %v", err)
		}
	}()

	crawler, err := NewCrawler()
	if err != nil {
		log.Fatal("Failed to create crawler:", err)
	}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		log.Println("\nReceived shutdown signal, stopping crawler gracefully...")
		atomic.StoreInt32(&crawler.shutdown, 1)
		crawler.cancel()
	}()

	if err := crawler.createIndex(); err != nil {
		log.Fatal("Failed to create Elasticsearch index:", err)
	}

	log.Println("Starting crawl process...")

	go func() {
		ticker := time.NewTicker(2 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				crawler.printStats()
			case <-crawler.ctx.Done():
				return
			}
		}
	}()

	if err := crawler.crawlCodingRepos(); err != nil {
		if err == context.Canceled {
			log.Println("Crawling was cancelled by user")
		} else {
			log.Printf("Crawling failed: %v", err)
		}
		crawler.printStats()
		return
	}

	log.Println("Crawling completed successfully")
	crawler.printStats()
}
