import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio


class Moderation(commands.Cog):
    """🔨 Full moderation suite."""

    def __init__(self, bot):
        self.bot = bot
        self.warnings = {}   # guild_id -> {user_id: [warn dicts]}
        self.notes    = {}   # guild_id -> {user_id: [note strings]}

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _warns(self, gid, uid):
        return self.warnings.setdefault(gid, {}).setdefault(uid, [])

    def _add_warn(self, gid, uid, reason, mod):
        self._warns(gid, uid).append({"reason": reason, "mod": str(mod),
                                       "time": datetime.datetime.utcnow().isoformat()})
        return len(self._warns(gid, uid))

    def _embed(self, action, target, mod, reason, color=discord.Color.red()):
        e = discord.Embed(title=f"🔨 {action}", color=color,
                          timestamp=datetime.datetime.utcnow())
        e.add_field(name="User",      value=f"{target.mention} (`{target.id}`)", inline=True)
        e.add_field(name="Moderator", value=mod.mention, inline=True)
        e.add_field(name="Reason",    value=reason or "No reason provided", inline=False)
        e.set_footer(text="Eclipse Moderation")
        return e

    async def _try_dm(self, member, msg):
        try: await member.send(msg)
        except Exception: pass

    # ── Ban ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member.")
    @app_commands.describe(member="Member to ban", reason="Reason", delete_days="Days of messages to delete (0-7)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = None, delete_days: int = 0):
        await self._try_dm(member, f"🔨 You were **banned** from **{interaction.guild.name}**. Reason: {reason or 'None'}")
        await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
        await interaction.response.send_message(embed=self._embed("Member Banned", member, interaction.user, reason))

    @app_commands.command(name="unban", description="Unban a user by ID.")
    @app_commands.describe(user_id="User ID to unban", reason="Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            e = discord.Embed(title="✅ User Unbanned", description=f"{user.mention} has been unbanned.", color=discord.Color.green())
            await interaction.response.send_message(embed=e)
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)

    @app_commands.command(name="softban", description="Ban then immediately unban (clears messages).")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await self._try_dm(member, f"👢 You were **softbanned** from **{interaction.guild.name}**. Reason: {reason or 'None'}")
        await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
        await interaction.guild.unban(member, reason="Softban unban")
        await interaction.response.send_message(embed=self._embed("Member Softbanned", member, interaction.user, reason, discord.Color.orange()))

    @app_commands.command(name="hackban", description="Ban a user by ID (even if not in server).")
    @app_commands.describe(user_id="Discord user ID", reason="Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def hackban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.ban(user, reason=reason)
            e = discord.Embed(title="🔨 User Hackbanned", description=f"`{user}` (`{user.id}`) banned.", color=discord.Color.red())
            await interaction.response.send_message(embed=e)
        except Exception as err:
            await interaction.response.send_message(f"❌ Failed: `{err}`", ephemeral=True)

    # ── Kick ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await self._try_dm(member, f"👢 You were **kicked** from **{interaction.guild.name}**. Reason: {reason or 'None'}")
        await member.kick(reason=reason)
        await interaction.response.send_message(embed=self._embed("Member Kicked", member, interaction.user, reason, discord.Color.orange()))

    # ── Timeout ───────────────────────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Timeout a member.")
    @app_commands.describe(member="Member", minutes="Duration in minutes", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                      minutes: int = 10, reason: str = None):
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await interaction.response.send_message(
            embed=self._embed(f"Timed Out ({minutes}m)", member, interaction.user, reason, discord.Color.yellow()))

    @app_commands.command(name="untimeout", description="Remove a member's timeout.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"✅ Timeout removed for {member.mention}.")

    # ── Warn ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        count = self._add_warn(interaction.guild_id, member.id, reason, interaction.user)
        await self._try_dm(member, f"⚠️ You received a warning in **{interaction.guild.name}**.\nReason: {reason}\nTotal warnings: {count}")
        await interaction.response.send_message(
            embed=self._embed(f"Member Warned (#{count})", member, interaction.user, reason, discord.Color.yellow()))
        if count >= 5:
            await member.ban(reason="Auto-ban: 5 warnings")
            await interaction.followup.send(f"🔨 {member.mention} auto-banned for reaching 5 warnings.")
        elif count >= 3:
            until = discord.utils.utcnow() + datetime.timedelta(hours=1)
            await member.timeout(until, reason="Auto-timeout: 3 warnings")
            await interaction.followup.send(f"⏳ {member.mention} auto-timed out for 1h (3 warnings).")

    @app_commands.command(name="warnings", description="View a member's warnings.")
    async def warnings_cmd(self, interaction: discord.Interaction, member: discord.Member):
        warns = self._warns(interaction.guild_id, member.id)
        if not warns:
            return await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
        e = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.orange())
        for i, w in enumerate(warns, 1):
            e.add_field(name=f"#{i} — {w['time'][:10]}", value=f"**Reason:** {w['reason']}\n**By:** {w['mod']}", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        self.warnings.get(interaction.guild_id, {}).pop(member.id, None)
        await interaction.response.send_message(f"✅ Cleared warnings for {member.mention}.")

    # ── Purge ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Bulk delete messages.")
    @app_commands.describe(amount="Number of messages (1–200)", member="Only delete from this member")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        amount = min(amount, 200)
        check = (lambda m: m.author == member) if member else None
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)

    # ── Lock/Unlock ───────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Lock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.send_messages = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(f"🔒 {ch.mention} **locked**.")

    @app_commands.command(name="unlock", description="Unlock the current channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.send_messages = True
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(f"🔓 {ch.mention} **unlocked**.")

    @app_commands.command(name="slowmode", description="Set channel slowmode.")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 = off)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = f"⏱️ Slowmode set to **{seconds}s**." if seconds else "⏱️ Slowmode **disabled**."
        await interaction.response.send_message(msg)

    @app_commands.command(name="lockdown", description="Lock ALL channels in the server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def lockdown(self, interaction: discord.Interaction, reason: str = "Lockdown"):
        await interaction.response.defer()
        count = 0
        for ch in interaction.guild.text_channels:
            try:
                ow = ch.overwrites_for(interaction.guild.default_role)
                ow.send_messages = False
                await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
                count += 1
            except Exception: pass
        await interaction.followup.send(f"🔒 **Lockdown activated** — {count} channels locked. Reason: {reason}")

    @app_commands.command(name="unlockdown", description="Unlock ALL channels.")
    @app_commands.checks.has_permissions(administrator=True)
    async def unlockdown(self, interaction: discord.Interaction):
        await interaction.response.defer()
        count = 0
        for ch in interaction.guild.text_channels:
            try:
                ow = ch.overwrites_for(interaction.guild.default_role)
                ow.send_messages = True
                await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
                count += 1
            except Exception: pass
        await interaction.followup.send(f"🔓 **Lockdown lifted** — {count} channels unlocked.")

    # ── Nick ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change a member's nickname.")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        await member.edit(nick=nickname)
        await interaction.response.send_message(f"✏️ Nickname {'set to **' + nickname + '**' if nickname else 'cleared'} for {member.mention}.")

    # ── Roles ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="addrole", description="Add a role to a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Added **{role.name}** to {member.mention}.")

    @app_commands.command(name="removerole", description="Remove a role from a member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await interaction.response.send_message(f"✅ Removed **{role.name}** from {member.mention}.")

    @app_commands.command(name="massrole", description="Add a role to ALL members.")
    @app_commands.checks.has_permissions(administrator=True)
    async def massrole(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        count = 0
        for member in interaction.guild.members:
            if role not in member.roles and not member.bot:
                try: await member.add_roles(role); count += 1
                except Exception: pass
        await interaction.followup.send(f"✅ Added **{role.name}** to **{count}** members.")

    # ── Voice ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="deafen", description="Server-deafen a member.")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def deafen(self, interaction: discord.Interaction, member: discord.Member):
        await member.edit(deafen=True)
        await interaction.response.send_message(f"🔇 {member.mention} has been deafened.")

    @app_commands.command(name="undeafen", description="Remove server-deafen from a member.")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def undeafen(self, interaction: discord.Interaction, member: discord.Member):
        await member.edit(deafen=False)
        await interaction.response.send_message(f"🔊 {member.mention} has been undeafened.")

    @app_commands.command(name="movevc", description="Move a member to another voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def movevc(self, interaction: discord.Interaction, member: discord.Member,
                     channel: discord.VoiceChannel):
        if not member.voice:
            return await interaction.response.send_message("❌ That member is not in a VC.", ephemeral=True)
        await member.move_to(channel)
        await interaction.response.send_message(f"✅ Moved {member.mention} to **{channel.name}**.")

    # ── Notes ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="note", description="Add a note to a member (staff-only, not visible to user).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def note(self, interaction: discord.Interaction, member: discord.Member, text: str):
        self.notes.setdefault(interaction.guild_id, {}).setdefault(member.id, []).append(
            {"note": text, "by": str(interaction.user), "time": datetime.datetime.utcnow().isoformat()})
        await interaction.response.send_message(f"📝 Note added for {member.mention}.", ephemeral=True)

    @app_commands.command(name="notes", description="View staff notes for a member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def notes_cmd(self, interaction: discord.Interaction, member: discord.Member):
        notes = self.notes.get(interaction.guild_id, {}).get(member.id, [])
        if not notes:
            return await interaction.response.send_message(f"No notes for {member.mention}.", ephemeral=True)
        e = discord.Embed(title=f"📝 Notes for {member}", color=discord.Color.blurple())
        for i, n in enumerate(notes, 1):
            e.add_field(name=f"#{i} by {n['by']}", value=n["note"], inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── Error handler ─────────────────────────────────────────────────────────
    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
