# ============================================================================
# O'Reilly AI Agents MVP - Run Watcher Script (PowerShell)
# ============================================================================
# Starts the folder watcher to automatically process incoming issues.
# Run from the project root: .\scripts\run_watcher.ps1
# Press Ctrl+C to stop.
# ============================================================================

$ErrorActionPreference = "Stop"

# Activate virtual environment if not already active
if (-not $env:VIRTUAL_ENV) {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "Starting folder watcher..." -ForegroundColor Cyan
Write-Host "Watching: incoming/" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run the watcher
python -m agent_mvp.watcher.folder_watcher

if ($LASTEXITCODE -ne 0) {
    Write-Host "Watcher exited with code: $LASTEXITCODE" -ForegroundColor Yellow
}
