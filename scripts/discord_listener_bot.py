#!/usr/bin/env python3
"""
Discord Listener Bot — Real-time message capture via discord.py

Connects to Discord, listens for messages in configured channel(s),
and POSTs inbound messages to the FastAPI backend.

Environment Variables:
  DISCORD_BOT_TOKEN (required): Discord bot token
  API_BASE_URL (required): Backend URL (e.g., http://127.0.0.1:8000)
  SESSION_ID (required): Session ID for inbound messages (MVP hardcoded)
  DISCORD_CHANNEL_ID (optional): Specific channel to monitor (if empty, listen to all)

Usage:
  python scripts/discord_listener_bot.py

Notes:
  - Requires discord.py: pip install discord.py
  - Bot must have Message Content Intent enabled in Discord Developer Portal
"""

import os
import sys
import json
import requests
import logging
from typing import Optional

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord_listener")


def _env_or_error(key: str) -> str:
    """Get environment variable or exit with error."""
    val = os.getenv(key)
    if not val:
        logger.error(f"{key} not set")
        sys.exit(1)
    return val


class DiscordListenerBot(commands.Cog):
    """Cog for handling Discord messages and posting to backend."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_token = _env_or_error("DISCORD_BOT_TOKEN")
        self.api_base_url = _env_or_error("API_BASE_URL").rstrip("/")
        self.session_id = _env_or_error("SESSION_ID")
        self.channel_id = os.getenv("DISCORD_CHANNEL_ID")  # optional

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot connects and is ready."""
        logger.info(f"Bot logged in as {self.bot.user} (ID: {self.bot.user.id})")
        if self.channel_id:
            logger.info(f"Listening to channel: {self.channel_id}")
        else:
            logger.info("Listening to all channels (no DISCORD_CHANNEL_ID set)")

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
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Posted message_id={payload['message_id']} "
                    f"from {payload['author']}: "
                    f"ingested={data.get('ingested')}, "
                    f"reply={bool(data.get('reply_text'))}"
                )
                return True
            else:
                logger.error(f"Backend error {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to POST inbound: {e}")
            return False


async def main():
    """Initialize and run the bot."""
    bot_token = _env_or_error("DISCORD_BOT_TOKEN")
    api_base_url = _env_or_error("API_BASE_URL")
    session_id = _env_or_error("SESSION_ID")

    logger.info(f"Starting Discord listener bot")
    logger.info(f"API Base URL: {api_base_url}")
    logger.info(f"Session ID: {session_id}")

    # Create bot with minimal intents + message content
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    intents.messages = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Add the listener cog
    await bot.add_cog(DiscordListenerBot(bot))

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
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
