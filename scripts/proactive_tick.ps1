param(
  [string]$SessionId,
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

Invoke-RestMethod -Method Post -Uri "$BaseUrl/sessions/$SessionId/proactive/tick" | ConvertTo-Json -Depth 5
