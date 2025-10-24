#!/bin/bash

echo "🚀 MASSIVE Repository Collection & Training System"
echo "=================================================="
echo "Target: 10,000+ repositories for training"
echo ""

# Check for GitHub token
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✅ GitHub token found - UNLIMITED API access"
    echo "   Will use 20 parallel threads for maximum speed"
    TARGET=10000
    THREADS=20
else
    echo "⚠️  No GitHub token - rate limited mode"
    echo "   Will use 1 thread, ~1000 repos max"
    echo "   Set GITHUB_TOKEN for unlimited collection"
    TARGET=1000
    THREADS=1
fi

echo ""
echo "Collection will include:"
echo "• 50+ programming languages"
echo "• 100+ technology topics" 
echo "• NSFW & adult content libraries"
echo "• Trending, popular, and recent repositories"
echo "• Network discovery from seed repositories"
echo "• Automatic deduplication"
echo ""

read -p "Start massive collection? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔥 Starting massive collection..."
    
    # Install requirements if needed
    if ! python3 -c "import torch, transformers" 2>/dev/null; then
        echo "Installing requirements..."
        pip3 install -r requirements.txt
    fi
    
    # Start massive collection
    if [ -n "$GITHUB_TOKEN" ]; then
        python3 massive_repo_collector.py --token "$GITHUB_TOKEN" --target $TARGET --threads $THREADS
    else
        python3 massive_repo_collector.py --target $TARGET --threads $THREADS
    fi
    
    # After collection, start training
    echo ""
    read -p "Collection complete! Start training on collected repos? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧠 Starting training on collected repositories..."
        python3 train_on_massive_collection.py
    fi
else
    echo "Cancelled."
fi
