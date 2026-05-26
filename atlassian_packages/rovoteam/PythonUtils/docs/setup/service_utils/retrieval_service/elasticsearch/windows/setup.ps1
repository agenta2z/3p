# Elasticsearch Setup Script for Windows
# Requires Docker Desktop

param(
    [string]$Version = "8.12.0"
)

Write-Host "=== Elasticsearch Setup ===" -ForegroundColor Cyan

# Check Docker
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

if ($dockerAvailable) {
    Write-Host "Docker detected. Starting Elasticsearch $Version via Docker..." -ForegroundColor Green
    $composeFile = Join-Path $PSScriptRoot ".." "docker-compose.yml"
    docker compose -f $composeFile up -d
    Write-Host "Waiting for Elasticsearch to start (may take 30-60s)..." -ForegroundColor Yellow
    $retries = 0
    do {
        Start-Sleep -Seconds 5
        $retries++
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:9200" -ErrorAction SilentlyContinue
            if ($response) { break }
        } catch {}
    } while ($retries -lt 12)

    if ($retries -ge 12) {
        Write-Host "Elasticsearch did not start in time. Check: docker logs" -ForegroundColor Red
        exit 1
    }
    Write-Host "Elasticsearch is running." -ForegroundColor Green
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
        Write-Host "WSL2 detected. Checking Elasticsearch in WSL..." -ForegroundColor Green

        $esInstalled = wsl -d Ubuntu -- bash -c "test -f /usr/share/elasticsearch/bin/elasticsearch 2>/dev/null || dpkg -l elasticsearch 2>/dev/null | grep -q '^ii'"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Elasticsearch not found in WSL. Install it manually (see README)." -ForegroundColor Yellow
            exit 1
        }

        # Start Elasticsearch
        Write-Host "Starting Elasticsearch in WSL..." -ForegroundColor Yellow
        wsl -d Ubuntu -- bash -c "sudo service elasticsearch start"

        Write-Host "Waiting for Elasticsearch to start (may take 30-60s)..." -ForegroundColor Yellow
        $retries = 0
        do {
            Start-Sleep -Seconds 5
            $retries++
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:9200" -ErrorAction SilentlyContinue
                if ($response) { break }
            } catch {}
        } while ($retries -lt 12)

        if ($retries -ge 12) {
            Write-Host "Elasticsearch did not start in time. Check WSL manually." -ForegroundColor Red
            exit 1
        }
        Write-Host "Elasticsearch is running in WSL2." -ForegroundColor Green
    } else {
        Write-Host "Neither Docker nor WSL2 found." -ForegroundColor Red
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "  1. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        Write-Host "  2. Enable WSL2: wsl --install"
        Write-Host "  3. Download Elasticsearch: https://www.elastic.co/downloads/elasticsearch"
        exit 1
    }
}

# Install Python package
Write-Host "`nInstalling Python package..." -ForegroundColor Cyan
pip install elasticsearch

Write-Host "`n=== Elasticsearch setup complete ===" -ForegroundColor Green
Write-Host "Connection: http://localhost:9200"
