param(
  [string]$SessionId,
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [int]$MaxRetries = 2,
    [int]$RetryMinutes = 20
)

<#
Simple Outbox consumer simulator.

Optional Discord delivery mode:
- Set the environment variable `DISCORD_WEBHOOK_URL` to your Discord webhook URL
    (e.g. in PowerShell: `$env:DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/ID/TOKEN'`).
- When set, the consumer will POST `{ "content": "<message text>" }` with
    `application/json` to the webhook for each undelivered outbox message.
    On success (HTTP 200 or 204) the consumer will call the delivered endpoint
    for that message. On failure it will call the attempt endpoint.

Flow:
 1) POST /sessions/{id}/proactive/tick
 2) GET /sessions/{id}/outbox
 3) For each undelivered message:
        - If `DISCORD_WEBHOOK_URL` set: POST JSON `{ "content": "<text>" }` to webhook
            - on success -> POST /sessions/{id}/outbox/{message_id}/delivered
            - on failure -> POST /sessions/{id}/outbox/{message_id}/attempt
        - If webhook not set: fallback to console delivery and existing attempt/deliver logic

This simulates a delivery channel (e.g., SMS or Discord) without external services.
#>

function Safe-Invoke($scriptBlock) {
    try {
        & $scriptBlock
    } catch {
        Write-Host "ERROR: $($_.Exception.Message)"
        return $null
    }
}

Write-Host "Outbox consumer starting for session: $SessionId (BaseUrl=$BaseUrl)";

# Read optional Discord webhook from environment
$discord = $env:DISCORD_WEBHOOK_URL
if ($discord) { Write-Host "Discord webhook mode enabled." }

# 1) tick
try {
    $tick = Invoke-RestMethod -Method Post -Uri "$BaseUrl/sessions/$SessionId/proactive/tick" -ErrorAction Stop
    Write-Host "Tick response: $($tick | ConvertTo-Json -Depth 3)"
} catch {
    Write-Host "ERROR: tick failed -> $($_.Exception.Message)"; exit 2
}

# 2) get outbox
try {
    $out = Invoke-RestMethod -Method Get -Uri "$BaseUrl/sessions/$SessionId/outbox" -ErrorAction Stop
} catch {
    Write-Host "ERROR: failed to fetch outbox -> $($_.Exception.Message)"; exit 3
}

if (-not $out.outbox -or $out.outbox.Count -eq 0) {
    Write-Host "No outbox messages to deliver."; exit 0
}

foreach ($m in $out.outbox) {
    if ($m.delivered) { continue }
    if ($discord) {
        Write-Host "DELIVERING to Discord: $($m.text)";
        # post JSON { "content": "<text>" }
        try {
            $body = @{ content = $m.text } | ConvertTo-Json -Depth 3
            $resp = Invoke-RestMethod -Method Post -Uri $discord -ContentType 'application/json' -Body $body -ErrorAction Stop
            # Discord webhooks often return 204 No Content or 200 OK
            Write-Host "Discord webhook response received. Marking delivered for $($m.id)"
            # call delivered endpoint
            try {
                $del = Invoke-RestMethod -Method Post -Uri "$BaseUrl/sessions/$SessionId/outbox/$($m.id)/delivered" -ErrorAction Stop
                Write-Host "Marked delivered: $($del | ConvertTo-Json -Depth 2)"
            } catch {
                Write-Host "ERROR: mark delivered failed for $($m.id) -> $($_.Exception.Message)"
            }
            continue
        } catch {
            Write-Host "WARNING: Discord delivery failed for $($m.id) -> $($_.Exception.Message)"
            # fall through to attempt increment
        }
    } else {
        Write-Host "DELIVERING: $($m.text)";
    }

    # 3) increment attempt
    try {
        $attemptResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/sessions/$SessionId/outbox/$($m.id)/attempt" -ErrorAction Stop
    } catch {
        Write-Host "ERROR: attempt call failed for $($m.id) -> $($_.Exception.Message)"; continue
    }

    $attempts = $null
    if ($attemptResp -and $attemptResp.attempts -ne $null) { $attempts = [int]$attemptResp.attempts }

    if ($attempts -ne $null -and $attempts -ge $MaxRetries) {
        Write-Host "Max attempts reached ($attempts). Marking delivered (gave_up) for $($m.id)"
        try {
            $del = Invoke-RestMethod -Method Post -Uri "$BaseUrl/sessions/$SessionId/outbox/$($m.id)/delivered" -ErrorAction Stop
            Write-Host "Marked delivered: $($del | ConvertTo-Json -Depth 2)"
        } catch {
            Write-Host "ERROR: mark delivered failed for $($m.id) -> $($_.Exception.Message)"
        }
    } else {
        Write-Host "Attempted delivery for $($m.id). Attempts=$attempts. Will retry after $RetryMinutes minutes if undelivered."
    }
}

Write-Host "Outbox consumer finished.";
