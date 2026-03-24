import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import datetime
from collections import defaultdict
import time


# ── XP math ───────────────────────────────────────────────────────────────────
def xp_for_level(level: int) -> int:
    return math.floor(100 * (level ** 1.5))


def level_from_xp(xp: int) -> int:
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def xp_for_exact_level(level: int) -> int:
    """Returns the minimum XP needed to BE at exactly this level."""
    return xp_for_level(level)


# ── Cog ───────────────────────────────────────────────────────────────────────
class Leveling(commands.Cog):
    """📈 XP & Leveling system — rank cards, leaderboard, level roles, level channel display."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {guild_id: {user_id: {"xp": int, "messages": int}}}
        self.data = defaultdict(lambda: defaultdict(lambda: {"xp": 0, "messages": 0}))
        self.cooldowns: dict = defaultdict(dict)
        # {guild_id: {level: role_id}}
        self.level_roles: dict = defaultdict(dict)
        # {guild_id: channel_id} — where level-up announcements go
        self.announce_channels: dict = {}
        # {guild_id: channel_id} — where /levels leaderboard is always shown
        self.levels_display_channel: dict = {}
        # {guild_id: message_id} — pinned leaderboard message to edit in place
        self.levels_display_message: dict = {}

    def get_user_data(self, guild_id: int, user_id: int) -> dict:
        return self.data[guild_id][user_id]

    def get_rank(self, guild_id: int, user_id: int) -> int:
        sorted_users = sorted(
            self.data[guild_id].items(), key=lambda x: x[1]["xp"], reverse=True)
        for i, (uid, _) in enumerate(sorted_users, 1):
            if uid == user_id:
                return i
        return len(sorted_users) + 1

    # ── XP gain on message ────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        guild_id = message.guild.id
        user_id = message.author.id

        now = time.time()
        last = self.cooldowns[guild_id].get(user_id, 0)
        if now - last < 60:
            return
        self.cooldowns[guild_id][user_id] = now

        user = self.get_user_data(guild_id, user_id)
        old_level = level_from_xp(user["xp"])
        xp_gain = random.randint(15, 25)
        user["xp"] += xp_gain
        user["messages"] += 1
        new_level = level_from_xp(user["xp"])

        if new_level > old_level:
            await self._on_level_up(message, new_level)

        # Update the live levels display channel if set
        await self._refresh_levels_display(message.guild)

    async def _on_level_up(self, message: discord.Message, new_level: int):
        guild = message.guild
        member = message.author

        # Assign level role if configured
        role_id = self.level_roles[guild.id].get(new_level)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Level {new_level} reached")
                except discord.Forbidden:
                    pass

        # Send level-up announcement
        channel_id = self.announce_channels.get(guild.id)
        channel = guild.get_channel(channel_id) if channel_id else message.channel
        if not channel:
            channel = message.channel

        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"{member.mention} reached **Level {new_level}**! 🌑",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Next Level",
            value=f"Needs **{xp_for_level(new_level + 1)}** total XP",
            inline=True)
        embed.set_footer(text="Eclipse Bot Leveling 🌑")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    async def _refresh_levels_display(self, guild: discord.Guild):
        """Update the pinned leaderboard message in the levels display channel."""
        channel_id = self.levels_display_channel.get(guild.id)
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = self._build_leaderboard_embed(guild)
        msg_id = self.levels_display_message.get(guild.id)

        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return
            except (discord.NotFound, discord.HTTPException):
                pass

        # Send fresh message and store its ID
        try:
            msg = await channel.send(embed=embed)
            self.levels_display_message[guild.id] = msg.id
        except discord.Forbidden:
            pass

    def _build_leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        guild_data = self.data[guild.id]
        embed = discord.Embed(
            title="🏆 Server Levels",
            description="Live leaderboard — updates as members chat!",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        if not guild_data:
            embed.add_field(name="No data yet", value="Start chatting to earn XP!", inline=False)
            embed.set_footer(text="Eclipse Leveling 🌑")
            return embed

        sorted_users = sorted(
            guild_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:15]
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 12

        lines = []
        for i, (uid, udata) in enumerate(sorted_users):
            member = guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lvl = level_from_xp(udata["xp"])
            lines.append(f"{medals[i]} **#{i+1}** {name} — Lvl **{lvl}** | **{udata['xp']}** XP")

        embed.description = "\n".join(lines) or "No XP data yet."
        embed.set_footer(text="Eclipse Leveling 🌑 | Auto-updates on activity")
        return embed

    # ── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="View your or another member's rank card.")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        user = self.get_user_data(interaction.guild_id, member.id)
        xp = user["xp"]
        level = level_from_xp(xp)
        rank = self.get_rank(interaction.guild_id, member.id)
        current_xp = xp - xp_for_level(level)
        needed_xp = xp_for_level(level + 1) - xp_for_level(level)
        progress = int((current_xp / needed_xp) * 20) if needed_xp else 20
        bar = "█" * progress + "░" * (20 - progress)

        embed = discord.Embed(color=discord.Color.purple())
        embed.set_author(
            name=f"{member.display_name}'s Rank",
            icon_url=member.display_avatar.url)
        embed.add_field(name="🏆 Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="⭐ Level", value=str(level), inline=True)
        embed.add_field(name="✉️ Messages", value=str(user["messages"]), inline=True)
        embed.add_field(
            name="📊 Progress",
            value=f"`{bar}` {current_xp}/{needed_xp} XP",
            inline=False)
        embed.add_field(name="🔢 Total XP", value=str(xp), inline=True)
        embed.set_footer(text="Eclipse Leveling 🌑")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the server XP leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        embed = self._build_leaderboard_embed(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="setlevelschannel",
        description="Set a channel where a live levels leaderboard is always displayed.")
    @app_commands.describe(channel="Channel to post and auto-update the levels board")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlevelschannel(
            self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.levels_display_channel[interaction.guild_id] = channel.id
        # Clear old message reference so a fresh one is posted
        self.levels_display_message.pop(interaction.guild_id, None)
        await interaction.response.send_message(
            f"✅ Live levels leaderboard will be displayed in {channel.mention}. "
            f"It updates automatically as members earn XP!")
        # Post immediately
        await self._refresh_levels_display(interaction.guild)

    @app_commands.command(
        name="setlevel",
        description="Set a member's level directly (Admin/Owner only).")
    @app_commands.describe(
        member="Member to update",
        level="Level to set them to")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevel(
            self, interaction: discord.Interaction,
            member: discord.Member, level: int):
        if level < 0:
            await interaction.response.send_message(
                "❌ Level cannot be negative.", ephemeral=True)
            return
        # Set XP to the minimum needed for that level
        new_xp = xp_for_exact_level(level)
        user = self.get_user_data(interaction.guild_id, member.id)
        user["xp"] = new_xp

        embed = discord.Embed(
            title="⭐ Level Set",
            description=f"{member.mention} has been set to **Level {level}**.",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="New XP", value=str(new_xp), inline=True)
        embed.add_field(name="Set by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Eclipse Leveling 🌑")
        await interaction.response.send_message(embed=embed)

        # Award level role if configured
        role_id = self.level_roles[interaction.guild_id].get(level)
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Level set to {level} by admin")
                except discord.Forbidden:
                    pass

        await self._refresh_levels_display(interaction.guild)

    @app_commands.command(name="setxp", description="Set a member's XP directly (Admin only).")
    @app_commands.describe(member="Member to update", xp="XP value to set")
    @app_commands.checks.has_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        self.get_user_data(interaction.guild_id, member.id)["xp"] = max(0, xp)
        await interaction.response.send_message(
            f"✅ Set {member.mention}'s XP to **{max(0, xp)}** "
            f"(Level **{level_from_xp(max(0, xp))}**).")
        await self._refresh_levels_display(interaction.guild)

    @app_commands.command(name="addxp", description="Add XP to a member (Admin only).")
    @app_commands.describe(member="Member to reward", xp="Amount of XP to add")
    @app_commands.checks.has_permissions(administrator=True)
    async def addxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        user = self.get_user_data(interaction.guild_id, member.id)
        user["xp"] += xp
        await interaction.response.send_message(
            f"✅ Added **{xp}** XP to {member.mention}. "
            f"Now Level **{level_from_xp(user['xp'])}**.")
        await self._refresh_levels_display(interaction.guild)

    @app_commands.command(
        name="levelrole",
        description="Assign a role to be given when a member reaches a specific level.")
    @app_commands.describe(level="Level that triggers the role", role="Role to assign")
    @app_commands.checks.has_permissions(administrator=True)
    async def levelrole(
            self, interaction: discord.Interaction, level: int, role: discord.Role):
        self.level_roles[interaction.guild_id][level] = role.id
        await interaction.response.send_message(
            f"✅ {role.mention} will be awarded when members reach Level **{level}**.")

    @app_commands.command(
        name="levelchannel",
        description="Set the channel for level-up announcement messages.")
    @app_commands.describe(channel="Channel for level-up pings")
    @app_commands.checks.has_permissions(administrator=True)
    async def levelchannel(
            self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.announce_channels[interaction.guild_id] = channel.id
        await interaction.response.send_message(
            f"✅ Level-up announcements will be sent to {channel.mention}.")

    @app_commands.command(name="resetxp", description="Reset a member's XP (Admin only).")
    @app_commands.describe(member="Member to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetxp(self, interaction: discord.Interaction, member: discord.Member):
        self.data[interaction.guild_id][member.id] = {"xp": 0, "messages": 0}
        await interaction.response.send_message(f"✅ Reset {member.mention}'s XP to 0.")
        await self._refresh_levels_display(interaction.guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
