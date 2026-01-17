#!/usr/bin/env python3
"""
Discord Reply Sender - Sends agent replies back to Discord

Polls the backend outbox and sends undelivered messages back to Discord.

Environment Variables:
  DISCORD_BOT_TOKEN (required): Discord bot token
  API_BASE_URL (required): Backend URL (e.g., http://127.0.0.1:8000)
  SESSION_ID (required): Session ID to poll
  DISCORD_CHANNEL_ID (required): Channel to send replies to

Usage:
  python scripts/discord_reply_sender.py
"""

import os
import sys
import time
import logging
import requests
import asyncio
from typing import Optional

import discord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord_reply_sender")


def _env_or_error(key: str) -> str:
    """Get environment variable or exit with error."""
    val = os.getenv(key)
    if not val:
        logger.error(f"{key} not set")
        sys.exit(1)
    return val


class DiscordReplySender:
    """Polls backend outbox and sends replies to Discord."""

    def __init__(self):
        self.bot_token = _env_or_error("DISCORD_BOT_TOKEN")
        self.api_base_url = _env_or_error("API_BASE_URL").rstrip("/")
        self.session_id = _env_or_error("SESSION_ID")
        self.channel_id = _env_or_error("DISCORD_CHANNEL_ID")
        
        # Discord client for sending messages
        intents = discord.Intents.default()
        intents.message_content = False  # We only need to send messages
        self.client = discord.Client(intents=intents)
        
        self.channel = None

    async def start(self):
        """Start the reply sender."""
        logger.info("Starting Discord Reply Sender")
        logger.info(f"API Base URL: {self.api_base_url}")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Channel ID: {self.channel_id}")

        # Setup event handler
        @self.client.event
        async def on_ready():
            """Called when bot connects."""
            logger.info(f"Bot logged in as {self.client.user} (ID: {self.client.user.id})")
            
            # Get the channel
            self.channel = self.client.get_channel(int(self.channel_id))
            if not self.channel:
                logger.error(f"Could not find channel {self.channel_id}")
                await self.client.close()
                return
                
            logger.info(f"Connected to channel: {self.channel.name}")
            
            # Start polling loop
            await self.poll_outbox()

        # Connect to Discord
        await self.client.start(self.bot_token)

    async def poll_outbox(self):
        """Poll backend outbox and send replies."""
        logger.info("Starting outbox polling loop...")
        
        while True:
            try:
                # Get undelivered messages from outbox
                response = requests.get(
                    f"{self.api_base_url}/sessions/{self.session_id}/outbox",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    outbox = data.get("outbox", [])
                    
                    # Find undelivered messages
                    undelivered = [msg for msg in outbox if not msg.get("delivered", False)]
                    
                    if undelivered:
                        logger.info(f"Found {len(undelivered)} undelivered messages")
                        
                        for msg in undelivered:
                            await self.send_reply(msg)
                            
                else:
                    logger.error(f"Failed to get outbox: {response.status_code}")
                
                # Wait before next poll
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)

    async def send_reply(self, msg: dict):
        """Send a reply message to Discord."""
        try:
            text = msg.get("text", "").strip()
            if not text:
                logger.warning("Empty message, skipping")
                return

            logger.info(f"Sending reply: {text[:60]}...")
            
            # Send message to Discord
            discord_msg = await self.channel.send(text)
            
            # Mark as delivered in backend
            response = requests.patch(
                f"{self.api_base_url}/sessions/{self.session_id}/outbox/{msg['id']}",
                json={"delivered": True, "delivered_at": discord_msg.created_at.isoformat()},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Reply sent and marked as delivered")
            else:
                logger.error(f"Failed to mark as delivered: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending reply: {e}")


async def main():
    """Initialize and run the reply sender."""
    sender = DiscordReplySender()
    await sender.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
