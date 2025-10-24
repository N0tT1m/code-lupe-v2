# Check NAS and Rebuild Script for Windows
# This script checks your NAS setup and provides options
# Run with: .\check_nas_and_rebuild.ps1

Write-Host "🔍 CODELUPE NAS CHECKER AND REBUILDER" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Yellow

# Function to check NAS connectivity
function Test-NASConnection {
    Write-Host "🔌 Checking NAS connectivity..." -ForegroundColor Cyan
    
    # Check if P: drive exists
    if (-not (Test-Path "P:\")) {
        Write-Host "❌ P: drive not found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "💡 TO FIX THIS:" -ForegroundColor Yellow
        Write-Host "1. Open File Explorer" -ForegroundColor White
        Write-Host "2. Right-click 'This PC' → 'Map network drive'" -ForegroundColor White
        Write-Host "3. Choose 'P:' as drive letter" -ForegroundColor White
        Write-Host "4. Enter your NAS path (e.g., \\192.168.1.66\plex3)" -ForegroundColor White
        Write-Host "5. Check 'Reconnect at sign-in'" -ForegroundColor White
        Write-Host ""
        return $false
    }
    
    Write-Host "✅ P: drive found!" -ForegroundColor Green
    
    # Check if codelupe directory exists
    if (-not (Test-Path "P:\codelupe")) {
        Write-Host "⚠️  P:\codelupe directory not found, creating..." -ForegroundColor Yellow
        try {
            New-Item -ItemType Directory -Path "P:\codelupe" -Force | Out-Null
            Write-Host "✅ Created P:\codelupe" -ForegroundColor Green
        } catch {
            Write-Host "❌ Failed to create P:\codelupe - check permissions" -ForegroundColor Red
            return $false
        }
    }
    
    # Check if repos directory exists
    if (-not (Test-Path "P:\codelupe\repos")) {
        Write-Host "⚠️  P:\codelupe\repos directory not found, creating..." -ForegroundColor Yellow
        try {
            New-Item -ItemType Directory -Path "P:\codelupe\repos" -Force | Out-Null
            Write-Host "✅ Created P:\codelupe\repos" -ForegroundColor Green
        } catch {
            Write-Host "❌ Failed to create P:\codelupe\repos - check permissions" -ForegroundColor Red
            return $false
        }
    }
    
    # Test write permissions
    $testFile = "P:\codelupe\repos\test_write.tmp"
    try {
        "test" | Out-File -FilePath $testFile -Force
        Remove-Item $testFile -Force
        Write-Host "✅ Write permissions OK" -ForegroundColor Green
    } catch {
        Write-Host "❌ No write permissions to P:\codelupe\repos" -ForegroundColor Red
        return $false
    }
    
    # Show directory info
    $dirInfo = Get-ChildItem "P:\codelupe\repos" -ErrorAction SilentlyContinue
    if ($dirInfo) {
        Write-Host "📁 Found $($dirInfo.Count) items in P:\codelupe\repos" -ForegroundColor Cyan
    } else {
        Write-Host "📁 P:\codelupe\repos is empty (ready for downloads)" -ForegroundColor Cyan
    }
    
    return $true
}

# Check NAS first
$nasOK = Test-NASConnection

if (-not $nasOK) {
    Write-Host ""
    Write-Host "❌ NAS setup issues detected. Please fix them before rebuilding." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ NAS setup looks good!" -ForegroundColor Green
Write-Host ""

# Ask what to do
Write-Host "🤔 What would you like to do?" -ForegroundColor Yellow
Write-Host "1. Quick rebuild (recommended - keeps data)" -ForegroundColor White
Write-Host "2. Complete rebuild (fresh start)" -ForegroundColor White
Write-Host "3. Just check current status" -ForegroundColor White
Write-Host "4. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter your choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "🚀 Starting quick rebuild..." -ForegroundColor Green
        & .\quick_rebuild.ps1
    }
    "2" {
        Write-Host ""
        Write-Host "🚀 Starting complete rebuild..." -ForegroundColor Green
        & .\rebuild_and_restart.ps1
    }
    "3" {
        Write-Host ""
        Write-Host "📊 Current Docker status:" -ForegroundColor Yellow
        docker-compose ps
        Write-Host ""
        Write-Host "📁 NAS contents:" -ForegroundColor Yellow
        Get-ChildItem "P:\codelupe\repos" -Name | Select-Object -First 10
    }
    "4" {
        Write-Host "👋 Goodbye!" -ForegroundColor Green
        exit 0
    }
    default {
        Write-Host "❌ Invalid choice. Please run the script again." -ForegroundColor Red
        exit 1
    }
}