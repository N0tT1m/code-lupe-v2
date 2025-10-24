package examples

import (
	"codelupe/pkg/circuitbreaker"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"
)

// Example 1: Using circuit breaker with HTTP client
func ExampleHTTPClient() {
	// Create circuit breaker
	cb := circuitbreaker.New(circuitbreaker.Config{
		MaxFailures: 5,
		Timeout:     30 * time.Second,
		MaxRequests: 2,
		OnStateChange: func(from, to circuitbreaker.State) {
			log.Printf("Circuit breaker state changed: %s -> %s", from, to)
		},
	})

	client := &http.Client{Timeout: 10 * time.Second}

	// Execute HTTP request with circuit breaker protection
	err := cb.Execute(func() error {
		resp, err := client.Get("https://api.github.com/repos/rust-lang/rust")
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 500 {
			return fmt.Errorf("server error: %d", resp.StatusCode)
		}

		return nil
	})

	if err != nil {
		if err == circuitbreaker.ErrCircuitOpen {
			log.Println("Circuit is open, request not executed")
		} else {
			log.Printf("Request failed: %v", err)
		}
	}
}

// Example 2: Using circuit breaker with database operations
type Database struct {
	circuitBreaker *circuitbreaker.CircuitBreaker
}

func NewDatabase() *Database {
	return &Database{
		circuitBreaker: circuitbreaker.New(circuitbreaker.Config{
			MaxFailures: 3,
			Timeout:     60 * time.Second,
			OnStateChange: func(from, to circuitbreaker.State) {
				log.Printf("Database circuit breaker: %s -> %s", from, to)
			},
		}),
	}
}

func (db *Database) Query(query string) error {
	return db.circuitBreaker.Execute(func() error {
		// Simulate database query
		// In real code, this would be actual database operation
		if query == "FAIL" {
			return errors.New("database error")
		}
		return nil
	})
}

// Example 3: Multiple circuit breakers for different services
type ServiceClient struct {
	githubCB   *circuitbreaker.CircuitBreaker
	elasticCB  *circuitbreaker.CircuitBreaker
	postgresCB *circuitbreaker.CircuitBreaker
}

func NewServiceClient() *ServiceClient {
	onStateChange := func(service string) func(circuitbreaker.State, circuitbreaker.State) {
		return func(from, to circuitbreaker.State) {
			log.Printf("[%s] Circuit breaker: %s -> %s", service, from, to)
		}
	}

	return &ServiceClient{
		githubCB: circuitbreaker.New(circuitbreaker.Config{
			MaxFailures:   5,
			Timeout:       30 * time.Second,
			OnStateChange: onStateChange("GitHub"),
		}),
		elasticCB: circuitbreaker.New(circuitbreaker.Config{
			MaxFailures:   3,
			Timeout:       60 * time.Second,
			OnStateChange: onStateChange("Elasticsearch"),
		}),
		postgresCB: circuitbreaker.New(circuitbreaker.Config{
			MaxFailures:   3,
			Timeout:       60 * time.Second,
			OnStateChange: onStateChange("PostgreSQL"),
		}),
	}
}

func (sc *ServiceClient) FetchFromGitHub(url string) error {
	return sc.githubCB.Execute(func() error {
		// GitHub API call
		return nil
	})
}

func (sc *ServiceClient) IndexToElasticsearch(doc interface{}) error {
	return sc.elasticCB.Execute(func() error {
		// Elasticsearch indexing
		return nil
	})
}

func (sc *ServiceClient) SaveToPostgres(data interface{}) error {
	return sc.postgresCB.Execute(func() error {
		// PostgreSQL insert
		return nil
	})
}

// Example 4: Monitoring circuit breaker stats
func MonitorCircuitBreaker(cb *circuitbreaker.CircuitBreaker) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		stats := cb.Stats()
		log.Printf("Circuit Breaker Stats - State: %s, Failures: %d, Last Fail: %v",
			stats.State,
			stats.Failures,
			stats.LastFailTime,
		)

		// Alert if circuit is open
		if stats.State == circuitbreaker.StateOpen {
			log.Printf("ALERT: Circuit breaker is OPEN! Last failed: %v", stats.LastFailTime)
			// Send alert to monitoring system
		}
	}
}
