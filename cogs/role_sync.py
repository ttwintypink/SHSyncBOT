from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import IDS, SETTINGS

log = logging.getLogger("role_sync")


class RoleSync(commands.Cog):
    """
    Source of truth: PRIVATE_ROLE_SH_ID in the private guild.
    Target state in public guild:
      - If user has SH in private -> add PUBLIC SH, remove PUBLIC FUN SH
      - Else (including left/kicked/banned) -> remove PUBLIC SH, add PUBLIC FUN SH
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.public_guild: Optional[discord.Guild] = None
        self.private_guild: Optional[discord.Guild] = None

        self.public_role_sh: Optional[discord.Role] = None
        self.public_role_fun: Optional[discord.Role] = None
        self.private_role_sh: Optional[discord.Role] = None

        self._ready_once = False

        self._user_locks: dict[int, asyncio.Lock] = {}

        self.reconcile_loop.change_interval(minutes=SETTINGS.sync_interval_minutes)

    def _lock_for(self, user_id: int) -> asyncio.Lock:
        lock = self._user_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[user_id] = lock
        return lock

    async def _resolve_objects(self) -> None:
        self.public_guild = self.bot.get_guild(IDS.PUBLIC_GUILD_ID)
        self.private_guild = self.bot.get_guild(IDS.PRIVATE_GUILD_ID)

        if not self.public_guild:
            raise RuntimeError(f"Bot is not in PUBLIC guild {IDS.PUBLIC_GUILD_ID}")
        if not self.private_guild:
            raise RuntimeError(f"Bot is not in PRIVATE guild {IDS.PRIVATE_GUILD_ID}")

        self.public_role_sh = self.public_guild.get_role(IDS.PUBLIC_ROLE_SH_ID)
        self.public_role_fun = self.public_guild.get_role(IDS.PUBLIC_ROLE_FUN_SH_ID)
        self.private_role_sh = self.private_guild.get_role(IDS.PRIVATE_ROLE_SH_ID)

        if not self.public_role_sh:
            raise RuntimeError(f"PUBLIC_ROLE_SH_ID not found: {IDS.PUBLIC_ROLE_SH_ID}")
        if not self.public_role_fun:
            raise RuntimeError(f"PUBLIC_ROLE_FUN_SH_ID not found: {IDS.PUBLIC_ROLE_FUN_SH_ID}")
        if not self.private_role_sh:
            raise RuntimeError(f"PRIVATE_ROLE_SH_ID not found: {IDS.PRIVATE_ROLE_SH_ID}")

    async def _chunk_members_once(self) -> None:
        """
        Helps populate member cache so role.members is more complete.
        """
        assert self.public_guild and self.private_guild
        try:
            await self.public_guild.chunk(cache=True)
        except Exception:
            log.exception("Failed to chunk public guild members (continuing).")
        try:
            await self.private_guild.chunk(cache=True)
        except Exception:
            log.exception("Failed to chunk private guild members (continuing).")

    async def _private_has_sh(self, user_id: int) -> bool:
        """
        True if user is in the private guild AND has the private SH role.
        If user is not found (left/kicked/banned) -> False.
        """
        assert self.private_guild and self.private_role_sh

        member = self.private_guild.get_member(user_id)
        if member is None:
            try:
                member = await self.private_guild.fetch_member(user_id)
            except discord.NotFound:
                return False
            except discord.Forbidden:
                log.warning("No permission to fetch_member in private guild.")
                return False
            except discord.HTTPException:
                log.exception("HTTP error while fetch_member(private).")
                return False

        return any(r.id == self.private_role_sh.id for r in member.roles)

    async def _get_public_member(self, user_id: int) -> Optional[discord.Member]:
        assert self.public_guild
        member = self.public_guild.get_member(user_id)
        if member is None:
            try:
                member = await self.public_guild.fetch_member(user_id)
            except discord.NotFound:
                return None
            except discord.Forbidden:
                log.warning("No permission to fetch_member in public guild.")
                return None
            except discord.HTTPException:
                log.exception("HTTP error while fetch_member(public).")
                return None
        return member

    async def _apply_public_roles(self, member: discord.Member, want_sh: bool, reason: str) -> bool:
        """
        Enforces desired public role state.
        Returns True if changes were made.
        """
        assert self.public_role_sh and self.public_role_fun

        has_sh = any(r.id == self.public_role_sh.id for r in member.roles)
        has_fun = any(r.id == self.public_role_fun.id for r in member.roles)

        to_add: list[discord.Role] = []
        to_remove: list[discord.Role] = []

        if want_sh:
            if not has_sh:
                to_add.append(self.public_role_sh)
            if has_fun:
                to_remove.append(self.public_role_fun)
        else:
            if has_sh:
                to_remove.append(self.public_role_sh)
            if not has_fun:
                to_add.append(self.public_role_fun)

        if not to_add and not to_remove:
            return False

        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason=reason)
            if to_add:
                await member.add_roles(*to_add, reason=reason)
            return True
        except discord.Forbidden:
            log.error(
                "Forbidden while editing roles for %s (%s). Check Manage Roles and role hierarchy.",
                member, member.id
            )
            return False
        except discord.HTTPException:
            log.exception("HTTP error while editing roles for %s (%s).", member, member.id)
            return False

    async def sync_user(self, user_id: int, *, force_private_absent: bool = False, source: str = "") -> bool:
        """
        Sync one user from private -> public.
        Returns True if public roles changed.
        """
        if not self.public_guild:
            await self._resolve_objects()

        async with self._lock_for(user_id):
            want_sh = False if force_private_absent else await self._private_has_sh(user_id)

            pub_member = await self._get_public_member(user_id)
            if pub_member is None:
                return False

            reason = f"RoleSync ({source}): private SH={'YES' if want_sh else 'NO'}"
            return await self._apply_public_roles(pub_member, want_sh, reason=reason)

    # -------- Events --------

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._ready_once:
            return
        self._ready_once = True

        await self._resolve_objects()
        await self._chunk_members_once()

        if not self.reconcile_loop.is_running():
            self.reconcile_loop.start()

        asyncio.create_task(self.reconcile_once(source="startup"))

        try:
            await self.bot.tree.sync()
        except Exception:
            log.exception("Failed to sync app commands (continuing).")

        log.info("RoleSync ready. Public=%s Private=%s", self.public_guild, self.private_guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        # Track ONLY private guild role change for private SH role
        if after.guild.id != IDS.PRIVATE_GUILD_ID:
            return

        before_has = any(r.id == IDS.PRIVATE_ROLE_SH_ID for r in before.roles)
        after_has = any(r.id == IDS.PRIVATE_ROLE_SH_ID for r in after.roles)

        if before_has != after_has:
            await self.sync_user(after.id, source="private_role_update")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        # Left/kicked from private -> treat as no SH in private
        if member.guild.id != IDS.PRIVATE_GUILD_ID:
            return
        await self.sync_user(member.id, force_private_absent=True, source="private_member_remove")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if guild.id != IDS.PRIVATE_GUILD_ID:
            return
        await self.sync_user(user.id, force_private_absent=True, source="private_member_ban")

    # -------- Reconcile loop --------

    @tasks.loop(minutes=10)
    async def reconcile_loop(self) -> None:
        await self.reconcile_once(source="periodic")

    async def reconcile_once(self, *, source: str) -> None:
        """
        Periodically reconcile all candidates in the public guild:
        anyone who currently has either PUBLIC SH or PUBLIC FUN SH.
        """
        if not self.public_guild:
            await self._resolve_objects()
        assert self.public_role_sh and self.public_role_fun and self.public_guild

        candidates = {m.id for m in self.public_role_sh.members} | {m.id for m in self.public_role_fun.members}
        if not candidates:
            return

        changed = 0
        for uid in candidates:
            try:
                did = await self.sync_user(uid, source=f"reconcile:{source}")
                if did:
                    changed += 1
            except Exception:
                log.exception("Unexpected error while reconciling user %s", uid)

        log.info("Reconcile(%s): candidates=%d changed=%d", source, len(candidates), changed)

    @reconcile_loop.before_loop
    async def _before_reconcile_loop(self) -> None:
        await self.bot.wait_until_ready()

    # -------- Slash commands --------

    @app_commands.command(
        name="sync",
        description="Синхронизировать роли пользователя в паблике по роли SH в приватке",
    )
    @app_commands.describe(user="Кого синхронизировать")
    async def sync_cmd(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Нет прав (нужно Manage Roles).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        changed = await self.sync_user(user.id, source=f"manual_by:{interaction.user.id}")
        await interaction.followup.send(
            f"Готово. Пользователь: {user.mention}. Изменения: {'ДА' if changed else 'НЕТ'}.",
            ephemeral=True
        )

    @app_commands.command(
        name="syncall",
        description="Запустить сверку всех кандидатов (у кого SH/FUN SH в паблике)",
    )
    async def syncall_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Нет прав (нужно Manage Roles).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.reconcile_once(source=f"manual_all_by:{interaction.user.id}")
        await interaction.followup.send("Сверка выполнена (подробности в логах).", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RoleSync(bot))
