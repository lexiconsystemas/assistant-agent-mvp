#!/usr/bin/env python3
"""
Discord Poller — Fetches new Discord messages and POSTs them to /integrations/discord/ingest

Environment Variables:
  DISCORD_BOT_TOKEN (required): Discord bot token
  DISCORD_CHANNEL_ID (required): Discord channel ID to monitor
  SESSION_ID (required): Session ID for ingest endpoint
  BASE_URL (optional, default: http://127.0.0.1:8000): Backend URL
  DISCORD_ALLOWED_USER_ID (optional): Filter to single user
  STATE_FILE (optional, default: .discord_last_seen.json): Persist last seen message ID

Usage:
  python scripts/discord_poller.py
"""

import os
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

def _env_or_error(key: str) -> str:
    """Get environment variable or exit with error."""
    val = os.getenv(key)
    if not val:
        print(f"ERROR: {key} not set", file=sys.stderr)
        sys.exit(1)
    return val


def _load_last_seen(state_file: str) -> str | None:
    """Load last seen message ID from state file."""
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                data = json.load(f)
                return data.get("last_seen_id")
    except Exception as e:
        print(f"[WARN] Failed to load state file: {e}", file=sys.stderr)
    return None


def _save_last_seen(state_file: str, message_id: str) -> None:
    """Save last seen message ID to state file."""
    try:
        with open(state_file, "w") as f:
            json.dump({"last_seen_id": message_id}, f)
    except Exception as e:
        print(f"[WARN] Failed to save state file: {e}", file=sys.stderr)


def _fetch_discord_messages(bot_token: str, channel_id: str, limit: int = 10) -> list:
    """Fetch recent messages from Discord channel."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "User-Agent": "discord-poller/1.0",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Discord API error: {e.code} {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[ERROR] Failed to fetch Discord messages: {e}", file=sys.stderr)
        return []


def _post_ingest(base_url: str, payload: dict) -> dict | None:
    """POST message to /integrations/discord/ingest endpoint."""
    url = f"{base_url}/integrations/discord/ingest"
    headers = {"Content-Type": "application/json"}
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode("utf-8")
            return json.loads(result)
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Ingest endpoint error: {e.code} {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] Failed to POST ingest: {e}", file=sys.stderr)
        return None


def main():
    """Main poller loop."""
    bot_token = _env_or_error("DISCORD_BOT_TOKEN")
    channel_id = _env_or_error("DISCORD_CHANNEL_ID")
    session_id = _env_or_error("SESSION_ID")
    
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    state_file = os.getenv("STATE_FILE", ".discord_last_seen.json")
    allowed_user_id = os.getenv("DISCORD_ALLOWED_USER_ID")
    
    print(f"[START] Discord poller: channel={channel_id}, session={session_id}")
    
    # Load last seen message ID
    last_seen_id = _load_last_seen(state_file)
    if last_seen_id:
        print(f"[INFO] Resuming from message_id={last_seen_id}")
    
    # Fetch recent messages
    messages = _fetch_discord_messages(bot_token, channel_id, limit=10)
    if not messages:
        print("[INFO] No messages fetched")
        return
    
    print(f"[INFO] Fetched {len(messages)} messages")
    
    # Process messages (newest first, but we want oldest first for processing)
    messages_to_process = []
    for msg in reversed(messages):
        msg_id = msg.get("id")
        
        # Skip if we've already seen this message
        if last_seen_id and msg_id == last_seen_id:
            break
        if last_seen_id and int(msg_id) <= int(last_seen_id):
            continue
        
        # Skip bot messages
        author = msg.get("author", {})
        if author.get("bot"):
            print(f"[SKIP] bot message {msg_id}")
            continue
        
        # Skip if user filtering enabled and user doesn't match
        if allowed_user_id:
            author_id = author.get("id")
            if author_id != allowed_user_id:
                print(f"[SKIP] unauthorized user {author_id} in message {msg_id}")
                continue
        
        messages_to_process.append(msg)
    
    if not messages_to_process:
        print("[INFO] No new messages to process")
        return
    
    print(f"[INFO] Processing {len(messages_to_process)} new messages")
    
    # Process each message
    last_ingested_id = None
    for msg in messages_to_process:
        msg_id = msg.get("id")
        author = msg.get("author", {})
        author_name = author.get("username", "unknown")
        content = msg.get("content", "").strip()
        ts = msg.get("timestamp")
        
        if not content:
            print(f"[SKIP] empty content in message {msg_id}")
            continue
        
        # POST to ingest endpoint
        payload = {
            "session_id": session_id,
            "channel_id": channel_id,
            "message_id": msg_id,
            "author": author_name,
            "content": content,
            "ts": ts,
        }
        
        print(f"[INGEST] message_id={msg_id} author={author_name}")
        result = _post_ingest(base_url, payload)
        
        if result:
            deduped = result.get("deduped", False)
            queued = result.get("queued_reply", False)
            if deduped:
                print(f"[INFO] message_id={msg_id} was already ingested")
            elif queued:
                reply = result.get("reply_text", "")
                print(f"[INFO] message_id={msg_id} reply queued: {reply[:60]}...")
            else:
                print(f"[INFO] message_id={msg_id} ingested (no reply)")
            last_ingested_id = msg_id
        else:
            print(f"[ERROR] failed to ingest message_id={msg_id}")
    
    # Save last seen ID
    if last_ingested_id:
        _save_last_seen(state_file, last_ingested_id)
        print(f"[OK] Saved last_seen_id={last_ingested_id}")
    
    print("[END] Discord poller complete")


if __name__ == "__main__":
    main()
