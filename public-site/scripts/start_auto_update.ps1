param(
    [string]$PythonExe = "",
    [int]$IntervalMinutes = 10,
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$runnerPath = Join-Path $publicSiteRoot "scripts\auto_update_runner.py"
$runtimePipelineRoot = Join-Path $repoRoot "runtime\pipeline"
$runtimeLogRoot = Join-Path $repoRoot "runtime\logs"
$statusPath = Join-Path $runtimePipelineRoot "auto_update_status.json"
$settingsPath = Join-Path $runtimePipelineRoot "auto_update_settings.json"
$stdoutPath = Join-Path $runtimeLogRoot "auto_update_runner.stdout.log"
$stderrPath = Join-Path $runtimeLogRoot "auto_update_runner.stderr.log"

New-Item -ItemType Directory -Force -Path $runtimePipelineRoot | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeLogRoot | Out-Null

function Resolve-PythonCommand {
    param([string]$Preferred)

    if ($Preferred) {
        return $Preferred
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return "$($py.Source) -3"
    }

    throw "python_runtime_not_found"
}

function Get-ExistingRunnerPid {
    if (-not (Test-Path -LiteralPath $statusPath)) {
        return $null
    }
    try {
        $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
    if (-not $status.runner_pid) {
        return $null
    }
    $existing = Get-Process -Id ([int]$status.runner_pid) -ErrorAction SilentlyContinue
    if ($existing) {
        return [int]$status.runner_pid
    }
    return $null
}

if ($Enable) {
    $settings = @{
        enabled = $true
        interval_minutes = $IntervalMinutes
        skip_outbound_notifications = $true
        publish_on_article_change_only = $true
        updated_at = (Get-Date).ToString("o")
    }
    $settings | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
}

$existingPid = Get-ExistingRunnerPid
if ($existingPid) {
    Write-Host "auto_update_runner_already_running=$existingPid"
    Write-Host "settings_path=$settingsPath"
    Write-Host "status_path=$statusPath"
    exit 0
}

$pythonCommand = Resolve-PythonCommand -Preferred $PythonExe
if ($pythonCommand -like "* -3") {
    $pySource = $pythonCommand.Split(" ")[0]
    $argumentList = "-3 `"$runnerPath`""
    $process = Start-Process -FilePath $pySource -ArgumentList $argumentList -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
}
else {
    $argumentList = "`"$runnerPath`""
    $process = Start-Process -FilePath $pythonCommand -ArgumentList $argumentList -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
}

Write-Host "auto_update_runner_started=$($process.Id)"
Write-Host "settings_path=$settingsPath"
Write-Host "status_path=$statusPath"
Write-Host "stdout_path=$stdoutPath"
Write-Host "stderr_path=$stderrPath"
