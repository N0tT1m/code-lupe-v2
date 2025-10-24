#!/usr/bin/env python3
"""
Test script for Mamba-Codestral + Mathstral Ensemble
Tests routing, inference, and hybrid mode
"""

import sys
import time
from hybrid_mathcode_ensemble import HybridMathCodeEnsemble, EnsembleConfig, TaskType

def print_result(query: str, result: dict):
    """Pretty print result"""
    print("\n" + "="*80)
    print(f"📝 QUERY: {query[:100]}...")
    print(f"🎯 Task Type: {result['task_type'].upper()}")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"🤖 Model: {result['model_used']}")
    print(f"⏱️  Time: {result['generation_time']:.2f}s")
    print(f"✅ Success: {result['success']}")
    print("-"*80)
    print(f"💬 RESPONSE:\n{result['response'][:500]}...")
    print("="*80)

def main():
    print("🚀 Testing Mamba-Codestral + Mathstral Ensemble")
    print("="*80)

    # Create ensemble
    print("\n📥 Loading models (this may take a few minutes)...")
    config = EnsembleConfig()
    ensemble = HybridMathCodeEnsemble(config)

    try:
        ensemble.load_models()
        print("✅ Both models loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load models: {e}")
        print("\n💡 Make sure you have:")
        print("   1. HF_TOKEN set for gated models")
        print("   2. Sufficient GPU memory (~18GB)")
        print("   3. mamba-ssm and causal-conv1d installed")
        sys.exit(1)

    # Test queries
    test_queries = [
        {
            "name": "Math Query",
            "prompt": "[INST] Solve the quadratic equation: 3x^2 - 7x + 2 = 0 [/INST]",
            "expected": TaskType.MATH
        },
        {
            "name": "Code Query",
            "prompt": "[INST] Implement a Python function to reverse a linked list [/INST]",
            "expected": TaskType.CODE
        },
        {
            "name": "Hybrid Query",
            "prompt": "[INST] Implement a numerical integration algorithm using Simpson's rule and explain the mathematical derivation [/INST]",
            "expected": TaskType.HYBRID
        },
        {
            "name": "Algorithm Complexity",
            "prompt": "[INST] Explain Big O notation and implement a function to calculate the time complexity of bubble sort [/INST]",
            "expected": TaskType.HYBRID
        },
        {
            "name": "Data Structure",
            "prompt": "[INST] Create a binary search tree class in Python with insert, search, and delete methods [/INST]",
            "expected": TaskType.CODE
        },
        {
            "name": "Mathematical Proof",
            "prompt": "[INST] Prove that the sum of first n natural numbers is n(n+1)/2 [/INST]",
            "expected": TaskType.MATH
        }
    ]

    print(f"\n🧪 Running {len(test_queries)} test queries...\n")

    results = []
    for i, test in enumerate(test_queries, 1):
        print(f"\n📋 Test {i}/{len(test_queries)}: {test['name']}")
        print(f"Expected task type: {test['expected'].value}")

        start = time.time()
        result = ensemble.generate(test['prompt'])

        # Save to database
        ensemble.save_to_database(test['prompt'], result)

        # Print result
        print_result(test['prompt'], result)

        # Verify routing
        if result['task_type'] == test['expected'].value:
            print("✅ Routing correct!")
        else:
            print(f"⚠️  Routing mismatch (expected: {test['expected'].value})")

        results.append(result)

        # Small delay between queries
        time.sleep(1)

    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    stats = ensemble.get_stats()
    print(f"\nTotal queries: {stats['total_queries']}")
    print(f"Math queries: {stats['math_queries']}")
    print(f"Code queries: {stats['code_queries']}")
    print(f"Hybrid queries: {stats['hybrid_queries']}")
    print(f"General queries: {stats['general_queries']}")

    success_count = sum(1 for r in results if r['success'])
    print(f"\nSuccess rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

    avg_time = sum(r['generation_time'] for r in results) / len(results)
    print(f"Average generation time: {avg_time:.2f}s")

    # Model usage breakdown
    model_usage = {}
    for r in results:
        model = r['model_used']
        model_usage[model] = model_usage.get(model, 0) + 1

    print("\nModel usage:")
    for model, count in model_usage.items():
        print(f"  {model}: {count} queries")

    print("\n" + "="*80)
    print("✅ Testing complete!")
    print("\n💡 Check database for saved queries:")
    print("   SELECT * FROM ensemble_queries ORDER BY created_at DESC;")
    print("="*80)

if __name__ == "__main__":
    main()
