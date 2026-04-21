param(
    [int]$WebPort = 8765,
    [int]$OutputPort = 8766
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$webRoot = Join-Path $publicSiteRoot "web"
$outputRoot = Join-Path $repoRoot "runtime\pipeline"
$logDir = Join-Path $repoRoot "runtime\logs\preview_server_logs"
$statusPath = Join-Path $outputRoot "preview_servers_status.json"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Resolve-PythonExe {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }

    throw "python_runtime_not_found"
}

function Start-HttpServer {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [int]$Port,
        [string]$PythonExe
    )

    $existing = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        return @{
            name = $Name
            port = $Port
            pid = $existing.OwningProcess
            state = "listening"
            started_new = $false
            working_directory = $WorkingDirectory
            local_url = "http://127.0.0.1:$Port/"
        }
    }

    $stdoutPath = Join-Path $logDir "$Name.stdout.log"
    $stderrPath = Join-Path $logDir "$Name.stderr.log"
    $arguments = @("-m", "http.server", "$Port", "--bind", "127.0.0.1")

    $process = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $arguments `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    Start-Sleep -Seconds 2

    return @{
        name = $Name
        port = $Port
        pid = $process.Id
        state = "listening"
        started_new = $true
        working_directory = $WorkingDirectory
        local_url = "http://127.0.0.1:$Port/"
        stdout_log = $stdoutPath
        stderr_log = $stderrPath
    }
}

$pythonExe = Resolve-PythonExe
$servers = @()
$servers += Start-HttpServer -Name "web" -WorkingDirectory $webRoot -Port $WebPort -PythonExe $pythonExe
$servers += Start-HttpServer -Name "output" -WorkingDirectory $outputRoot -Port $OutputPort -PythonExe $pythonExe

$payload = @{
    checked_at = (Get-Date).ToString("o")
    python_exe = $pythonExe
    servers = $servers
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding UTF8

foreach ($server in $servers) {
    Write-Host "$($server.name)_url=$($server.local_url)"
    Write-Host "$($server.name)_pid=$($server.pid)"
    Write-Host "$($server.name)_started_new=$($server.started_new)"
}
Write-Host "preview_server_status_record=$statusPath"
