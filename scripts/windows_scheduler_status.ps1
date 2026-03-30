param(
    [string]$TaskName = "",
    [string]$TaskPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $repoRoot "output"
$installPath = Join-Path $outputDir "scheduler_installation.json"
$statusPath = Join-Path $outputDir "scheduler_task_status.json"

if ((-not $TaskName) -or (-not $TaskPath)) {
    if (Test-Path -LiteralPath $installPath) {
        $installInfo = Get-Content -LiteralPath $installPath -Raw | ConvertFrom-Json
        if (-not $TaskName) {
            $TaskName = $installInfo.task_name
        }
        if (-not $TaskPath) {
            $TaskPath = $installInfo.task_path
        }
    }
}

if (-not $TaskName) {
    $TaskName = "YouthTogetherAutoUpdate"
}
if (-not $TaskPath) {
    $TaskPath = "\YouthTogether\"
}

$task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

$triggerInfo = @()
foreach ($trigger in $task.Triggers) {
    $triggerInfo += @{
        start_boundary = $trigger.StartBoundary
        end_boundary = $trigger.EndBoundary
        days_interval = $trigger.DaysInterval
        trigger_type = $trigger.CimClass.CimClassName
    }
}

$payload = @{
    task_name = $TaskName
    task_path = $TaskPath
    full_name = "$TaskPath$TaskName"
    state = "$($task.State)"
    enabled = $task.Settings.Enabled
    wake_to_run = $task.Settings.WakeToRun
    start_when_available = $task.Settings.StartWhenAvailable
    allow_start_if_on_batteries = $task.Settings.AllowStartIfOnBatteries
    dont_stop_if_going_on_batteries = $task.Settings.DontStopIfGoingOnBatteries
    last_run_time = if ($taskInfo.LastRunTime -gt [datetime]::MinValue) { $taskInfo.LastRunTime.ToString("o") } else { $null }
    next_run_time = if ($taskInfo.NextRunTime -gt [datetime]::MinValue) { $taskInfo.NextRunTime.ToString("o") } else { $null }
    last_task_result = $taskInfo.LastTaskResult
    number_of_missed_runs = $taskInfo.NumberOfMissedRuns
    triggers = $triggerInfo
    checked_at = (Get-Date).ToString("o")
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding UTF8

Write-Host "task_name=$TaskPath$TaskName"
Write-Host "state=$($payload.state)"
Write-Host "enabled=$($payload.enabled)"
Write-Host "wake_to_run=$($payload.wake_to_run)"
Write-Host "start_when_available=$($payload.start_when_available)"
Write-Host "last_run_time=$($payload.last_run_time)"
Write-Host "next_run_time=$($payload.next_run_time)"
Write-Host "last_task_result=$($payload.last_task_result)"
Write-Host "scheduler_status_record=$statusPath"
