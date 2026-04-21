param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$runtimePipelineRoot = Join-Path $repoRoot "runtime\pipeline"
$settingsPath = Join-Path $runtimePipelineRoot "auto_update_settings.json"
$statusPath = Join-Path $runtimePipelineRoot "auto_update_status.json"

if (Test-Path -LiteralPath $settingsPath) {
    Write-Host "settings_path=$settingsPath"
    Get-Content -LiteralPath $settingsPath -Raw
}
else {
    Write-Host "settings_path_missing=$settingsPath"
}

if (Test-Path -LiteralPath $statusPath) {
    Write-Host "status_path=$statusPath"
    Get-Content -LiteralPath $statusPath -Raw
}
else {
    Write-Host "status_path_missing=$statusPath"
}
