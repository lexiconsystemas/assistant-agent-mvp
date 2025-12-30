# scripts/run_outbox_consumer.ps1
# Runs the outbox consumer with your defaults (Task Scheduler-safe)

$env:DISCORD_WEBHOOK_URL = " "

$SessionId = "b7309de1-7c56-4432-93f6-96f36de729b1"
$BaseUrl = "http://127.0.0.1:8000"
$MaxRetries = 2
$RetryMinutes = 10

& "$PSScriptRoot\outbox_consumer.ps1" `
  -SessionId $SessionId `
  -BaseUrl $BaseUrl `
  -MaxRetries $MaxRetries `
  -RetryMinutes $RetryMinutes
