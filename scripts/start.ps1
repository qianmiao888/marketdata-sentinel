param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $SkipInstall) {
    uv sync --all-extras --frozen
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
uv run python -m sentinel.cli seed
if ($LASTEXITCODE -ne 0) { throw 'Seed failed' }
uv run python -m sentinel.cli scenario missing
if ($LASTEXITCODE -ne 0) { throw 'Missing scenario preparation failed' }
uv run python -m sentinel.cli scenario stale
if ($LASTEXITCODE -ne 0) { throw 'Stale scenario preparation failed' }
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$apiResponds = $false
try {
    $response = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2
    $apiResponds = $response.service -eq 'MarketData Sentinel'
} catch { }
New-Item -ItemType Directory -Path 'data' -Force | Out-Null
if (-not $apiResponds) {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','sentinel.api:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput 'data\api.stdout.log' -RedirectStandardError 'data\api.stderr.log' -PassThru
    $apiProcess.Id | Set-Content 'data\api.pid'
}
$uiResponds = $false
try { $uiResponds = (Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 2).StatusCode -eq 200 } catch { }
if (-not $uiResponds) {
    $uiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','streamlit','run','sentinel/ui.py','--server.address','127.0.0.1','--server.headless','true','--browser.gatherUsageStats','false') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput 'data\ui.stdout.log' -RedirectStandardError 'data\ui.stderr.log' -PassThru
    $uiProcess.Id | Set-Content 'data\ui.pid'
}
$ready = $false
for ($attempt=0; $attempt -lt 20; $attempt++) {
    try {
        $apiReady = Invoke-RestMethod 'http://127.0.0.1:8000/ready' -TimeoutSec 2
        $uiReady = Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 2
        if ($apiReady.status -eq 'ready' -and $uiReady.StatusCode -eq 200) { $ready=$true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw 'Services did not become ready; inspect data/*.stderr.log. Check for port conflicts.' }
Write-Host 'Ready: http://127.0.0.1:8501  | API docs: http://127.0.0.1:8000/docs'
Write-Host 'Stop only processes started by this script: scripts/stop.ps1'
