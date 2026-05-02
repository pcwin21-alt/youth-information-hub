param(
    [string]$TaskName = "YouthTogetherAutoUpdate",
    [string]$TaskPath = "\YouthTogether\",
    [string[]]$Times = @("09:00", "15:00", "21:00"),
    [switch]$WakeToRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$runnerScript = Join-Path $publicSiteRoot "scripts\run_scheduled_pipeline.ps1"
$outputDir = Join-Path $repoRoot "runtime\pipeline"
$installPath = Join-Path $outputDir "scheduler_installation.json"
$statusScript = Join-Path $publicSiteRoot "scripts\windows_scheduler_status.ps1"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

if (-not (Test-Path -LiteralPath $runnerScript)) {
    throw "runner_script_missing:$runnerScript"
}

$existingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($existingTask) {
    if (-not $Force) {
        throw "scheduled_task_exists:$TaskPath$TaskName"
    }

    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
}

$actionArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArguments
$triggers = @()
foreach ($time in $Times) {
    $triggerTime = [DateTime]::ParseExact($time, "HH:mm", [System.Globalization.CultureInfo]::InvariantCulture)
    $triggers += New-ScheduledTaskTrigger -Daily -At $triggerTime
}

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settingsArgs = @{
    AllowStartIfOnBatteries = $true
    DontStopIfGoingOnBatteries = $true
    StartWhenAvailable = $true
    MultipleInstances = "IgnoreNew"
}
if ($WakeToRun) {
    $settingsArgs["WakeToRun"] = $true
}
$settings = New-ScheduledTaskSettingsSet @settingsArgs

Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $action `
    -Trigger $triggers `
    -Principal $principal `
    -Settings $settings `
    -Description "Youth Together crawler auto-update at fixed daily times." | Out-Null

$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
$frequency = if ($Times.Count -eq 1) { "daily_1x" } else { "daily_$($Times.Count)x" }
$payload = @{
    task_name = $TaskName
    task_path = $TaskPath
    full_name = "$TaskPath$TaskName"
    repo_root = $repoRoot
    public_site_root = $publicSiteRoot
    runner_script = $runnerScript
    installed_at = (Get-Date).ToString("o")
    user_id = $userId
    logon_type = "Interactive"
    wake_to_run = [bool]$WakeToRun
    schedule = @{
        timezone = "Asia/Seoul"
        frequency = $frequency
        times = $Times
    }
    last_run_time = if ($taskInfo.LastRunTime -gt [datetime]::MinValue) { $taskInfo.LastRunTime.ToString("o") } else { $null }
    next_run_time = if ($taskInfo.NextRunTime -gt [datetime]::MinValue) { $taskInfo.NextRunTime.ToString("o") } else { $null }
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $installPath -Encoding UTF8

Write-Host "scheduled_task_installed=$TaskPath$TaskName"
Write-Host "scheduled_times=$($Times -join ',')"
Write-Host "wake_to_run=$([bool]$WakeToRun)"
Write-Host "installation_record=$installPath"

if (Test-Path -LiteralPath $statusScript) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $statusScript -TaskName $TaskName -TaskPath $TaskPath
}
