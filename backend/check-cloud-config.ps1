$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python workflows\cloud_connection_check.py
$connectionExit = $LASTEXITCODE
python workflows\cloud_test_status.py
if ($connectionExit -ne 0) {
    exit $connectionExit
}
exit $LASTEXITCODE

