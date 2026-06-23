param(
  [int]$Port = 8890
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebRoot = Join-Path $Root "frontend\web"

if (-not (Test-Path $WebRoot)) {
  Write-Error "Web root not found: $WebRoot"
  exit 1
}

Write-Host "Starting trade platform web preview..."
Write-Host "URL: http://127.0.0.1:$Port/"
Write-Host "Web root: $WebRoot"
Write-Host "Press Ctrl+C to stop."

python -m http.server $Port --bind 127.0.0.1 --directory $WebRoot
