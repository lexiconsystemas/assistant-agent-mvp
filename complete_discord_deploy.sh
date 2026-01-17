#!/bin/bash
# complete_discord_deploy.sh - One command to deploy everything

set -e  # Exit on any error

echo "================================================================"
echo "Discord Integration - Complete Deployment"
echo "================================================================"

# Change to project directory
cd /Users/simonelawson/Documents/GitHub/assistant-agent-mvp

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Error: .venv not found"
    exit 1
fi

echo "✓ Activating virtual environment..."
source .venv/bin/activate

# Kill any existing processes on port 8000
echo "✓ Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 2

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "✓ Loading .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Set required environment variables (secrets come from .env file loaded above)
echo "✓ Setting environment variables..."

# CRITICAL: Backend needs this
export DISCORD_SESSION_ID="pitch-demo-session"

# Discord bot needs these (DISCORD_BOT_TOKEN comes from .env)
export API_BASE_URL="http://localhost:8000"
export SESSION_ID="pitch-demo-session"
# DISCORD_CHANNEL_ID comes from .env

# SSL fix
export SSL_CERT_FILE="/Users/simonelawson/Documents/GitHub/assistant-agent-mvp/.venv/lib/python3.14/site-packages/certifi/cacert.pem"

# Database (if you're using PostgreSQL)
export DATABASE_URL="${DATABASE_URL:-sqlite:///./assistant.db}"

echo ""
echo "Environment Configuration:"
echo "  DISCORD_SESSION_ID: $DISCORD_SESSION_ID"
echo "  API_BASE_URL: $API_BASE_URL"
echo "  DISCORD_CHANNEL_ID: $DISCORD_CHANNEL_ID"
echo "  SESSION_ID: $SESSION_ID"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "================================================================"
    echo "Shutting down..."
    echo "================================================================"
    [ ! -z "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null || true
    [ ! -z "$BOT_PID" ] && kill $BOT_PID 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

# Start backend
echo "================================================================"
echo "Starting Backend Server..."
echo "================================================================"
uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
echo "Log file: backend.log"

# Wait for backend
echo ""
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start. Check backend.log:"
        tail -20 backend.log
        exit 1
    fi
    sleep 1
    echo -n "."
done

# Clear any old session data (including mock LLM messages in outbox)
echo ""
echo "Clearing old session data..."
curl -s -X DELETE http://localhost:8000/sessions/pitch-demo-session > /dev/null 2>&1
echo "✓ Session cleared"

# Test backend configuration
echo ""
echo "Testing backend configuration..."
TEST_RESPONSE=$(curl -s -X POST http://localhost:8000/integrations/discord/inbound \
    -H "Content-Type: application/json" \
    -d '{
        "channel_id": "1455374022840680574",
        "author": "ConfigTest",
        "author_id": "123",
        "content": "Configuration test message",
        "message_id": "config-test-'$(date +%s)'",
        "ts": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
        "raw": {}
    }')

echo "Backend test response:"
echo "$TEST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TEST_RESPONSE"

if echo "$TEST_RESPONSE" | grep -q '"ok": *true'; then
    echo "✓ Backend is properly configured!"
else
    echo "❌ Backend configuration issue detected!"
    echo ""
    echo "Response shows:"
    echo "$TEST_RESPONSE"
    echo ""
    if echo "$TEST_RESPONSE" | grep -q "DISCORD_SESSION_ID"; then
        echo "❌ DISCORD_SESSION_ID is not set properly in backend!"
        echo ""
        echo "FIX: The backend process needs DISCORD_SESSION_ID in its environment."
        echo "Current value: $DISCORD_SESSION_ID"
        echo ""
        echo "Restarting backend with explicit environment..."
        kill $BACKEND_PID 2>/dev/null || true
        sleep 2
        
        # Start backend with explicit env var
        DISCORD_SESSION_ID="pitch-demo-session" uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
        BACKEND_PID=$!
        
        echo "Waiting for backend restart..."
        sleep 5
        
        # Test again
        TEST_RESPONSE2=$(curl -s -X POST http://localhost:8000/integrations/discord/inbound \
            -H "Content-Type: application/json" \
            -d '{
                "channel_id": "1455374022840680574",
                "author": "RetryTest",
                "author_id": "123",
                "content": "Retry test",
                "message_id": "retry-test-'$(date +%s)'",
                "ts": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
                "raw": {}
            }')
        
        if echo "$TEST_RESPONSE2" | grep -q '"ok": *true'; then
            echo "✓ Backend fixed and working!"
        else
            echo "❌ Still failing. Response:"
            echo "$TEST_RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$TEST_RESPONSE2"
            exit 1
        fi
    else
        exit 1
    fi
fi

# Start Discord Full Bot (listener + reply sender)
echo ""
echo "================================================================"
echo "Starting Discord Full Bot (Listener + Reply Sender)..."
echo "================================================================"
python scripts/discord_full_bot.py > discord_bot.log 2>&1 &
BOT_PID=$!
echo "Bot PID: $BOT_PID"
echo "Log file: discord_bot.log"

# Wait for bot to connect
echo ""
echo "Waiting for bot to connect to Discord..."
for i in {1..20}; do
    if grep -q "Bot logged in" discord_bot.log 2>/dev/null; then
        BOT_NAME=$(grep "Bot logged in as" discord_bot.log | sed 's/.*Bot logged in as //' | sed 's/ (.*//')
        echo "✓ Bot connected as: $BOT_NAME"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "❌ Bot failed to connect. Check discord_bot.log:"
        tail -20 discord_bot.log
        exit 1
    fi
    sleep 1
    echo -n "."
done

# All systems go!
echo ""
echo "================================================================"
echo "🚀 SYSTEM IS LIVE!"
echo "================================================================"
echo ""
echo "✅ Backend running on http://localhost:8000"
echo "✅ Discord full bot connected (listening + replying)"
echo "✅ Session ID: pitch-demo-session"
echo ""
echo "================================================================"
echo "💬 TEST IT NOW:"
echo "================================================================"
echo "1. Open Discord"
echo "2. Go to your test channel"
echo "3. Send a message: 'Hello assistant!'"
echo "4. Watch the logs below"
echo ""
echo "================================================================"
echo "📊 API Endpoints:"
echo "================================================================"
echo "  Health:    curl http://localhost:8000/health"
echo "  Outbox:    curl http://localhost:8000/sessions/pitch-demo-session/outbox"
echo "  History:   curl http://localhost:8000/sessions/pitch-demo-session"
echo "  Tasks:     curl http://localhost:8000/sessions/pitch-demo-session/tasks"
echo ""
echo "================================================================"
echo "📝 Monitoring Logs (Press Ctrl+C to stop):"
echo "================================================================"
echo ""

# Tail both logs with clear separation
tail -f backend.log discord_bot.log | while read line; do
    if [[ $line == *"[INFO]"* ]] && [[ $line == *"discord_full_bot"* ]]; then
        echo "🤖 BOT: $line"
    elif [[ $line == *"[START]"* ]] || [[ $line == *"[END]"* ]] || [[ $line == *"[INBOUND]"* ]] || [[ $line == *"[OUTBOX]"* ]]; then
        echo "🔧 API: $line"
    else
        echo "$line"
    fi
done
