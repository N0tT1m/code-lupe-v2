#!/bin/bash

set -e

# Script to generate changelog using git-cliff

echo "📝 Generating CHANGELOG.md..."

# Check if git-cliff is installed
if ! command -v git-cliff &> /dev/null; then
    echo "⚠️  git-cliff is not installed. Installing..."

    # Install based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install git-cliff
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        cargo install git-cliff
    else
        echo "❌ Unsupported OS. Please install git-cliff manually:"
        echo "   https://git-cliff.org/docs/installation"
        exit 1
    fi
fi

# Generate full changelog
if [ "$1" == "--unreleased" ]; then
    echo "Generating unreleased changes only..."
    git-cliff --unreleased --output CHANGELOG.md
elif [ "$1" == "--tag" ]; then
    echo "Generating changelog for tag: $2"
    git-cliff --tag "$2" --output CHANGELOG.md
else
    echo "Generating full changelog..."
    git-cliff --output CHANGELOG.md
fi

echo "✅ Changelog generated successfully!"
echo "📄 See CHANGELOG.md"
