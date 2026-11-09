$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
foreach ($serviceName in @('api','ui')) {
    $pidFile = Join-Path $projectRoot "data\$serviceName.pid"
    if (Test-Path -LiteralPath $pidFile) {
        $servicePid = [int](Get-Content -LiteralPath $pidFile)
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid" -ErrorAction SilentlyContinue
        $expected = if ($serviceName -eq 'api') { 'sentinel.api:app' } else { 'sentinel/ui.py' }
        if ($processInfo -and $processInfo.CommandLine.Contains($expected) -and $processInfo.ExecutablePath.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $servicePid
        }
        Remove-Item -LiteralPath $pidFile
    }
}
