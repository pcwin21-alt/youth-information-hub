param(
    [string]$LocalUrl = "http://127.0.0.1:8765",
    [switch]$InstallIfMissing
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$publicSiteRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $publicSiteRoot
$outputRoot = Join-Path $repoRoot "runtime\pipeline"
$logDir = Join-Path $repoRoot "runtime\logs\tunnel_logs"
$statusPath = Join-Path $outputRoot "public_tunnel_status.json"
$stdoutPath = Join-Path $logDir "cloudflared.stdout.log"
$stderrPath = Join-Path $logDir "cloudflared.stderr.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Resolve-Cloudflared {
    $command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $wingetPackageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -LiteralPath $wingetPackageRoot) {
        $wingetBinary = Get-ChildItem `
            -Path $wingetPackageRoot `
            -Directory `
            -Filter "Cloudflare.cloudflared*" `
            -ErrorAction SilentlyContinue | ForEach-Object {
                Get-ChildItem -Path $_.FullName -Filter "cloudflared.exe" -ErrorAction SilentlyContinue
            } | Select-Object -First 1

        if ($wingetBinary) {
            return $wingetBinary.FullName
        }
    }

    return $null
}

function Install-Cloudflared {
    winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements --silent
}

$cloudflaredExe = Resolve-Cloudflared
if (-not $cloudflaredExe) {
    if (-not $InstallIfMissing) {
        throw "cloudflared_not_found"
    }

    Install-Cloudflared
    $cloudflaredExe = Resolve-Cloudflared
}

if (-not $cloudflaredExe) {
    throw "cloudflared_install_failed"
}

$existing = Get-CimInstance Win32_Process | Where-Object { $_.Name -like "cloudflared*" }
foreach ($process in $existing) {
    if ($process.CommandLine -like "*$LocalUrl*") {
        $payload = @{
            checked_at = (Get-Date).ToString("o")
            local_url = $LocalUrl
            process_id = $process.ProcessId
            cloudflared_exe = $cloudflaredExe
            public_url = $null
            state = "already_running"
            stdout_log = $stdoutPath
            stderr_log = $stderrPath
        }
        $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statusPath -Encoding UTF8
        Write-Host "cloudflared_pid=$($process.ProcessId)"
        Write-Host "public_url="
        Write-Host "public_tunnel_status_record=$statusPath"
        exit 0
    }
}

if (Test-Path -LiteralPath $stdoutPath) { Remove-Item -LiteralPath $stdoutPath -Force }
if (Test-Path -LiteralPath $stderrPath) { Remove-Item -LiteralPath $stderrPath -Force }

$process = Start-Process `
    -FilePath $cloudflaredExe `
    -ArgumentList @("tunnel", "--url", $LocalUrl, "--no-autoupdate") `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

$publicUrl = $null
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    $combined = ""
    if (Test-Path -LiteralPath $stdoutPath) { $combined += Get-Content -LiteralPath $stdoutPath -Raw }
    if (Test-Path -LiteralPath $stderrPath) { $combined += "`n" + (Get-Content -LiteralPath $stderrPath -Raw) }
    if ($combined -match 'https://[-a-z0-9]+\.trycloudflare\.com') {
        $publicUrl = $matches[0]
        break
    }
}

$payload = @{
    checked_at = (Get-Date).ToString("o")
    local_url = $LocalUrl
    process_id = $process.Id
    cloudflared_exe = $cloudflaredExe
    public_url = $publicUrl
    state = if ($publicUrl) { "running" } else { "starting" }
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
}

$payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statusPath -Encoding UTF8

Write-Host "cloudflared_pid=$($process.Id)"
Write-Host "public_url=$publicUrl"
Write-Host "public_tunnel_status_record=$statusPath"
