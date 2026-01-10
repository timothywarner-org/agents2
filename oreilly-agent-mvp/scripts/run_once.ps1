# ============================================================================
# O'Reilly AI Agents MVP - Run Once Script (PowerShell)
# ============================================================================
# Runs the pipeline once on a mock issue.
# Run from the project root: .\scripts\run_once.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

# Ensure script runs from the project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
Set-Location $projectRoot

# Activate virtual environment if not already active
if (-not $env:VIRTUAL_ENV) {
    & .\.venv\Scripts\Activate.ps1
}

# Default mock file
$MockFile = $args[0]
if (-not $MockFile) {
    $MockFile = "mock_issues/issue_001.json"
}

Write-Host "Running pipeline with: $MockFile" -ForegroundColor Cyan
Write-Host ""

# Run the pipeline
python -m agent_mvp.pipeline.run_once --source mock --mock-file $MockFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Pipeline failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Done\! Check the outgoing/ folder for results." -ForegroundColor Green
