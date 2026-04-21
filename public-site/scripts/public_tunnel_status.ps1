$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$statusPath = Join-Path $repoRoot "runtime\pipeline\public_tunnel_status.json"

if (-not (Test-Path -LiteralPath $statusPath)) {
    throw "public_tunnel_status_missing"
}

$payload = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$process = Get-Process -Id $payload.process_id -ErrorAction SilentlyContinue

Write-Host "state=$(if ($process) { 'running' } else { 'stopped' })"
Write-Host "local_url=$($payload.local_url)"
Write-Host "public_url=$($payload.public_url)"
Write-Host "process_id=$($payload.process_id)"
Write-Host "stdout_log=$($payload.stdout_log)"
Write-Host "stderr_log=$($payload.stderr_log)"
Write-Host "checked_at=$($payload.checked_at)"
