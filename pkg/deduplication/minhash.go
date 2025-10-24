package deduplication

import (
	"fmt"
	"hash/fnv"
	"math"
	"regexp"
	"strings"
)

// MinHash implements the MinHash algorithm for document similarity
type MinHash struct {
	numHashes      int
	shingleSize    int
	permutations   []HashFunc
	codeNormalizer *regexp.Regexp
}

// HashFunc represents a hash function with parameters for permutation
type HashFunc struct {
	a, b, c uint32
}

// MinHashSignature represents a MinHash signature for a document
type MinHashSignature struct {
	Hashes     []uint32
	NumHashes  int
	Normalized string // Normalized content for exact match checking
}

// NewMinHash creates a new MinHash instance
func NewMinHash(numHashes, shingleSize int) *MinHash {
	permutations := make([]HashFunc, numHashes)

	// Generate random hash functions (using deterministic values for consistency)
	for i := 0; i < numHashes; i++ {
		permutations[i] = HashFunc{
			a: uint32(i*2 + 1),
			b: uint32(i*3 + 1),
			c: uint32(math.MaxUint32),
		}
	}

	// Regex to normalize code by removing comments and extra whitespace
	codeNormalizer := regexp.MustCompile(`\s+`)

	return &MinHash{
		numHashes:      numHashes,
		shingleSize:    shingleSize,
		permutations:   permutations,
		codeNormalizer: codeNormalizer,
	}
}

// normalizeCode removes comments and normalizes whitespace
func (mh *MinHash) normalizeCode(code string) string {
	// Remove single-line comments (// and #)
	lines := strings.Split(code, "\n")
	var normalized []string
	for _, line := range lines {
		// Remove // comments
		if idx := strings.Index(line, "//"); idx != -1 {
			line = line[:idx]
		}
		// Remove # comments (Python)
		if idx := strings.Index(line, "#"); idx != -1 {
			line = line[:idx]
		}
		line = strings.TrimSpace(line)
		if line != "" {
			normalized = append(normalized, line)
		}
	}

	// Join and normalize whitespace
	result := strings.Join(normalized, " ")
	result = mh.codeNormalizer.ReplaceAllString(result, " ")
	return strings.TrimSpace(strings.ToLower(result))
}

// generateShingles creates character-level shingles from text
func (mh *MinHash) generateShingles(text string) []string {
	if len(text) < mh.shingleSize {
		return []string{text}
	}

	shingles := make([]string, 0, len(text)-mh.shingleSize+1)
	for i := 0; i <= len(text)-mh.shingleSize; i++ {
		shingles = append(shingles, text[i:i+mh.shingleSize])
	}
	return shingles
}

// hash computes FNV-1a hash of a string
func hash(s string) uint32 {
	h := fnv.New32a()
	h.Write([]byte(s))
	return h.Sum32()
}

// ComputeSignature generates a MinHash signature for the given code
func (mh *MinHash) ComputeSignature(code string) *MinHashSignature {
	normalized := mh.normalizeCode(code)
	shingles := mh.generateShingles(normalized)

	// Initialize signature with max values
	signature := make([]uint32, mh.numHashes)
	for i := range signature {
		signature[i] = math.MaxUint32
	}

	// Compute MinHash signature
	for _, shingle := range shingles {
		shingleHash := hash(shingle)

		for i, perm := range mh.permutations {
			// Apply permutation: (a * x + b) mod c
			permutedHash := (perm.a*shingleHash + perm.b) % perm.c
			if permutedHash < signature[i] {
				signature[i] = permutedHash
			}
		}
	}

	return &MinHashSignature{
		Hashes:     signature,
		NumHashes:  mh.numHashes,
		Normalized: normalized,
	}
}

// JaccardSimilarity estimates the Jaccard similarity between two signatures
func (mh *MinHash) JaccardSimilarity(sig1, sig2 *MinHashSignature) float64 {
	if sig1.NumHashes != sig2.NumHashes {
		return 0.0
	}

	matches := 0
	for i := 0; i < sig1.NumHashes; i++ {
		if sig1.Hashes[i] == sig2.Hashes[i] {
			matches++
		}
	}

	return float64(matches) / float64(sig1.NumHashes)
}

// IsDuplicate checks if two code snippets are duplicates based on similarity threshold
func (mh *MinHash) IsDuplicate(code1, code2 string, threshold float64) bool {
	sig1 := mh.ComputeSignature(code1)
	sig2 := mh.ComputeSignature(code2)

	// Check for exact match after normalization
	if sig1.Normalized == sig2.Normalized {
		return true
	}

	// Check Jaccard similarity
	similarity := mh.JaccardSimilarity(sig1, sig2)
	return similarity >= threshold
}

// DeduplicationIndex maintains an index of code signatures for efficient deduplication
type DeduplicationIndex struct {
	minHash    *MinHash
	signatures map[string]*MinHashSignature // key -> signature
	threshold  float64
}

// NewDeduplicationIndex creates a new deduplication index
func NewDeduplicationIndex(numHashes, shingleSize int, threshold float64) *DeduplicationIndex {
	return &DeduplicationIndex{
		minHash:    NewMinHash(numHashes, shingleSize),
		signatures: make(map[string]*MinHashSignature),
		threshold:  threshold,
	}
}

// Add adds a code snippet to the index with a unique key
func (di *DeduplicationIndex) Add(key, code string) error {
	signature := di.minHash.ComputeSignature(code)
	di.signatures[key] = signature
	return nil
}

// FindDuplicates finds all keys with code similar to the given code
func (di *DeduplicationIndex) FindDuplicates(code string) []string {
	targetSig := di.minHash.ComputeSignature(code)

	var duplicates []string
	for key, sig := range di.signatures {
		// Check exact match first
		if sig.Normalized == targetSig.Normalized {
			duplicates = append(duplicates, key)
			continue
		}

		// Check similarity
		similarity := di.minHash.JaccardSimilarity(targetSig, sig)
		if similarity >= di.threshold {
			duplicates = append(duplicates, key)
		}
	}

	return duplicates
}

// IsDuplicate checks if the given code is a duplicate of any indexed code
func (di *DeduplicationIndex) IsDuplicate(code string) bool {
	return len(di.FindDuplicates(code)) > 0
}

// Remove removes a key from the index
func (di *DeduplicationIndex) Remove(key string) {
	delete(di.signatures, key)
}

// Size returns the number of signatures in the index
func (di *DeduplicationIndex) Size() int {
	return len(di.signatures)
}

// Clear removes all signatures from the index
func (di *DeduplicationIndex) Clear() {
	di.signatures = make(map[string]*MinHashSignature)
}

// GetSimilarity returns the similarity between the code and a specific key
func (di *DeduplicationIndex) GetSimilarity(key, code string) (float64, error) {
	sig, exists := di.signatures[key]
	if !exists {
		return 0, fmt.Errorf("key not found: %s", key)
	}

	targetSig := di.minHash.ComputeSignature(code)
	return di.minHash.JaccardSimilarity(targetSig, sig), nil
}
