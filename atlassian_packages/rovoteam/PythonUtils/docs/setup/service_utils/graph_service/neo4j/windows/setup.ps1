# Neo4j Setup Script for Windows
# Requires Docker Desktop

param(
    [string]$Version = "5-community"
)

Write-Host "=== Neo4j Setup ===" -ForegroundColor Cyan

# Check Docker
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

if ($dockerAvailable) {
    Write-Host "Docker detected. Starting Neo4j $Version via Docker..." -ForegroundColor Green
    $composeFile = Join-Path $PSScriptRoot ".." "docker-compose.yml"
    docker compose -f $composeFile up -d
    Write-Host "Waiting for Neo4j to start (may take 15-30s)..." -ForegroundColor Yellow
    $retries = 0
    do {
        Start-Sleep -Seconds 5
        $retries++
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:7474" -ErrorAction SilentlyContinue
            if ($response) { break }
        } catch {}
    } while ($retries -lt 12)

    if ($retries -ge 12) {
        Write-Host "Neo4j did not start in time. Check: docker logs" -ForegroundColor Red
        exit 1
    }
    Write-Host "Neo4j is running." -ForegroundColor Green
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
        Write-Host "WSL2 detected. Checking Neo4j in WSL..." -ForegroundColor Green

        $neo4jInstalled = wsl -d Ubuntu -- bash -c "which neo4j 2>/dev/null"
        if (-not $neo4jInstalled) {
            Write-Host "Neo4j not found in WSL. Install it manually (see README)." -ForegroundColor Yellow
            Write-Host "  wsl -d Ubuntu -- bash -c 'sudo apt install -y neo4j'" -ForegroundColor Yellow
            exit 1
        }

        # Start Neo4j
        Write-Host "Starting Neo4j in WSL..." -ForegroundColor Yellow
        wsl -d Ubuntu -- bash -c "sudo neo4j start"

        Write-Host "Waiting for Neo4j to start (may take 15-30s)..." -ForegroundColor Yellow
        $retries = 0
        do {
            Start-Sleep -Seconds 5
            $retries++
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:7474" -ErrorAction SilentlyContinue
                if ($response) { break }
            } catch {}
        } while ($retries -lt 12)

        if ($retries -ge 12) {
            Write-Host "Neo4j did not start in time. Check WSL manually." -ForegroundColor Red
            exit 1
        }
        Write-Host "Neo4j is running in WSL2." -ForegroundColor Green
    } else {
        Write-Host "Neither Docker nor WSL2 found." -ForegroundColor Red
        Write-Host "Options:" -ForegroundColor Yellow
        Write-Host "  1. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        Write-Host "  2. Enable WSL2: wsl --install"
        Write-Host "  3. Download Neo4j: https://neo4j.com/download/"
        exit 1
    }
}

# Install Python package
Write-Host "`nInstalling Python package..." -ForegroundColor Cyan
pip install neo4j

Write-Host "`n=== Neo4j setup complete ===" -ForegroundColor Green
Write-Host "Bolt:    bolt://localhost:7687"
Write-Host "Browser: http://localhost:7474"
Write-Host "Auth:    neo4j / testpassword"
