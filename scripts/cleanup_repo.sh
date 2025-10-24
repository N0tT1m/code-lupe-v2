#!/bin/bash
# Script to clean up repository structure and remove unnecessary files

set -e

echo "🧹 Cleaning up CodeLupe repository..."

# Create scripts directory if it doesn't exist
mkdir -p scripts/windows
mkdir -p scripts/deployment
mkdir -p scripts/monitoring

# Move PowerShell scripts to scripts/windows
echo "📁 Moving PowerShell scripts..."
mv *.ps1 scripts/windows/ 2>/dev/null || true

# Move batch files to scripts/windows
echo "📁 Moving batch files..."
mv *.bat scripts/windows/ 2>/dev/null || true

# Move shell scripts (except this one) to scripts/deployment
echo "📁 Moving shell scripts..."
for file in *.sh; do
    if [ "$file" != "cleanup_repo.sh" ] && [ -f "$file" ]; then
        mv "$file" scripts/deployment/
    fi
done

# Remove binary files (they should be in .gitignore)
echo "🗑️  Removing binary files..."
rm -f *.exe
rm -f crawler downloader fix_languages main test_ip_rotation
rm -f scraper.exe

# Remove database files (should not be committed)
echo "🗑️  Removing database files..."
rm -f *.db
rm -f *.sqlite
rm -f *.sqlite3

# Remove macOS metadata
echo "🗑️  Removing macOS metadata..."
find . -name ".DS_Store" -type f -delete

# Clean Python cache
echo "🗑️  Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# Update .gitignore to ensure these files stay ignored
echo "📝 Updating .gitignore..."
cat >> .gitignore << 'EOL'

# Binaries (should never be committed)
*.exe
!*.exe.config
*.dll
*.so
*.dylib
crawler
downloader
main
fix_languages
test_ip_rotation
scraper.exe

# Database files
*.db
*.sqlite
*.sqlite3

# macOS
.DS_Store
.AppleDouble
.LSOverride

EOL

echo "✅ Repository cleanup complete!"
echo ""
echo "📊 Summary:"
echo "  - Moved PowerShell/Batch scripts to scripts/windows/"
echo "  - Moved shell scripts to scripts/deployment/"
echo "  - Removed binary files"
echo "  - Removed database files"
echo "  - Cleaned macOS metadata"
echo "  - Updated .gitignore"
echo ""
echo "⚠️  Please review the changes and commit them."
