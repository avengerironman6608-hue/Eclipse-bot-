import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import os

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))


def is_owner_protected(user_id: int) -> bool:
    return user_id == OWNER_ID


class Moderation(commands.Cog):
    """🔨 Full moderation suite — ban, kick, mute, warn, purge, slowmode & more."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> {user_id: [warnings]}
        self.warnings = {}

    # ─── Helper ────────────────────────────────────────────────────────────────

    def _get_warnings(self, guild_id, user_id):
        return self.warnings.get(guild_id, {}).get(user_id, [])

    def _add_warning(self, guild_id, user_id, reason, moderator):
        self.warnings.setdefault(guild_id, {}).setdefault(user_id, [])
        self.warnings[guild_id][user_id].append({
            "reason": reason,
            "moderator": str(moderator),
            "time": datetime.datetime.utcnow().isoformat()
        })
        return len(self.warnings[guild_id][user_id])

    async def _mod_embed(self, action, target, moderator, reason, color=discord.Color.red()):
        embed = discord.Embed(
            title=f"🔨 {action}",
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} (`{target.id}`)", inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        embed.set_footer(text="Eclipse Bot Moderation")
        return embed

    # ─── Ban ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = None, delete_days: int = 0):
        if is_owner_protected(member.id):
            await interaction.response.send_message(
                "❌ You cannot ban the bot owner.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
            embed = await self._mod_embed("Member Banned", member, interaction.user, reason)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban that member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user by ID.")
    @app_commands.describe(user_id="User ID to unban", reason="Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            embed = discord.Embed(
                title="✅ User Unbanned",
                description=f"{user.mention} has been unbanned.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)

    # ─── Kick ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if is_owner_protected(member.id):
            await interaction.response.send_message(
                "❌ You cannot kick the bot owner.", ephemeral=True)
            return
        try:
            await member.kick(reason=reason)
            embed = await self._mod_embed("Member Kicked", member, interaction.user, reason,
                                          discord.Color.orange())
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick that member.", ephemeral=True)

    # ─── Timeout (Mute) ────────────────────────────────────────────────────────

    @app_commands.command(name="timeout", description="Timeout (mute) a member.")
    @app_commands.describe(member="Member to timeout", minutes="Duration in minutes", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                      minutes: int = 10, reason: str = None):
        if is_owner_protected(member.id):
            await interaction.response.send_message(
                "❌ You cannot timeout the bot owner.", ephemeral=True)
            return
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        try:
            await member.timeout(until, reason=reason)
            embed = await self._mod_embed(f"Member Timed Out ({minutes}m)", member, interaction.user,
                                          reason, discord.Color.yellow())
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout that member.", ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove timeout from a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None)
            embed = discord.Embed(
                title="✅ Timeout Removed",
                description=f"{member.mention}'s timeout has been removed.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to remove that timeout.", ephemeral=True)

    # ─── Warn ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if is_owner_protected(member.id):
            await interaction.response.send_message(
                "❌ You cannot warn the bot owner.", ephemeral=True)
            return
        count = self._add_warning(interaction.guild_id, member.id, reason, interaction.user)
        embed = await self._mod_embed(f"Member Warned (Total: {count})", member, interaction.user,
                                      reason, discord.Color.yellow())
        await interaction.response.send_message(embed=embed)

        # Auto-escalate
        if count >= 5:
            try:
                await member.ban(reason="Auto-ban: 5 warnings reached")
                await interaction.followup.send(
                    f"🔨 {member.mention} has been **auto-banned** for reaching 5 warnings.")
            except discord.Forbidden:
                pass
        elif count >= 3:
            until = discord.utils.utcnow() + datetime.timedelta(hours=1)
            try:
                await member.timeout(until, reason="Auto-timeout: 3 warnings reached")
                await interaction.followup.send(
                    f"⏳ {member.mention} has been **auto-timed out** for 1 hour (3 warnings).")
            except discord.Forbidden:
                pass

    @app_commands.command(name="warnings", description="View warnings for a member.")
    async def warnings_cmd(self, interaction: discord.Interaction, member: discord.Member):
        warns = self._get_warnings(interaction.guild_id, member.id)
        if not warns:
            await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.orange())
        for i, w in enumerate(warns, 1):
            embed.add_field(
                name=f"#{i} — {w['time'][:10]}",
                value=f"**Reason:** {w['reason']}\n**By:** {w['moderator']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        self.warnings.get(interaction.guild_id, {}).pop(member.id, None)
        await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}.")

    # ─── Purge ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="purge", description="Bulk delete messages.")
    @app_commands.describe(amount="Number of messages to delete (1–200)",
                           member="Only delete messages from this member")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int,
                    member: discord.Member = None):
        amount = min(amount, 200)
        await interaction.response.defer(ephemeral=True)
        if member:
            def check(m): return m.author == member
            deleted = await interaction.channel.purge(limit=amount, check=check)
        else:
            deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)

    # ─── Slowmode ──────────────────────────────────────────────────────────────

    @app_commands.command(name="slowmode", description="Set slowmode for the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = f"⏱️ Slowmode set to **{seconds}s**." if seconds else "⏱️ Slowmode **disabled**."
        await interaction.response.send_message(msg)

    # ─── Lock/Unlock ───────────────────────────────────────────────────────────

    @app_commands.command(name="lock", description="Lock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Channel **locked**.")

    @app_commands.command(name="unlock", description="Unlock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Channel **unlocked**.")

    # ─── Nick ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="nick", description="Change a member's nickname.")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member,
                   nickname: str = None):
        try:
            await member.edit(nick=nickname)
            await interaction.response.send_message(f"✏️ Nickname updated for {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I can't change that member's nickname.", ephemeral=True)

    # ─── Role Management ───────────────────────────────────────────────────────

    @app_commands.command(name="addrole", description="Add a role to a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def addrole(self, interaction: discord.Interaction, member: discord.Member,
                      role: discord.Role):
        try:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{role.name}** to {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to add that role.", ephemeral=True)

    @app_commands.command(name="removerole", description="Remove a role from a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(self, interaction: discord.Interaction, member: discord.Member,
                         role: discord.Role):
        try:
            await member.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{role.name}** from {member.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to remove that role.", ephemeral=True)

    # ─── Softban ───────────────────────────────────────────────────────────────

    @app_commands.command(name="softban", description="Ban and immediately unban a member (clears messages).")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member,
                      reason: str = None):
        if is_owner_protected(member.id):
            await interaction.response.send_message("❌ You cannot softban the bot owner.", ephemeral=True)
            return
        try:
            await member.ban(reason=f"Softban: {reason}", delete_message_days=1)
            await interaction.guild.unban(member, reason="Softban unban")
            embed = await self._mod_embed("Member Softbanned", member, interaction.user, reason,
                                          discord.Color.orange())
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to softban that member.", ephemeral=True)

    # ─── Error Handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ You don't have permission to use this command.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
