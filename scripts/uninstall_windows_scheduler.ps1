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

$existingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
}

Remove-Item -LiteralPath $installPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $statusPath -Force -ErrorAction SilentlyContinue

Write-Host "scheduled_task_removed=$TaskPath$TaskName"
