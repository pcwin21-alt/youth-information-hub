param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$statusPath = Join-Path $repoRoot "runtime\pipeline\auto_update_status.json"

if (-not (Test-Path -LiteralPath $statusPath)) {
    Write-Host "auto_update_status_missing=$statusPath"
    exit 0
}

$status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$pid = $status.runner_pid
if (-not $pid) {
    Write-Host "auto_update_runner_pid_missing"
    exit 0
}

$process = Get-Process -Id ([int]$pid) -ErrorAction SilentlyContinue
if (-not $process) {
    Write-Host "auto_update_runner_not_running=$pid"
    exit 0
}

Stop-Process -Id ([int]$pid) -Force
Write-Host "auto_update_runner_stopped=$pid"
