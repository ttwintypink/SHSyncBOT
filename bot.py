from __future__ import annotations

import logging
import sys

import discord
from discord.ext import commands

from config import SETTINGS


def setup_logging() -> None:
    level = getattr(logging, SETTINGS.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


class RoleSyncBot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("cogs.role_sync")


def main() -> None:
    setup_logging()

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True  # IMPORTANT: enable "Server Members Intent" in Dev Portal

    bot = RoleSyncBot(
        command_prefix="!",  # slash commands are used; no message content intent needed
        intents=intents,
        allowed_mentions=discord.AllowedMentions.none(),
    )

    bot.run(SETTINGS.token)


if __name__ == "__main__":
    main()
