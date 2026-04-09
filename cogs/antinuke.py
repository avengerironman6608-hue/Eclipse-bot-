import discord
from discord.ext import commands
from discord import app_commands
import datetime
from collections import defaultdict, deque
import asyncio
import os

OWNER_ID = int(os.getenv("OWNER_ID", "0"))


class AntiNuke(commands.Cog):
    """🛡️ Anti-Nuke — protects against mass bans, kicks, channel/role deletions."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> settings
        self.settings = {}
        # Action trackers: guild_id -> user_id -> deque of timestamps
        self.ban_tracker    = defaultdict(lambda: defaultdict(lambda: deque(maxlen=20)))
        self.kick_tracker   = defaultdict(lambda: defaultdict(lambda: deque(maxlen=20)))
        self.ch_del_tracker = defaultdict(lambda: defaultdict(lambda: deque(maxlen=20)))
        self.role_del_tracker = defaultdict(lambda: defaultdict(lambda: deque(maxlen=20)))
        self.webhook_tracker  = defaultdict(lambda: defaultdict(lambda: deque(maxlen=20)))
        # Punished users (to avoid double punishment): set of (guild_id, user_id)
        self.punished = set()
        # Whitelist: guild_id -> set of user_ids
        self.whitelist = defaultdict(set)

    def get_settings(self, gid) -> dict:
        return self.settings.setdefault(gid, {
            "enabled": True,
            "log_channel": None,
            # Thresholds (actions in 10 seconds)
            "ban_threshold":     3,
            "kick_threshold":    3,
            "ch_del_threshold":  2,
            "role_del_threshold": 2,
            "webhook_threshold": 2,
            # Punishment: "ban" | "kick" | "strip" (strip admin roles)
            "punishment": "strip",
        })

    def is_whitelisted(self, gid, uid) -> bool:
        if uid == OWNER_ID: return True
        return uid in self.whitelist[gid]

    async def log(self, guild: discord.Guild, title: str, description: str, color=discord.Color.red()):
        s = self.get_settings(guild.id)
        ch_id = s.get("log_channel")
        if not ch_id: return
        ch = guild.get_channel(ch_id)
        if not ch: return
        embed = discord.Embed(title=f"🚨 Anti-Nuke | {title}", description=description,
                              color=color, timestamp=datetime.datetime.utcnow())
        embed.set_footer(text="Eclipse Anti-Nuke")
        try: await ch.send(embed=embed)
        except Exception: pass

    async def punish(self, guild: discord.Guild, user_id: int, reason: str):
        key = (guild.id, user_id)
        if key in self.punished: return
        self.punished.add(key)

        s = self.get_settings(guild.id)
        punishment = s.get("punishment", "strip")
        member = guild.get_member(user_id)

        await self.log(guild, "Nuke Detected", f"**User:** <@{user_id}>\n**Action:** {reason}\n**Punishment:** {punishment}")

        if not member:
            # Try ban by ID
            try:
                user = await self.bot.fetch_user(user_id)
                await guild.ban(user, reason=f"Anti-Nuke: {reason}")
            except Exception: pass
            return

        if punishment == "ban":
            try: await guild.ban(member, reason=f"Anti-Nuke: {reason}")
            except Exception: pass
        elif punishment == "kick":
            try: await guild.kick(member, reason=f"Anti-Nuke: {reason}")
            except Exception: pass
        elif punishment == "strip":
            # Remove all dangerous roles
            dangerous_perms = ["administrator", "ban_members", "kick_members",
                               "manage_guild", "manage_channels", "manage_roles", "manage_webhooks"]
            roles_to_remove = [
                r for r in member.roles
                if r != guild.default_role
                and any(getattr(r.permissions, p, False) for p in dangerous_perms)
            ]
            try: await member.remove_roles(*roles_to_remove, reason=f"Anti-Nuke: {reason}")
            except Exception: pass
            # Also timeout for 24 hours
            try:
                until = discord.utils.utcnow() + datetime.timedelta(hours=24)
                await member.timeout(until, reason=f"Anti-Nuke: {reason}")
            except Exception: pass

        # Clean up punished after 60s so they can be re-caught if needed
        await asyncio.sleep(60)
        self.punished.discard(key)

    def _check_threshold(self, tracker, gid, uid, threshold, window=10) -> bool:
        import time
        now = time.time()
        dq  = tracker[gid][uid]
        dq.append(now)
        recent = [t for t in dq if now - t <= window]
        return len(recent) >= threshold

    # ── Audit log watchers ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        s = self.get_settings(guild.id)
        if not s["enabled"]: return
        await asyncio.sleep(0.5)  # Wait for audit log
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                mod_id = entry.user.id
                if self.is_whitelisted(guild.id, mod_id): return
                if self._check_threshold(self.ban_tracker, guild.id, mod_id, s["ban_threshold"]):
                    await self.punish(guild, mod_id, f"Mass ban ({s['ban_threshold']} in 10s)")
        except Exception: pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        s = self.get_settings(guild.id)
        if not s["enabled"]: return
        await asyncio.sleep(0.5)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if (datetime.datetime.utcnow() - entry.created_at.replace(tzinfo=None)).total_seconds() > 5:
                    return
                mod_id = entry.user.id
                if self.is_whitelisted(guild.id, mod_id): return
                if self._check_threshold(self.kick_tracker, guild.id, mod_id, s["kick_threshold"]):
                    await self.punish(guild, mod_id, f"Mass kick ({s['kick_threshold']} in 10s)")
        except Exception: pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        s = self.get_settings(guild.id)
        if not s["enabled"]: return
        await asyncio.sleep(0.5)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                mod_id = entry.user.id
                if self.is_whitelisted(guild.id, mod_id): return
                if self._check_threshold(self.ch_del_tracker, guild.id, mod_id, s["ch_del_threshold"]):
                    await self.punish(guild, mod_id, f"Mass channel delete ({s['ch_del_threshold']} in 10s)")
        except Exception: pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        s = self.get_settings(guild.id)
        if not s["enabled"]: return
        await asyncio.sleep(0.5)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                mod_id = entry.user.id
                if self.is_whitelisted(guild.id, mod_id): return
                if self._check_threshold(self.role_del_tracker, guild.id, mod_id, s["role_del_threshold"]):
                    await self.punish(guild, mod_id, f"Mass role delete ({s['role_del_threshold']} in 10s)")
        except Exception: pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = channel.guild
        s = self.get_settings(guild.id)
        if not s["enabled"]: return
        await asyncio.sleep(0.5)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                mod_id = entry.user.id
                if self.is_whitelisted(guild.id, mod_id): return
                if self._check_threshold(self.webhook_tracker, guild.id, mod_id, s["webhook_threshold"]):
                    await self.punish(guild, mod_id, f"Mass webhook creation ({s['webhook_threshold']} in 10s)")
        except Exception: pass

    # ── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(name="antinuke", description="Toggle Anti-Nuke protection on/off.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke(self, interaction: discord.Interaction):
        s = self.get_settings(interaction.guild_id)
        s["enabled"] = not s["enabled"]
        status = "✅ enabled" if s["enabled"] else "❌ disabled"
        await interaction.response.send_message(f"🛡️ Anti-Nuke **{status}**.")

    @app_commands.command(name="antinuke_status", description="View Anti-Nuke settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke_status(self, interaction: discord.Interaction):
        s = self.get_settings(interaction.guild_id)
        wl = self.whitelist[interaction.guild_id]
        e = discord.Embed(title="🛡️ Anti-Nuke Status", color=discord.Color.purple())
        e.add_field(name="Enabled",       value="✅" if s["enabled"] else "❌", inline=True)
        e.add_field(name="Punishment",    value=s["punishment"], inline=True)
        e.add_field(name="Ban Threshold", value=str(s["ban_threshold"]), inline=True)
        e.add_field(name="Kick Threshold",value=str(s["kick_threshold"]), inline=True)
        e.add_field(name="Ch Del Threshold", value=str(s["ch_del_threshold"]), inline=True)
        e.add_field(name="Role Del Threshold",value=str(s["role_del_threshold"]), inline=True)
        e.add_field(name=f"Whitelist ({len(wl)})",
                    value=", ".join(f"<@{u}>" for u in wl) or "None", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="antinuke_set", description="Configure Anti-Nuke settings.")
    @app_commands.describe(setting="Setting to change", value="New value")
    @app_commands.choices(setting=[
        app_commands.Choice(name="punishment (ban/kick/strip)", value="punishment"),
        app_commands.Choice(name="ban_threshold",    value="ban_threshold"),
        app_commands.Choice(name="kick_threshold",   value="kick_threshold"),
        app_commands.Choice(name="ch_del_threshold", value="ch_del_threshold"),
        app_commands.Choice(name="role_del_threshold", value="role_del_threshold"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke_set(self, interaction: discord.Interaction, setting: str, value: str):
        s = self.get_settings(interaction.guild_id)
        if setting == "punishment":
            if value not in ("ban", "kick", "strip"):
                return await interaction.response.send_message("❌ Valid: `ban`, `kick`, `strip`", ephemeral=True)
            s["punishment"] = value
        else:
            try: s[setting] = int(value)
            except ValueError:
                return await interaction.response.send_message("❌ Value must be a number.", ephemeral=True)
        await interaction.response.send_message(f"✅ `{setting}` set to `{value}`.")

    @app_commands.command(name="antinuke_log", description="Set the Anti-Nuke log channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.get_settings(interaction.guild_id)["log_channel"] = channel.id
        await interaction.response.send_message(f"✅ Anti-Nuke logs → {channel.mention}")

    @app_commands.command(name="antinuke_whitelist", description="Whitelist a user from Anti-Nuke actions.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke_whitelist(self, interaction: discord.Interaction, member: discord.Member):
        self.whitelist[interaction.guild_id].add(member.id)
        await interaction.response.send_message(f"✅ {member.mention} whitelisted from Anti-Nuke.")

    @app_commands.command(name="antinuke_unwhitelist", description="Remove a user from the Anti-Nuke whitelist.")
    @app_commands.checks.has_permissions(administrator=True)
    async def antinuke_unwhitelist(self, interaction: discord.Interaction, member: discord.Member):
        self.whitelist[interaction.guild_id].discard(member.id)
        await interaction.response.send_message(f"✅ {member.mention} removed from whitelist.")


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
