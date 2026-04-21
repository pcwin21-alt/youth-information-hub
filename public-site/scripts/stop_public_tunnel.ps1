$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$statusPath = Join-Path $repoRoot "runtime\pipeline\public_tunnel_status.json"

if (Test-Path -LiteralPath $statusPath) {
    $payload = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($payload.process_id) {
        Stop-Process -Id $payload.process_id -Force -ErrorAction SilentlyContinue
        Write-Host "stopped_cloudflared_pid=$($payload.process_id)"
    }
}
