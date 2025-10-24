Write-Host "🚀 MASSIVE Repository Collection & Training System" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Target: 10,000+ repositories for training" -ForegroundColor Yellow
Write-Host ""

# Check for GitHub token
if ($env:GITHUB_TOKEN) {
    Write-Host "✅ GitHub token found - UNLIMITED API access" -ForegroundColor Green
    Write-Host "   Will use 20 parallel threads for maximum speed" -ForegroundColor Green
    $TARGET = 10000
    $THREADS = 20
} else {
    Write-Host "⚠️  No GitHub token - rate limited mode" -ForegroundColor Yellow
    Write-Host "   Will use 1 thread, ~1000 repos max" -ForegroundColor Yellow
    Write-Host "   Set GITHUB_TOKEN for unlimited collection" -ForegroundColor Yellow
    $TARGET = 1000
    $THREADS = 1
}

Write-Host ""
Write-Host "Collection will include:" -ForegroundColor Cyan
Write-Host "• 50+ programming languages"
Write-Host "• 100+ technology topics"
Write-Host "• NSFW & adult content libraries"
Write-Host "• Trending, popular, and recent repositories"
Write-Host "• Network discovery from seed repositories"
Write-Host "• Automatic deduplication"
Write-Host ""

$response = Read-Host "Start massive collection? (y/N)"
if ($response -match '^[Yy]$') {
    Write-Host "🔥 Starting massive collection..." -ForegroundColor Green

    # Check if requirements are installed
    $pythonCheck = $null
    try {
        $pythonCheck = python3 -c "import torch, transformers" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Modules not found"
        }
    } catch {
        Write-Host "Installing requirements..." -ForegroundColor Yellow
        pip3 install -r requirements.txt
    }

    # Start massive collection
    if ($env:GITHUB_TOKEN) {
        python3 massive_repo_collector.py --token "$env:GITHUB_TOKEN" --target $TARGET --threads $THREADS
    } else {
        python3 massive_repo_collector.py --target $TARGET --threads $THREADS
    }

    # After collection, start training
    Write-Host ""
    $trainResponse = Read-Host "Collection complete! Start training on collected repos? (y/N)"
    if ($trainResponse -match '^[Yy]$') {
        Write-Host "🧠 Starting training on collected repositories..." -ForegroundColor Green
        python3 train_on_massive_collection.py
    }
} else {
    Write-Host "Cancelled." -ForegroundColor Red
}
