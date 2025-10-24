# Monitor the Fixes Script for Windows
# Run with: .\monitor_fixes.ps1

Write-Host "🔍 MONITORING PIPELINE FIXES" -ForegroundColor Yellow
Write-Host "============================" -ForegroundColor Yellow

function Show-Menu {
    Write-Host ""
    Write-Host "Choose what to monitor:" -ForegroundColor Cyan
    Write-Host "1. All services" -ForegroundColor White
    Write-Host "2. Trainer (Flash Attention fix)" -ForegroundColor White
    Write-Host "3. Processor (PostgreSQL transaction fix)" -ForegroundColor White
    Write-Host "4. Downloader (NAS location fix)" -ForegroundColor White
    Write-Host "5. Check service status" -ForegroundColor White
    Write-Host "6. Check NAS location" -ForegroundColor White
    Write-Host "7. Exit" -ForegroundColor White
    Write-Host ""
}

function Monitor-Trainer {
    Write-Host "🤖 Monitoring Trainer for Flash Attention issues..." -ForegroundColor Yellow
    Write-Host "Looking for: CUDA symbols, flash_attn errors, import issues" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to return to menu" -ForegroundColor Gray
    Write-Host ""
    docker-compose logs -f trainer
}

function Monitor-Processor {
    Write-Host "⚙️  Monitoring Processor for PostgreSQL transaction issues..." -ForegroundColor Yellow
    Write-Host "Looking for: transaction aborted, failed to insert, batch errors" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to return to menu" -ForegroundColor Gray
    Write-Host ""
    docker-compose logs -f processor
}

function Monitor-Downloader {
    Write-Host "📥 Monitoring Downloader for NAS location..." -ForegroundColor Yellow
    Write-Host "Looking for: download paths, cloning activity, saved locations" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to return to menu" -ForegroundColor Gray
    Write-Host ""
    docker-compose logs -f downloader
}

function Check-ServiceStatus {
    Write-Host "📊 Service Status:" -ForegroundColor Yellow
    docker-compose ps
    
    Write-Host ""
    Write-Host "🔍 Quick Health Check:" -ForegroundColor Yellow
    
    # Check trainer
    $trainerLogs = docker-compose logs trainer --tail=20 2>$null
    if ($trainerLogs -match "undefined symbol|ImportError|flash_attn.*error") {
        Write-Host "❌ Trainer: Flash Attention issues detected" -ForegroundColor Red
    } elseif ($trainerLogs -match "Continuous Trainer initialized|✅") {
        Write-Host "✅ Trainer: Running OK" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Trainer: Status unclear" -ForegroundColor Yellow
    }
    
    # Check processor
    $processorLogs = docker-compose logs processor --tail=20 2>$null
    if ($processorLogs -match "transaction is aborted|Failed to insert.*pq") {
        Write-Host "❌ Processor: PostgreSQL transaction issues detected" -ForegroundColor Red
    } elseif ($processorLogs -match "Batch insert completed|Processing pipeline") {
        Write-Host "✅ Processor: Running OK" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Processor: Status unclear" -ForegroundColor Yellow
    }
    
    # Check downloader
    $downloaderLogs = docker-compose logs downloader --tail=20 2>$null
    if ($downloaderLogs -match "Downloaded.*repos|Cloning.*repos") {
        Write-Host "✅ Downloader: Saving to correct location" -ForegroundColor Green
    } elseif ($downloaderLogs -match "Download process completed") {
        Write-Host "✅ Downloader: Completed successfully" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Downloader: Status unclear" -ForegroundColor Yellow
    }
}

function Check-NASLocation {
    Write-Host "📁 Checking NAS location..." -ForegroundColor Yellow
    
    if (Test-Path "P:\codelupe\repos") {
        $items = Get-ChildItem "P:\codelupe\repos" -ErrorAction SilentlyContinue
        Write-Host "✅ P:\codelupe\repos exists" -ForegroundColor Green
        Write-Host "📊 Contains $($items.Count) items" -ForegroundColor Cyan
        
        # Show recent activity
        $recent = $items | Sort-Object LastWriteTime -Descending | Select-Object -First 5
        if ($recent) {
            Write-Host ""
            Write-Host "🕒 Most recent items:" -ForegroundColor Yellow
            foreach ($item in $recent) {
                Write-Host "  $($item.Name) - $($item.LastWriteTime)" -ForegroundColor White
            }
        }
    } else {
        Write-Host "❌ P:\codelupe\repos not found!" -ForegroundColor Red
    }
}

# Main loop
while ($true) {
    Show-Menu
    $choice = Read-Host "Enter your choice (1-7)"
    
    switch ($choice) {
        "1" {
            Write-Host "📋 Monitoring all services..." -ForegroundColor Yellow
            Write-Host "Press Ctrl+C to return to menu" -ForegroundColor Gray
            Write-Host ""
            docker-compose logs -f
        }
        "2" {
            Monitor-Trainer
        }
        "3" {
            Monitor-Processor
        }
        "4" {
            Monitor-Downloader
        }
        "5" {
            Check-ServiceStatus
        }
        "6" {
            Check-NASLocation
        }
        "7" {
            Write-Host "👋 Goodbye!" -ForegroundColor Green
            exit 0
        }
        default {
            Write-Host "❌ Invalid choice. Please try again." -ForegroundColor Red
        }
    }
    
    if ($choice -in @("1", "2", "3", "4")) {
        Write-Host ""
        Write-Host "Returned to menu..." -ForegroundColor Green
    }
}