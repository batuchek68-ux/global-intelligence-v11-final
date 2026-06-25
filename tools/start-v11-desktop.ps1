param(
  [int]$ApiPort = 8000,
  [int]$HubPort = 8787,
  [int]$FallbackHubPort = 8788,
  [int]$MaxFallbackHubPort = 8799,
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
  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (!$connect.AsyncWaitHandle.WaitOne(500, $false)) {
      return $false
    }
    $client.EndConnect($connect)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Start-HiddenProcess {
  param(
    [string]$FilePath,
    [string]$WorkingDirectory,
    [string[]]$Arguments
  )

  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $FilePath
  $startInfo.WorkingDirectory = $WorkingDirectory
  $startInfo.Arguments = (($Arguments | ForEach-Object {
    if ($_ -match '[\s"`]') {
      '"' + ($_ -replace '"', '\"') + '"'
    } else {
      $_
    }
  }) -join " ")
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  [void]$process.Start()
  return $process
}

function New-EncodedPowerShellArguments {
  param([string]$Command)
  $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
  return @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded)
}

function Select-DecisionHubPort {
  param([int]$PreferredPort, [int]$FallbackStartPort, [int]$FallbackEndPort)

  $preferredUrl = "http://127.0.0.1:$PreferredPort/"
  if (Test-HttpOk $preferredUrl) {
    return @{ Port = $PreferredPort; Url = $preferredUrl; AlreadyRunning = $true }
  }
  if (!(Test-PortListening $PreferredPort)) {
    return @{ Port = $PreferredPort; Url = $preferredUrl; AlreadyRunning = $false }
  }

  Write-Host "Decision Hub port $PreferredPort is occupied but not responding. Looking for a free fallback port." -ForegroundColor Yellow
  for ($port = $FallbackStartPort; $port -le $FallbackEndPort; $port++) {
    $url = "http://127.0.0.1:$port/"
    if (Test-HttpOk $url) {
      return @{ Port = $port; Url = $url; AlreadyRunning = $true }
    }
    if (!(Test-PortListening $port)) {
      return @{ Port = $port; Url = $url; AlreadyRunning = $false }
    }
    Write-Host "Decision Hub fallback port $port is occupied but not responding. Trying next port." -ForegroundColor Yellow
  }

  throw "No available Decision Hub port found in $FallbackStartPort-$FallbackEndPort."
}

Set-Location $Root

if (Test-HttpOk $ApiHealth) {
  Write-Host "v11 API is already running: $ApiUrl" -ForegroundColor Green
} else {
  Write-Host "Starting v11 API: $ApiUrl" -ForegroundColor Cyan
  $apiLog = Join-Path $LogDir "v11-api.log"
  $apiErr = Join-Path $LogDir "v11-api.err.log"
  $apiCommand = "python -m uvicorn backend.api.main:app --host 127.0.0.1 --port $ApiPort *> '$apiLog' 2> '$apiErr'"
  Start-HiddenProcess -FilePath "powershell.exe" -WorkingDirectory $Root -Arguments (New-EncodedPowerShellArguments $apiCommand) | Out-Null
  if (!(Wait-HttpOk $ApiHealth 45)) {
    throw "v11 API did not become healthy within 45 seconds. Check $apiLog and $apiErr"
  }
  Write-Host "v11 API is healthy: $ApiUrl" -ForegroundColor Green
}

$hubSelection = Select-DecisionHubPort $HubPort $FallbackHubPort $MaxFallbackHubPort
$HubPort = [int]$hubSelection.Port
$HubUrl = [string]$hubSelection.Url
$HubHealth = $HubUrl

if ($hubSelection.AlreadyRunning) {
  Write-Host "Decision Hub is already running: $HubUrl" -ForegroundColor Green
} else {
  Write-Host "Starting Decision Hub: $HubUrl" -ForegroundColor Cyan
  $hubRoot = Join-Path $Root "apps\decision-hub"
  $hubLog = Join-Path $LogDir "decision-hub-$HubPort.log"
  $hubErr = Join-Path $LogDir "decision-hub-$HubPort.err.log"
  $hubCommand = "& '.\server.ps1' -Port $HubPort *> '$hubLog' 2> '$hubErr'"
  Start-HiddenProcess -FilePath "powershell.exe" -WorkingDirectory $hubRoot -Arguments (New-EncodedPowerShellArguments $hubCommand) | Out-Null
  if (!(Wait-HttpOk $HubHealth 30)) {
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
