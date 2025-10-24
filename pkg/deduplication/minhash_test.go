package deduplication

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMinHash_ComputeSignature(t *testing.T) {
	mh := NewMinHash(128, 3)

	code := `
	func hello() {
		fmt.Println("Hello, World!")
	}
	`

	sig := mh.ComputeSignature(code)
	assert.Equal(t, 128, len(sig.Hashes))
	assert.NotEmpty(t, sig.Normalized)
}

func TestMinHash_IsDuplicate_ExactMatch(t *testing.T) {
	mh := NewMinHash(128, 3)

	code1 := `
	func hello() {
		fmt.Println("Hello, World!")
	}
	`

	code2 := `
	func hello() {
		// This is a comment
		fmt.Println("Hello, World!")
	}
	`

	// Should be considered duplicate (comments are removed)
	isDup := mh.IsDuplicate(code1, code2, 0.8)
	assert.True(t, isDup)
}

func TestMinHash_IsDuplicate_SimilarCode(t *testing.T) {
	mh := NewMinHash(128, 3)

	code1 := `
	func hello() {
		fmt.Println("Hello, World!")
		fmt.Println("Goodbye!")
	}
	`

	code2 := `
	func hello() {
		fmt.Println("Hello, World!")
		fmt.Println("Farewell!")
	}
	`

	// Should be similar but not exact duplicates
	similarity := mh.JaccardSimilarity(
		mh.ComputeSignature(code1),
		mh.ComputeSignature(code2),
	)
	assert.Greater(t, similarity, 0.7)
	assert.Less(t, similarity, 1.0)
}

func TestMinHash_IsDuplicate_DifferentCode(t *testing.T) {
	mh := NewMinHash(128, 3)

	code1 := `
	func add(a, b int) int {
		return a + b
	}
	`

	code2 := `
	func multiply(x, y float64) float64 {
		return x * y
	}
	`

	// Should not be duplicates
	isDup := mh.IsDuplicate(code1, code2, 0.8)
	assert.False(t, isDup)
}

func TestMinHash_JaccardSimilarity(t *testing.T) {
	mh := NewMinHash(128, 3)

	code1 := "func hello() { fmt.Println(\"test\") }"
	code2 := "func hello() { fmt.Println(\"test\") }"
	code3 := "func goodbye() { fmt.Println(\"different\") }"

	sig1 := mh.ComputeSignature(code1)
	sig2 := mh.ComputeSignature(code2)
	sig3 := mh.ComputeSignature(code3)

	// Identical code should have similarity close to 1.0
	sim12 := mh.JaccardSimilarity(sig1, sig2)
	assert.Greater(t, sim12, 0.9)

	// Different code should have lower similarity
	sim13 := mh.JaccardSimilarity(sig1, sig3)
	assert.Less(t, sim13, 0.5)
}

func TestDeduplicationIndex_AddAndFind(t *testing.T) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	code1 := `
	func add(a, b int) int {
		return a + b
	}
	`

	code2 := `
	func add(a, b int) int {
		// Adding two numbers
		return a + b
	}
	`

	code3 := `
	func multiply(x, y int) int {
		return x * y
	}
	`

	// Add codes to index
	di.Add("code1", code1)
	di.Add("code3", code3)

	// code2 should be found as duplicate of code1
	duplicates := di.FindDuplicates(code2)
	assert.Contains(t, duplicates, "code1")
	assert.NotContains(t, duplicates, "code3")
}

func TestDeduplicationIndex_IsDuplicate(t *testing.T) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	code1 := "func test() { fmt.Println(\"test\") }"
	code2 := "func test() { fmt.Println(\"test\") }" // Same as code1
	code3 := "func other() { fmt.Println(\"different\") }"

	di.Add("code1", code1)

	// code2 should be detected as duplicate
	assert.True(t, di.IsDuplicate(code2))

	// code3 should not be detected as duplicate
	assert.False(t, di.IsDuplicate(code3))
}

func TestDeduplicationIndex_Remove(t *testing.T) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	code := "func test() { fmt.Println(\"test\") }"

	di.Add("code1", code)
	assert.Equal(t, 1, di.Size())

	di.Remove("code1")
	assert.Equal(t, 0, di.Size())
}

func TestDeduplicationIndex_Clear(t *testing.T) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	di.Add("code1", "func a() {}")
	di.Add("code2", "func b() {}")
	di.Add("code3", "func c() {}")
	assert.Equal(t, 3, di.Size())

	di.Clear()
	assert.Equal(t, 0, di.Size())
}

func TestDeduplicationIndex_GetSimilarity(t *testing.T) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	code1 := "func test() { fmt.Println(\"test\") }"
	code2 := "func test() { fmt.Println(\"test\") }"
	code3 := "func other() { return 42 }"

	di.Add("code1", code1)

	// Similarity with identical code
	sim, err := di.GetSimilarity("code1", code2)
	assert.NoError(t, err)
	assert.Greater(t, sim, 0.9)

	// Similarity with different code
	sim, err = di.GetSimilarity("code1", code3)
	assert.NoError(t, err)
	assert.Less(t, sim, 0.5)

	// Non-existent key
	_, err = di.GetSimilarity("nonexistent", code1)
	assert.Error(t, err)
}

func TestMinHash_NormalizeCode(t *testing.T) {
	mh := NewMinHash(128, 3)

	code := `
	func hello() {
		// This is a comment
		fmt.Println("Hello") // inline comment
		# Python-style comment
		return
	}
	`

	normalized := mh.normalizeCode(code)

	// Should not contain comment markers
	assert.NotContains(t, normalized, "//")
	assert.NotContains(t, normalized, "#")
	assert.NotContains(t, normalized, "This is a comment")

	// Should contain actual code
	assert.Contains(t, normalized, "func hello")
	assert.Contains(t, normalized, "fmt.println")
	assert.Contains(t, normalized, "return")
}

func BenchmarkMinHash_ComputeSignature(b *testing.B) {
	mh := NewMinHash(128, 3)
	code := `
	func complexFunction(a, b, c int) int {
		result := 0
		for i := 0; i < a; i++ {
			for j := 0; j < b; j++ {
				result += c * (i + j)
			}
		}
		return result
	}
	`

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		mh.ComputeSignature(code)
	}
}

func BenchmarkDeduplicationIndex_FindDuplicates(b *testing.B) {
	di := NewDeduplicationIndex(128, 3, 0.8)

	// Add 1000 code snippets
	for i := 0; i < 1000; i++ {
		code := "func test" + string(rune(i)) + "() { return }"
		di.Add("code"+string(rune(i)), code)
	}

	testCode := "func testX() { return }"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		di.FindDuplicates(testCode)
	}
}
