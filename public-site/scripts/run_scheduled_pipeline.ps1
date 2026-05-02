param(
    [string]$PythonExe = "",
    [switch]$UseSampleData,
    [switch]$SendOutboundNotifications
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$logDir = Join-Path $repoRoot "runtime\logs\scheduler_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "scheduled_run_$timestamp.log"

function Write-Log {
    param([string]$Message)
    Write-Host $Message
    Add-Content -LiteralPath $logPath -Value $Message -Encoding UTF8
}

function Resolve-PythonCommand {
    param([string]$Preferred)

    if ($Preferred) {
        return @{
            Exe = $Preferred
            Args = @()
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            Exe = $python.Source
            Args = @()
        }
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return @{
            Exe = $py.Source
            Args = @("-3")
        }
    }

    throw "python_runtime_not_found"
}

try {
    $python = Resolve-PythonCommand -Preferred $PythonExe
    $runner = Join-Path $publicSiteRoot "scripts\cron_runner.py"
    $commandArgs = @()
    $commandArgs += $python.Args
    $commandArgs += $runner

    if ($UseSampleData) {
        $commandArgs += "--use-sample-data"
    }
    if (-not $SendOutboundNotifications) {
        $commandArgs += "--skip-outbound-notifications"
    }

    Write-Log "[$((Get-Date).ToString('o'))] scheduled_run_started"
    Write-Log "repo_root=$repoRoot"
    Write-Log "public_site_root=$publicSiteRoot"
    Write-Log "python_exe=$($python.Exe)"
    Write-Log "log_path=$logPath"
    Write-Log "send_outbound_notifications=$([bool]$SendOutboundNotifications)"

    & $python.Exe @commandArgs 2>&1 | ForEach-Object {
        $line = ($_ | Out-String).TrimEnd()
        if ($line) {
            Write-Log $line
        }
    }

    $exitCode = $LASTEXITCODE
    Write-Log "[$((Get-Date).ToString('o'))] scheduled_run_finished exit_code=$exitCode"
    exit $exitCode
}
catch {
    Write-Log "[$((Get-Date).ToString('o'))] scheduled_run_failed"
    Write-Log ($_ | Out-String)
    exit 1
}
