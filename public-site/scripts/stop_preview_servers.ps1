param(
    [int[]]$Ports = @(8765, 8766)
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

foreach ($port in $Ports) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "stopped_port=$port pid=$($listener.OwningProcess)"
    }
}
