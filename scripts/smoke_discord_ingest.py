#!/usr/bin/env python3
"""
Smoke Test — Discord Ingest

Verifies:
  1. OK response on first ingest
  2. Deduped=True on duplicate message_id
  3. Outbox contains queued reply
  4. Agent reply text is captured

Usage:
  python scripts/smoke_discord_ingest.py
"""

import json
import sys
import urllib.request
import urllib.error
import os
from datetime import datetime, timezone

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION_ID = "test-discord-session-" + str(datetime.now(timezone.utc).timestamp())
CHANNEL_ID = "test-channel-123"


def post_ingest(message_id: str, author: str, content: str) -> dict | None:
    """POST to /integrations/discord/ingest"""
    url = f"{BASE_URL}/integrations/discord/ingest"
    payload = {
        "session_id": SESSION_ID,
        "channel_id": CHANNEL_ID,
        "message_id": message_id,
        "author": author,
        "content": content,
    }
    
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode("utf-8")
            return json.loads(result)
    except Exception as e:
        print(f"[ERROR] POST failed: {e}", file=sys.stderr)
        return None


def get_outbox() -> list:
    """GET /sessions/{session_id}/outbox"""
    url = f"{BASE_URL}/sessions/{SESSION_ID}/outbox"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            result = response.read().decode("utf-8")
            data = json.loads(result)
            return data.get("outbox", [])
    except Exception as e:
        print(f"[ERROR] GET outbox failed: {e}", file=sys.stderr)
        return []


def main():
    """Run smoke tests"""
    print(f"[TEST] Session: {SESSION_ID}")
    print(f"[TEST] Base URL: {BASE_URL}\n")
    
    # Test 1: First ingest (no dedup)
    print("=" * 60)
    print("TEST 1: First ingest (should NOT be deduped)")
    print("=" * 60)
    
    msg_id_1 = "msg-123-first"
    result1 = post_ingest(msg_id_1, "alice", "Hello, this is my first message!")
    
    if not result1:
        print("[FAIL] No response from endpoint", file=sys.stderr)
        sys.exit(1)
    
    print(f"Response: {json.dumps(result1, indent=2)}")
    
    assert result1.get("ok") == True, "ok should be True"
    assert result1.get("deduped") == False, "deduped should be False (first ingest)"
    assert result1.get("queued_reply") == True, "queued_reply should be True"
    
    reply_text_1 = result1.get("reply_text")
    print(f"\n✓ First ingest OK, deduped=False, reply queued")
    print(f"  Reply: {reply_text_1}\n")
    
    # Test 2: Duplicate message (should dedup)
    print("=" * 60)
    print("TEST 2: Duplicate message (should dedup)")
    print("=" * 60)
    
    result2 = post_ingest(msg_id_1, "alice", "Hello, this is my first message!")
    
    print(f"Response: {json.dumps(result2, indent=2)}")
    
    assert result2.get("ok") == True, "ok should be True"
    assert result2.get("deduped") == True, "deduped should be True (duplicate)"
    assert result2.get("queued_reply") == False, "queued_reply should be False (deduped)"
    
    print(f"\n✓ Duplicate detected, deduped=True\n")
    
    # Test 3: Different message (no dedup)
    print("=" * 60)
    print("TEST 3: Different message (should NOT be deduped)")
    print("=" * 60)
    
    msg_id_2 = "msg-456-second"
    result3 = post_ingest(msg_id_2, "bob", "This is a different message.")
    
    print(f"Response: {json.dumps(result3, indent=2)}")
    
    assert result3.get("ok") == True, "ok should be True"
    assert result3.get("deduped") == False, "deduped should be False (different message)"
    assert result3.get("queued_reply") == True, "queued_reply should be True"
    
    print(f"\n✓ Second message OK, deduped=False, reply queued\n")
    
    # Test 4: Check outbox
    print("=" * 60)
    print("TEST 4: Verify replies in outbox")
    print("=" * 60)
    
    outbox = get_outbox()
    print(f"Outbox ({len(outbox)} messages):")
    for msg in outbox:
        print(f"  - {msg.get('id')}: {msg.get('text')[:50]}...")
        assert msg.get("reason") == "discord_reply", f"reason should be 'discord_reply', got {msg.get('reason')}"
    
    assert len(outbox) >= 2, f"Expected at least 2 messages in outbox, got {len(outbox)}"
    
    print(f"\n✓ Outbox contains queued replies\n")
    
    # Summary
    print("=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nSummary:")
    print(f"  - First ingest: OK, deduped=False, reply queued")
    print(f"  - Duplicate ingest: OK, deduped=True")
    print(f"  - Second message: OK, deduped=False, reply queued")
    print(f"  - Outbox: {len(outbox)} messages queued for Discord delivery")


if __name__ == "__main__":
    main()
