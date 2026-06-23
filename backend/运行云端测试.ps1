param(
    [string]$Repository = $env:GITHUB_REPOSITORY,
    [string]$Token = $env:GITHUB_TOKEN,
    [string]$Branch = "main",
    [switch]$CreateRepo,
    [switch]$Upload,
    [switch]$Public,
    [switch]$NoTrigger
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ProjectRoot "run-cloud-test.ps1") @PSBoundParameters
exit $LASTEXITCODE
