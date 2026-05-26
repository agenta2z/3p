# Redis Setup Script for Windows
# Requires Docker Desktop or Memurai

param(
    [string]$Version = "7-alpine"
)

Write-Host "=== Redis Setup ===" -ForegroundColor Cyan

# Check Docker
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

if ($dockerAvailable) {
    Write-Host "Docker detected. Starting Redis $Version via Docker..." -ForegroundColor Green
    $composeFile = Join-Path $PSScriptRoot ".." "docker-compose.yml"
    docker compose -f $composeFile up -d
    Start-Sleep -Seconds 3
    Write-Host "Verifying..." -ForegroundColor Yellow
    docker exec (docker compose -f $composeFile ps -q redis) redis-cli ping
} else {
    Write-Host "Docker not found. Trying WSL2..." -ForegroundColor Yellow

    # Check if WSL is available with a running distro
    $wslAvailable = $false
    try {
        $wslList = wsl --list --verbose 2>$null
        if ($LASTEXITCODE -eq 0 -and $wslList -match "Running") {
            $wslAvailable = $true
        }
    } catch { }

    if ($wslAvailable) {
        Write-Host "WSL2 detected. Checking Redis in WSL..." -ForegroundColor Green

        # Check if redis-server is installed
        $redisInstalled = wsl -d Ubuntu -- bash -c "which redis-server 2>/dev/null"
        if (-not $redisInstalled) {
            Write-Host "Installing Redis in WSL..." -ForegroundColor Yellow
            wsl -d Ubuntu -- bash -c "sudo apt update && sudo apt install -y redis-server"
        }

        # Start Redis service
        Write-Host "Starting Redis in WSL..." -ForegroundColor Yellow
        wsl -d Ubuntu -- bash -c "sudo service redis-server start"
        Start-Sleep -Seconds 2

        # Verify
        Write-Host "Verifying..." -ForegroundColor Yellow
        $ping = wsl -d Ubuntu -- bash -c "redis-cli ping 2>/dev/null"
        if ($ping -eq "PONG") {
            Write-Host "Redis is running in WSL2." -ForegroundColor Green
        } else {
            Write-Host "Redis failed to start in WSL. Check WSL manually." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Neither Docker nor WSL2 found." -ForegroundColor Red
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "  1. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        Write-Host "  2. Enable WSL2: wsl --install"
        Write-Host "  3. Install Memurai (Windows Redis): https://www.memurai.com/"
        exit 1
    }
}

# Install Python package
Write-Host "`nInstalling Python package..." -ForegroundColor Cyan
pip install redis

Write-Host "`n=== Redis setup complete ===" -ForegroundColor Green
Write-Host "Connection: localhost:6379"
