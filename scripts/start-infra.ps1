#Requires -Version 5.1
<#
.SYNOPSIS
    Start local PostgreSQL and Redis for the v12 runtime.
.NOTES
    Requires Docker Desktop with the Linux engine running (WSL2).
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Install Docker Desktop first."
}

try {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker daemon not running" }
} catch {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) {
        Write-Host "Starting Docker Desktop..."
        Start-Process $desktop
        Write-Host "Wait until Docker is ready, then re-run this script."
    }
    throw "Docker daemon unavailable. Start Docker Desktop (WSL2) and retry."
}

Push-Location $repo
try {
    docker compose -f docker-compose.infra.yml up -d
    Write-Host "`nInfrastructure started. Set these for the API process:"
    Write-Host '  $env:CLOUD_OS_DATABASE_URL = "postgresql://codex:codex@127.0.0.1:5432/codex_v11"'
    Write-Host '  $env:REDIS_URL = "redis://127.0.0.1:6379/0"'
    Write-Host '  $env:CLOUD_OS_USE_DB = "1"'
} finally {
    Pop-Location
}
