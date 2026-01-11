# run_discord_poller.ps1
# Windows PowerShell runner for Discord poller
# Sets environment variables and invokes python scripts/discord_poller.py
# 
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/run_discord_poller.ps1
#
# Or schedule via Windows Task Scheduler /TR:
#   powershell -ExecutionPolicy Bypass -File C:\path\to\scripts\run_discord_poller.ps1

param(
    [string]$BotToken = $env:DISCORD_BOT_TOKEN,
    [string]$ChannelId = $env:DISCORD_CHANNEL_ID,
    [string]$SessionId = $env:SESSION_ID,
    [string]$BaseUrl = $env:BASE_URL,
    [string]$AllowedUserId = $env:DISCORD_ALLOWED_USER_ID,
    [string]$StateFile = $env:STATE_FILE
)

# Validate required env vars
if (-not $BotToken) {
    Write-Error "DISCORD_BOT_TOKEN not set"
    exit 1
}
if (-not $ChannelId) {
    Write-Error "DISCORD_CHANNEL_ID not set"
    exit 1
}
if (-not $SessionId) {
    Write-Error "SESSION_ID not set"
    exit 1
}

# Set defaults
if (-not $BaseUrl) {
    $BaseUrl = "http://127.0.0.1:8000"
}
if (-not $StateFile) {
    $StateFile = ".discord_last_seen.json"
}

# Set environment for subprocess
$env:DISCORD_BOT_TOKEN = $BotToken
$env:DISCORD_CHANNEL_ID = $ChannelId
$env:SESSION_ID = $SessionId
$env:BASE_URL = $BaseUrl
if ($AllowedUserId) {
    $env:DISCORD_ALLOWED_USER_ID = $AllowedUserId
}
$env:STATE_FILE = $StateFile

Write-Host "[INFO] Running Discord poller..."
Write-Host "  DISCORD_CHANNEL_ID: $ChannelId"
Write-Host "  SESSION_ID: $SessionId"
Write-Host "  BASE_URL: $BaseUrl"
Write-Host "  STATE_FILE: $StateFile"

# Run the poller
python scripts/discord_poller.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Discord poller exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "[OK] Discord poller completed"
exit 0
