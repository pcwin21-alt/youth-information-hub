param(
    [string]$PythonExe = "",
    [switch]$UseSampleData
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot "output\scheduler_logs"
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
    $runner = Join-Path $repoRoot ".claude\skills\scheduler\scripts\cron_runner.py"
    $commandArgs = @()
    $commandArgs += $python.Args
    $commandArgs += $runner

    if ($UseSampleData) {
        $commandArgs += "--use-sample-data"
    }

    Write-Log "[$((Get-Date).ToString('o'))] scheduled_run_started"
    Write-Log "repo_root=$repoRoot"
    Write-Log "python_exe=$($python.Exe)"
    Write-Log "log_path=$logPath"

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
