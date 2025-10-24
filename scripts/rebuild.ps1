# Simple rebuild script for Windows
param(
    [switch]$Complete
)

# Check NAS
if (-not (Test-Path "P:\")) {
    Write-Host "ERROR: P: drive not found. Map your NAS to P: drive first."
    exit 1
}

# Create directory if needed
if (-not (Test-Path "P:\codelupe\repos")) {
    New-Item -ItemType Directory -Path "P:\codelupe\repos" -Force | Out-Null
}

# Stop containers
docker-compose down

# Remove containers
docker-compose rm -f

if ($Complete) {
    # Complete rebuild - remove all images
    docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Select-String "codelupe" | ForEach-Object {
        $imageId = ($_ -split '\s+')[1]
        docker rmi -f $imageId
    }
    docker image prune -f
    docker builder prune -f
    docker-compose build --no-cache
} else {
    # Quick rebuild - only fixed services
    docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Select-String "codelupe.*(trainer|processor|downloader)" | ForEach-Object {
        $imageId = ($_ -split '\s+')[1]
        docker rmi -f $imageId
    }
    docker builder prune -f
    docker-compose build --no-cache trainer processor downloader
}

# Start services
docker-compose up -d

Write-Host "Rebuild complete. Monitor with: docker-compose logs -f"