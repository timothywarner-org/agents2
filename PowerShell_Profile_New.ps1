#!/usr/bin/env pwsh
# ============================================================================
# POWERSHELL - CLEAN CONFIG (matching .bashrc)
# ============================================================================

# --- Terminal settings ---
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Clear screen
Clear-Host

# --- Change to project directory ---
try {
    if (Test-Path "C:\github\agents2\oreilly-agent-mvp") {
        Set-Location "C:\github\agents2\oreilly-agent-mvp"
    } elseif (Test-Path "C:\github") {
        Set-Location "C:\github"
    }
} catch {
    # Silently continue
}

# ============================================================================
# POWERLINE-STYLE PROMPT WITH GIT BRANCH
# ============================================================================

function prompt {
    $exitCode = $LASTEXITCODE

    # Powerline characters (require Nerd Font)
    $rightArrow = [char]0xe0b0  #
    $gitBranch = [char]0xe0a0   #
    $gitDirty = [char]0xf0c9    #
    $gitClean = [char]0xf00c    #

    # Color scheme (matching bash blue/green/yellow)
    $pathBg = "Blue"
    $pathFg = "White"
    $gitCleanBg = "Green"
    $gitCleanFg = "White"
    $gitDirtyBg = "Yellow"
    $gitDirtyFg = "Black"

    # Get current path, truncate if too long
    $currentPath = $PWD.Path
    if ($currentPath -like "$HOME*") {
        $currentPath = $currentPath.Replace($HOME, "~")
    }
    if ($currentPath.Length -gt 40) {
        $currentPath = "..." + $currentPath.Substring($currentPath.Length - 37)
    }

    # Path segment
    Write-Host -NoNewline -ForegroundColor $pathFg -BackgroundColor $pathBg " $currentPath "
    Write-Host -NoNewline -ForegroundColor $pathBg "$rightArrow"

    # Git segment
    try {
        $null = git rev-parse --git-dir 2>$null
        if ($LASTEXITCODE -eq 0) {
            $gitBranchName = git branch --show-current 2>$null
            $gitStatus = git status --porcelain 2>$null

            if ($gitBranchName) {
                $isDirty = $gitStatus.Length -gt 0
                $statusIcon = if ($isDirty) { $gitDirty } else { $gitClean }
                $statusBg = if ($isDirty) { $gitDirtyBg } else { $gitCleanBg }
                $statusFg = if ($isDirty) { $gitDirtyFg } else { $gitCleanFg }

                Write-Host -NoNewline -ForegroundColor $statusFg -BackgroundColor $statusBg " $gitBranch $gitBranchName $statusIcon "
                Write-Host -NoNewline -ForegroundColor $statusBg "$rightArrow"
            }
        }
    } catch {
        # Not in a git repo, continue silently
    }

    # New line for command input
    Write-Host ""

    # Prompt character (cyan for success, red for error)
    if ($exitCode -eq 0 -or $null -eq $exitCode) {
        Write-Host -NoNewline -ForegroundColor "Cyan" "$ "
    } else {
        Write-Host -NoNewline -ForegroundColor "Red" "$ "
    }

    return ""
}

# --- Useful aliases (matching .bashrc) ---
Set-Alias -Name ll -Value Get-ChildItem -Option AllScope -Force
function gs { git status $args }
function gd { git diff $args }
function gl { git log --oneline -10 $args }

# ============================================================================
# RETAINED UTILITIES
# ============================================================================

# KEYLIGHT TOGGLE
function keylights {
    & keylights.bat
}
Set-Alias -Name keylight -Value keylights -Option AllScope

# TEACHING DESKTOP TOGGLE
function desktop {
    & "C:\tools\desktop\desktop.cmd"
}

# ============================================================================
# OLD CONFIG (commented out)
# ============================================================================
<#
# Previous config had:
# - ASCII art banner
# - System info display (uptime, reboot pending, admin mode)
# - DeepSeek daily affirmations
# - Weather/sunrise API calls
# - Complex powerline with folder icons
# - Cache management
#
# All of that functionality has been commented out to match the simpler .bashrc style
# If you want any of these features back, uncomment the relevant sections below.

$ENABLE_POWERLINE_PROMPT = $true
$script:DeepSeekActive = $false

function Get-FormattedUptime { ... }
function Test-PendingReboot { ... }
function Test-IsElevated { ... }
function Get-SunriseSunset { ... }
function Get-DeepSeekAffirmation { ... }
function Get-WeatherForecast { ... }

# ASCII Art Header
Write-Host ""
Write-Host "  ██╗  ██╗██╗      ████████╗██╗███╗   ███╗██╗" -ForegroundColor Cyan
...
Write-Host "===============================================================" -ForegroundColor DarkCyan
Write-Host " [UPTIME]          " -NoNewline -ForegroundColor Yellow
Write-Host $uptime -ForegroundColor White
...
#>
