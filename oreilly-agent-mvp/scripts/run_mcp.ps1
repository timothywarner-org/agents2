# Run the MCP server for O'Reilly Agent MVP

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "Starting O'Reilly Agent MVP MCP Server..."
Write-Host "Project root: $ProjectRoot"
Write-Host ""
Write-Host "The server will listen on stdio for MCP client connections."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

python -m agent_mvp.mcp_server
