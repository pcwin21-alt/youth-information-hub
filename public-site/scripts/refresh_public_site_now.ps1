param(
    [string]$PythonExe = "",
    [switch]$UseSampleData,
    [switch]$SkipOutboundNotifications,
    [switch]$PrintOnly
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$logDir = Join-Path $repoRoot "runtime\logs\manual_refresh"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir "manual_refresh_$timestamp.log"

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
    $statusScript = Join-Path $publicSiteRoot "scripts\status_report.py"

    $commandArgs = @()
    $commandArgs += $python.Args
    $commandArgs += $runner
    $commandArgs += "--curator-max-network-enrich"
    $commandArgs += "20"

    if ($UseSampleData) {
        $commandArgs += "--use-sample-data"
    }
    if ($SkipOutboundNotifications) {
        $commandArgs += "--skip-outbound-notifications"
    }

    if ($PrintOnly) {
        Write-Host "python_exe=$($python.Exe)"
        Write-Host "command=$($python.Exe) $($commandArgs -join ' ')"
        Write-Host "log_path=$logPath"
        exit 0
    }

    Write-Log "[$((Get-Date).ToString('o'))] manual_refresh_started"
    Write-Log "repo_root=$repoRoot"
    Write-Log "public_site_root=$publicSiteRoot"
    Write-Log "python_exe=$($python.Exe)"
    Write-Log "log_path=$logPath"

    & $python.Exe @commandArgs 2>&1 | ForEach-Object {
        $line = ($_ | Out-String).TrimEnd()
        if ($line) {
            Write-Log $line
        }
    }

    $exitCode = $LASTEXITCODE
    Write-Log "[$((Get-Date).ToString('o'))] manual_refresh_finished exit_code=$exitCode"

    if ($exitCode -eq 0) {
        & $python.Exe @($python.Args + $statusScript) 2>&1 | ForEach-Object {
            $line = ($_ | Out-String).TrimEnd()
            if ($line) {
                Write-Log $line
            }
        }
    }

    exit $exitCode
}
catch {
    Write-Log "[$((Get-Date).ToString('o'))] manual_refresh_failed"
    Write-Log ($_ | Out-String)
    exit 1
}
