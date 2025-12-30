# Minimal dependency-free smoke test for assistant-agent-mvp
# Usage: run this from the repository root while the server is running on port 8000

$base = "http://127.0.0.1:8000"

function Try-Get([string]$uri) {
    try {
        return Invoke-RestMethod -Method Get -Uri $uri -ErrorAction Stop
    } catch {
        Write-Host "ERROR: Failed to GET $uri -> $($_.Exception.Message)"
        return $null
    }
}

function Try-Post([string]$uri, $body) {
    try {
        return Invoke-RestMethod -Method Post -Uri $uri -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 5) -ErrorAction Stop
    } catch {
        Write-Host "ERROR: Failed to POST $uri -> $($_.Exception.Message)"
        return $null
    }
}

Write-Host "Starting smoke test against $base ..."

# 0) quick health check
$health = Try-Get "$base/health"
if (-not $health) {
    Write-Host "Server health check failed. Ensure the app is running (uvicorn app.main:app --reload --port 8000)"; exit 2
}

# 1) POST /chat with message 'hello'
$resp1 = Try-Post "$base/chat" @{ message = 'hello' }
if (-not $resp1) { Write-Host 'FAIL: /chat hello failed'; exit 1 }
$session = $resp1.session_id
Write-Host "Step 1: session_id=$session"

# 2) POST /chat add task buy groceries with same session_id
$resp2 = Try-Post "$base/chat" @{ message = 'add task buy groceries'; session_id = $session }
if (-not $resp2) { Write-Host 'FAIL: /chat add task failed'; exit 1 }
Write-Host "Step 2: add task reply: $($resp2.reply)"

# 3) POST /chat list tasks with same session_id
$resp3 = Try-Post "$base/chat" @{ message = 'list tasks'; session_id = $session }
if (-not $resp3) { Write-Host 'FAIL: /chat list tasks failed'; exit 1 }
$listReply = $resp3.reply
Write-Host "Step 3: list tasks reply:`n$listReply`n"

# 4) GET /sessions/{session_id}/tasks
$tasksResp = Try-Get "$base/sessions/$session/tasks"
if (-not $tasksResp) { Write-Host 'FAIL: GET /sessions/{id}/tasks failed'; exit 1 }
Write-Host "Step 4: tasks endpoint returned:`n$($tasksResp | ConvertTo-Json -Depth 5)`n"

# 5) GET /sessions/{session_id}/proactive
$proactive = Try-Get "$base/sessions/$session/proactive"
if (-not $proactive) { Write-Host 'FAIL: GET /sessions/{id}/proactive failed'; exit 1 }
Write-Host "Step 5: proactive endpoint returned:`n$($proactive | ConvertTo-Json -Depth 5)`n"

# Summary checks
$passed = $true
$errors = @()

if (-not $session) {
    $passed = $false; $errors += 'session_id missing from first /chat response'
}

if (-not ($listReply -match '\|')) {
    $passed = $false; $errors += 'list tasks reply did not contain a task id line (no "|")'
}

if (-not ($tasksResp.tasks -and $tasksResp.tasks.Count -ge 1)) {
    $passed = $false; $errors += 'tasks endpoint did not return at least one task'
}

Write-Host "----- SMOKE TEST SUMMARY -----"
if ($passed) {
    Write-Host 'PASS: All checks passed'
    exit 0
} else {
    Write-Host 'FAIL: One or more checks failed:'
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}
