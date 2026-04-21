param(
    [int[]]$Ports = @(8765, 8766)
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$outputRoot = Join-Path $repoRoot "runtime\pipeline"
$statusPath = Join-Path $outputRoot "preview_servers_status.json"

$servers = @()
foreach ($port in $Ports) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    $servers += @{
        port = $port
        listening = [bool]$listener
        pid = if ($listener) { $listener.OwningProcess } else { $null }
        local_url = "http://127.0.0.1:$port/"
    }
}

$payload = @{
    checked_at = (Get-Date).ToString("o")
    servers = $servers
}

$payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statusPath -Encoding UTF8

foreach ($server in $servers) {
    Write-Host "port=$($server.port) listening=$($server.listening) pid=$($server.pid) url=$($server.local_url)"
}
Write-Host "preview_server_status_record=$statusPath"
