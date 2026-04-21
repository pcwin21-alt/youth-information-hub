param(
    [switch]$CriticalOnlyOnBattery
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$outputDir = Join-Path $repoRoot "runtime\pipeline"
$statusPath = Join-Path $outputDir "wake_configuration_status.json"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$rtcWakeGuid = "bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d"
$schemeOutput = powercfg /getactivescheme
if ($schemeOutput -notmatch "GUID:\s+([a-fA-F0-9-]+)") {
    throw "active_power_scheme_not_found"
}
$activeSchemeGuid = $matches[1]

$acValue = 1
$dcValue = if ($CriticalOnlyOnBattery) { 2 } else { 1 }

powercfg /setacvalueindex $activeSchemeGuid SUB_SLEEP $rtcWakeGuid $acValue | Out-Null
powercfg /setdcvalueindex $activeSchemeGuid SUB_SLEEP $rtcWakeGuid $dcValue | Out-Null
powercfg /setactive $activeSchemeGuid | Out-Null

$sleepSupport = powercfg /a | Out-String
$wakeTimerConfig = powercfg /q $activeSchemeGuid SUB_SLEEP $rtcWakeGuid | Out-String

$payload = @{
    checked_at = (Get-Date).ToString("o")
    active_scheme_guid = $activeSchemeGuid
    wake_timers_ac = $acValue
    wake_timers_dc = $dcValue
    battery_mode = if ($CriticalOnlyOnBattery) { "critical_only" } else { "enabled" }
    sleep_support = $sleepSupport.Trim()
    wake_timer_config = $wakeTimerConfig.Trim()
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding UTF8

Write-Host "active_scheme_guid=$activeSchemeGuid"
Write-Host "wake_timers_ac=$acValue"
Write-Host "wake_timers_dc=$dcValue"
Write-Host "battery_mode=$($payload.battery_mode)"
Write-Host "wake_config_record=$statusPath"
