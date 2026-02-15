from __future__ import annotations

import logging
import sys

import discord
from discord.ext import commands

from config import SETTINGS, IDS


def setup_logging() -> None:
    level = getattr(logging, SETTINGS.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


class RoleSyncBot(commands.Bot):
    async def setup_hook(self) -> None:
        log = logging.getLogger("bot")

        # Load cogs so commands exist in the app command tree
        await self.load_extension("cogs.role_sync")

        # Make the commands show up instantly: copy globals -> guild & sync per guild
        guilds = [discord.Object(id=IDS.PUBLIC_GUILD_ID), discord.Object(id=IDS.PRIVATE_GUILD_ID)]
        for g in guilds:
            try:
                self.tree.copy_global_to(guild=g)
                synced = await self.tree.sync(guild=g)
                log.info("Synced %d app command(s) to guild %s: %s",
                         len(synced), g.id, ", ".join(cmd.name for cmd in synced) or "(none)")
            except Exception:
                log.exception("Failed to sync app commands to guild %s", g.id)


def main() -> None:
    setup_logging()

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True  # Dev Portal -> Privileged Gateway Intents -> Server Members Intent

    bot = RoleSyncBot(
        command_prefix="!",  # prefix commands are not used; slash commands are
        intents=intents,
        allowed_mentions=discord.AllowedMentions.none(),
    )

    bot.run(SETTINGS.token)


if __name__ == "__main__":
    main()
