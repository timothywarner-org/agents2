# Start the interactive menu for the O'Reilly Agent MVP

Write-Host "Starting O'Reilly Agent MVP Interactive Menu..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
& .venv\Scripts\Activate.ps1

# Run the menu
python -m agent_mvp.cli.interactive_menu
