param(
  [int]$ApiPort = 8000,
  [int]$HubPort = 8787,
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ApiUrl = "http://127.0.0.1:$ApiPort"
$HubUrl = "http://127.0.0.1:$HubPort/"
$ApiHealth = "$ApiUrl/v1/health"
$HubHealth = "$HubUrl"
$LogDir = Join-Path $Root "work\runtime"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-HttpOk {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
    return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-HttpOk {
  param([string]$Url, [int]$Seconds = 30)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk $Url) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}
function Test-PortListening {
  param([int]$Port)
  try {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $connection
  } catch {
    return $false
  }
}

Set-Location $Root

if (Test-HttpOk $ApiHealth) {
  Write-Host "v11 API is already running: $ApiUrl" -ForegroundColor Green
} else {
  Write-Host "Starting v11 API: $ApiUrl" -ForegroundColor Cyan
  $apiLog = Join-Path $LogDir "v11-api.log"
  $apiErr = Join-Path $LogDir "v11-api.err.log"
  Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -WorkingDirectory $Root -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "python -m uvicorn backend.api.main:app --host 127.0.0.1 --port $ApiPort *> '$apiLog' 2> '$apiErr'"
  ) | Out-Null
  if (!(Wait-HttpOk $ApiHealth 45)) {
    throw "v11 API did not become healthy within 45 seconds. Check $apiLog and $apiErr"
  }
  Write-Host "v11 API is healthy: $ApiUrl" -ForegroundColor Green
}

if ((Test-HttpOk $HubHealth) -or (Test-PortListening $HubPort)) {
  Write-Host "Decision Hub is already running: $HubUrl" -ForegroundColor Green
} else {
  Write-Host "Starting Decision Hub: $HubUrl" -ForegroundColor Cyan
  $hubRoot = Join-Path $Root "apps\decision-hub"
  $hubLog = Join-Path $LogDir "decision-hub.log"
  $hubErr = Join-Path $LogDir "decision-hub.err.log"
  Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -WorkingDirectory $hubRoot -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ".\server.ps1",
    "-Port", "$HubPort"
  ) -RedirectStandardOutput $hubLog -RedirectStandardError $hubErr | Out-Null
  if (!(Wait-HttpOk $HubHealth 30) -and !(Test-PortListening $HubPort)) {
    throw "Decision Hub did not start within 30 seconds. Check $hubLog and $hubErr"
  }
  Write-Host "Decision Hub is ready: $HubUrl" -ForegroundColor Green
}

if (!$NoOpen) {
  Start-Process $HubUrl | Out-Null
}

Write-Host "v11 desktop delivery is running." -ForegroundColor Green
Write-Host "API: $ApiUrl"
Write-Host "Decision Hub: $HubUrl"