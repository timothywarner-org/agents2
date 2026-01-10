# Run the MCP server with MCP Inspector for debugging and testing

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MCP Inspector - O'Reilly Agent MVP Server" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting MCP Inspector..."
Write-Host "This opens a web UI for testing MCP tools, resources, and prompts."
Write-Host ""
Write-Host "Prerequisites:"
Write-Host "  - Node.js installed (for npx)"
Write-Host "  - Internet connection (downloads inspector on first run)"
Write-Host ""
Write-Host "The inspector will:"
Write-Host "  1. Launch the MCP server (agent-mvp)"
Write-Host "  2. Open a browser with interactive testing UI"
Write-Host "  3. Let you call tools, browse resources, and test prompts"
Write-Host ""
Write-Host "Press Ctrl+C to stop both server and inspector."
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is available
try {
    $null = Get-Command node -ErrorAction Stop
} catch {
    Write-Host "ERROR: Node.js not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "MCP Inspector requires Node.js."
    Write-Host "Install from: https://nodejs.org/"
    Write-Host ""
    exit 1
}

# Run MCP Inspector
# It will automatically download and run the inspector
npx @modelcontextprotocol/inspector python -m agent_mvp.mcp_server
