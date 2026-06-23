param(
    [string]$Repository,
    [switch]$CreateRepo,
    [switch]$Public,
    [switch]$NoTrigger,
    [switch]$SaveRepository
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Test-RepositoryName {
    param([string]$Value)
    if (-not $Value) {
        return $false
    }
    $Parts = $Value.Split("/")
    if ($Parts.Count -ne 2) {
        return $false
    }
    $Owner = $Parts[0]
    $Name = $Parts[1]
    if ($Owner -ne $Owner.Trim() -or $Name -ne $Name.Trim()) {
        return $false
    }
    if ([string]::IsNullOrWhiteSpace($Owner) -or [string]::IsNullOrWhiteSpace($Name)) {
        return $false
    }
    if ($Owner -match '^(owner|yourname|username)$' -or $Name -match '^(repository|repo)$') {
        return $false
    }
    return $Owner -match '^[A-Za-z0-9]([A-Za-z0-9-]{0,38}[A-Za-z0-9])?$' -and $Name -match '^[A-Za-z0-9._-]+$'
}

Write-Host "GitHub cloud test setup" -ForegroundColor Cyan
Write-Host "This session will not save your GitHub token to disk."
Write-Host ""

$LocalConfig = Join-Path $ProjectRoot "cloud.local.json"
if (Test-Path $LocalConfig) {
    $Config = Get-Content $LocalConfig -Raw | ConvertFrom-Json
    if (-not $Repository) {
        $Repository = $Config.repository
    }
    if ($Repository) {
        Write-Host "Using repository from cloud.local.json: $Repository"
    }
}

if ($Repository -and $SaveRepository) {
    if (-not (Test-RepositoryName $Repository)) {
        Write-Host "Repository must be a real GitHub owner/repository, for example octocat/international-trade-ai." -ForegroundColor Yellow
        python workflows\cloud_test_status.py
        exit 2
    }
    @{
        repository = $Repository
        branch = "main"
    } | ConvertTo-Json -Depth 2 | Set-Content -Path $LocalConfig -Encoding UTF8
    Write-Host "Saved repository to cloud.local.json. Token was not saved."
}

if (-not $Repository) {
    $Repository = Read-Host "GitHub repository (owner/repository)"
    if ($Repository -and -not $SaveRepository) {
        $SaveAnswer = Read-Host "Save repository to cloud.local.json for next time? (y/N)"
        if ($SaveAnswer -match "^(y|yes)$") {
            $SaveRepository = $true
        }
    }
    if ($Repository -and $SaveRepository) {
        if (-not (Test-RepositoryName $Repository)) {
            Write-Host "Repository must be a real GitHub owner/repository, for example octocat/international-trade-ai." -ForegroundColor Yellow
            python workflows\cloud_test_status.py
            exit 2
        }
        @{
            repository = $Repository
            branch = "main"
        } | ConvertTo-Json -Depth 2 | Set-Content -Path $LocalConfig -Encoding UTF8
        Write-Host "Saved repository to cloud.local.json. Token was not saved."
    }
}

if ($Repository -and -not (Test-RepositoryName $Repository)) {
    Write-Host "Repository must be a real GitHub owner/repository, for example octocat/international-trade-ai." -ForegroundColor Yellow
    python workflows\cloud_test_status.py
    exit 2
}

$SecureToken = Read-Host "GitHub token" -AsSecureString
$Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
)

if (-not $Repository -or -not $Token) {
    Write-Host "Repository and token are required." -ForegroundColor Yellow
    python workflows\cloud_run.py
    python workflows\cloud_test_status.py
    exit $LASTEXITCODE
}

$argsList = @("-Repository", $Repository, "-Token", $Token)
if ($CreateRepo) {
    $argsList += "-CreateRepo"
} else {
    $argsList += "-Upload"
}
if ($Public) {
    $argsList += "-Public"
}
if ($NoTrigger) {
    $argsList += "-NoTrigger"
}

& (Join-Path $ProjectRoot "run-cloud-test.ps1") @argsList
exit $LASTEXITCODE
