# Delivery Consumer (Outbox) — README

This document explains how to enable and run the local Outbox consumer for
proactive messages. The consumer can optionally deliver messages to a
Discord channel using a webhook.

1) Create a Discord webhook
- In your Discord server, open Server Settings → Integrations → Webhooks.
- Create a new webhook and copy the webhook URL (it looks like
  `https://discord.com/api/webhooks/<id>/<token>`).

2) Set `DISCORD_WEBHOOK_URL`
- You can set the environment variable in a `.env` file or in PowerShell.
- Example PowerShell (current shell only):
  ```powershell
  $env:DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/ID/TOKEN'
  ```
- Or add `DISCORD_WEBHOOK_URL` to your system/user environment variables or
  place it into a `.env` file that your workflow loads before running the
  consumer. The consumer script reads `DISCORD_WEBHOOK_URL` from the process
  environment.

3) Run the consumer manually
- Console-only mode (no webhook):
  ```powershell
  .\scripts\outbox_consumer.ps1 -SessionId "<SESSION_ID>" -BaseUrl "http://127.0.0.1:8000"
  ```
- Discord mode (set env var first):
  ```powershell
  $env:DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/ID/TOKEN'
  .\scripts\outbox_consumer.ps1 -SessionId "<SESSION_ID>"
  ```

4) Schedule the consumer (Task Scheduler example — every 20 minutes)
- Create a scheduled task that runs PowerShell and calls the consumer script.
- Example `schtasks` command (run in an elevated PowerShell prompt):
  ```powershell
  schtasks /Create /SC MINUTE /MO 20 /TN "OutboxConsumer" /TR "PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\path\to\assistant-agent-mvp\scripts\outbox_consumer.ps1\" -SessionId \"<SESSION_ID>\"" /F
  ```

Notes
- The consumer posts the proactive tick, fetches the outbox, and attempts
  delivery. When the Discord webhook successfully accepts the message, the
  consumer marks the message delivered by calling the server's delivered
  endpoint.
- This feature requires no server-side changes beyond the existing outbox
  endpoints and is optional. Ensure your server (`uvicorn`) is running and
  reachable from the machine running the consumer.
