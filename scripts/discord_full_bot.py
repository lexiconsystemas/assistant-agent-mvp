#!/usr/bin/env python3
"""
Discord Full Bot - Listens for messages AND sends replies

This combines the listener and reply sender into one bot to avoid permission issues.

Environment Variables:
  DISCORD_BOT_TOKEN (required): Discord bot token
  API_BASE_URL (required): Backend URL (e.g., http://127.0.0.1:8000)
  SESSION_ID (required): Session ID for messages
  DISCORD_CHANNEL_ID (required): Channel to monitor and reply in

Usage:
  python scripts/discord_full_bot.py
"""

import os
import sys
import json
import requests
import logging
import asyncio
from typing import Optional

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord_full_bot")


def _env_or_error(key: str) -> str:
    """Get environment variable or exit with error."""
    val = os.getenv(key)
    if not val:
        logger.error(f"{key} not set")
        sys.exit(1)
    return val


class DiscordFullBot(commands.Cog):
    """Combined Discord bot for listening and replying."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_token = _env_or_error("DISCORD_BOT_TOKEN")
        self.api_base_url = _env_or_error("API_BASE_URL").rstrip("/")
        self.session_id = _env_or_error("SESSION_ID")
        self.channel_id = _env_or_error("DISCORD_CHANNEL_ID")
        
        self.reply_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot connects and is ready."""
        logger.info(f"Bot logged in as {self.bot.user} (ID: {self.bot.user.id})")
        if self.channel_id:
            logger.info(f"Monitoring and replying in channel: {self.channel_id}")
        else:
            logger.info("Monitoring all channels (no DISCORD_CHANNEL_ID set)")
        
        # Start reply polling task
        self.reply_task = asyncio.create_task(self.poll_outbox())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages and post inbound to backend."""
        # Ignore bot messages (including self)
        if message.author.bot:
            return

        # Filter by channel if configured
        if self.channel_id and str(message.channel.id) != self.channel_id:
            return

        # Build inbound event payload
        payload = {
            "channel_id": str(message.channel.id),
            "author": str(message.author.name),
            "author_id": str(message.author.id),
            "content": message.content,
            "message_id": str(message.id),
            "ts": message.created_at.isoformat(),
            "raw": {
                "guild_id": str(message.guild.id) if message.guild else None,
                "webhook_id": message.webhook_id,
                "reference": str(message.reference) if message.reference else None,
            },
        }

        # POST to backend
        await self._post_inbound(payload)

    async def _post_inbound(self, payload: dict) -> bool:
        """POST inbound message to backend."""
        url = f"{self.api_base_url}/integrations/discord/inbound"
        
        try:
            logger.info("=" * 60)
            logger.info("POSTING MESSAGE TO BACKEND")
            logger.info(f"URL: {url}")
            logger.info(f"Author: {payload['author']}")
            logger.info(f"Content: {payload['content'][:100]}")
            logger.info("=" * 60)
            
            response = requests.post(url, json=payload, timeout=10)
            
            logger.info(f"Backend response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("ok"):
                    logger.info("✓ Message accepted by backend")
                    if data.get("ingested"):
                        logger.info("✓ Message processed (not duplicate)")
                    else:
                        logger.info("⊙ Message was duplicate (already processed)")
                    
                    if data.get("reply_text"):
                        logger.info(f"✓ REPLY GENERATED: {data['reply_text'][:100]}...")
                        logger.info("  (Reply queued in outbox for delivery)")
                    return True
                else:
                    error = data.get("error", "Unknown error")
                    logger.error(f"✗ Backend rejected message: {error}")
                    if "DISCORD_SESSION_ID" in error:
                        logger.error("  >> Set DISCORD_SESSION_ID env var when starting backend!")
                        logger.error("  >> Example: export DISCORD_SESSION_ID='test-session'")
                    return False
            else:
                logger.error(f"✗ Backend HTTP error {response.status_code}")
                logger.error(f"  Response: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"✗ Exception while posting: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

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
            
            # Get the channel (use bot.get_channel, not self.bot.get_channel)
            channel = self.bot.get_channel(int(self.channel_id))
            if not channel:
                logger.error(f"Could not find channel {self.channel_id}")
                # Debug: List all channels the bot can see
                logger.info("Available channels:")
                for guild in self.bot.guilds:
                    logger.info(f"  Guild: {guild.name}")
                    for ch in guild.text_channels:
                        logger.info(f"    - {ch.name} (ID: {ch.id})")
                return
            
            # Send message to Discord
            discord_msg = await channel.send(text)
            
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
    """Initialize and run the bot."""
    bot_token = _env_or_error("DISCORD_BOT_TOKEN")
    api_base_url = _env_or_error("API_BASE_URL")
    session_id = _env_or_error("SESSION_ID")

    logger.info(f"Starting Discord Full Bot")
    logger.info(f"API Base URL: {api_base_url}")
    logger.info(f"Session ID: {session_id}")

    # Create bot with minimal intents + message content
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    intents.messages = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Add the cog
    await bot.add_cog(DiscordFullBot(bot))

    # Start the bot
    try:
        await bot.start(bot_token)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await bot.close()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
