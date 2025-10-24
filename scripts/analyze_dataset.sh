#!/bin/bash

echo "🔍 CodeLupe Dataset Analyzer"
echo "============================="

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "❌ Go is not installed. Please install Go first."
    exit 1
fi

# Build the analyzer
echo "🏗️  Building dataset analyzer..."
go build -o dataset_analyzer dataset_analyzer.go

if [ $? -ne 0 ]; then
    echo "❌ Build failed. Check for errors above."
    exit 1
fi

echo "✅ Build successful!"
echo ""

# Run the analyzer
echo "🚀 Running dataset analysis..."
echo ""
./dataset_analyzer

echo ""
echo "📊 Analysis complete!"
echo ""
echo "💡 Pro Tips:"
echo "• Use this regularly to monitor dataset growth"
echo "• Check quality distribution to ensure good training data"
echo "• Monitor language balance for your specific use case"
echo "• Look for repositories that might need exclusion"
echo ""
echo "🔄 To run again: ./dataset_analyzer"