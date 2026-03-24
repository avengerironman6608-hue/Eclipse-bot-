import discord
from discord.ext import commands
from discord import app_commands
import random
import math
import datetime
from collections import defaultdict
import time


def xp_for_level(level: int) -> int:
    return math.floor(100 * (level ** 1.5))


def level_from_xp(xp: int) -> int:
    level = 0
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


class Leveling(commands.Cog):
    """📈 XP & Leveling system — rank cards, leaderboard, level roles."""

    def __init__(self, bot):
        self.bot = bot
        self.data = defaultdict(lambda: defaultdict(lambda: {"xp": 0, "messages": 0}))
        self.cooldowns = defaultdict(dict)
        self.level_roles = defaultdict(dict)
        self.announce_channels = {}

    def get_user_data(self, guild_id, user_id):
        return self.data[guild_id][user_id]

    def get_rank(self, guild_id, user_id):
        sorted_users = sorted(
            self.data[guild_id].items(), key=lambda x: x[1]["xp"], reverse=True)
        for i, (uid, _) in enumerate(sorted_users, 1):
            if uid == user_id:
                return i
        return len(sorted_users) + 1

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

    async def _on_level_up(self, message: discord.Message, new_level: int):
        guild = message.guild
        member = message.author

        role_id = self.level_roles[guild.id].get(new_level)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Level {new_level} reached")
                except discord.Forbidden:
                    pass

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
        next_xp = xp_for_level(new_level + 1)
        embed.set_footer(text=f"Next level at {next_xp} XP")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="rank", description="View your or another member's rank card.")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        user = self.get_user_data(interaction.guild_id, member.id)
        xp = user["xp"]
        level = level_from_xp(xp)
        rank = self.get_rank(interaction.guild_id, member.id)
        current_xp = xp - xp_for_level(level)
        needed_xp = xp_for_level(level + 1) - xp_for_level(level)
        progress = int((current_xp / needed_xp) * 20) if needed_xp else 0
        bar = "█" * progress + "░" * (20 - progress)

        embed = discord.Embed(color=discord.Color.purple())
        embed.set_author(name=f"{member.display_name}'s Rank Card",
                         icon_url=member.display_avatar.url)
        embed.add_field(name="🏆 Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="⭐ Level", value=str(level), inline=True)
        embed.add_field(name="✉️ Messages", value=str(user["messages"]), inline=True)
        embed.add_field(name="📊 XP Progress",
                        value=f"`{bar}` {current_xp}/{needed_xp}", inline=False)
        embed.add_field(name="🔢 Total XP", value=str(xp), inline=True)
        embed.set_footer(text="Eclipse Bot Leveling")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the server XP leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        guild_data = self.data[interaction.guild_id]
        if not guild_data:
            await interaction.response.send_message("No XP data yet!", ephemeral=True)
            return
        sorted_users = sorted(
            guild_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
        embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        for i, (uid, udata) in enumerate(sorted_users):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lvl = level_from_xp(udata["xp"])
            embed.add_field(
                name=f"{medals[i]} #{i+1} — {name}",
                value=f"Level **{lvl}** | **{udata['xp']}** XP",
                inline=False
            )
        embed.set_footer(text="Eclipse Bot Leveling System")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setxp", description="Set a member's XP (Admin only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        self.get_user_data(interaction.guild_id, member.id)["xp"] = max(0, xp)
        await interaction.response.send_message(f"✅ Set {member.mention}'s XP to **{xp}**.")

    @app_commands.command(name="addxp", description="Add XP to a member (Admin only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def addxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        self.get_user_data(interaction.guild_id, member.id)["xp"] += xp
        await interaction.response.send_message(f"✅ Added **{xp}** XP to {member.mention}.")

    @app_commands.command(name="levelrole",
                          description="Assign a role to be given at a specific level.")
    @app_commands.checks.has_permissions(administrator=True)
    async def levelrole(self, interaction: discord.Interaction, level: int, role: discord.Role):
        self.level_roles[interaction.guild_id][level] = role.id
        await interaction.response.send_message(
            f"✅ {role.mention} will be awarded at Level **{level}**.")

    @app_commands.command(name="levelchannel",
                          description="Set the channel for level-up announcements.")
    @app_commands.checks.has_permissions(administrator=True)
    async def levelchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.announce_channels[interaction.guild_id] = channel.id
        await interaction.response.send_message(
            f"✅ Level-up announcements will be sent to {channel.mention}.")

    @app_commands.command(name="resetxp", description="Reset a member's XP (Admin only).")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetxp(self, interaction: discord.Interaction, member: discord.Member):
        self.data[interaction.guild_id][member.id] = {"xp": 0, "messages": 0}
        await interaction.response.send_message(f"✅ Reset {member.mention}'s XP.")


async def setup(bot):
    await bot.add_cog(Leveling(bot))
