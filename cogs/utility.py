import discord
from discord.ext import commands
from discord import app_commands
import datetime
import platform
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class Utility(commands.Cog):
    """🔧 Utility commands."""

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()
        self.afk_users = {}  # ✅ AFK storage

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = (discord.Color.green() if latency < 100
                 else discord.Color.yellow() if latency < 200
                 else discord.Color.red())
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="Latency", value=f"{latency}ms")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="View Eclipse Bot information.")
    async def botinfo(self, interaction: discord.Interaction):
        uptime = datetime.datetime.utcnow() - self.start_time
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        embed = discord.Embed(
            title="🌑 Eclipse Bot Info",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Bot", value=str(self.bot.user), inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(
            name="Users",
            value=str(sum(g.member_count for g in self.bot.guilds if g.member_count)),
            inline=True)
        embed.add_field(name="Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.set_footer(text="Eclipse Bot — Your all-in-one companion 🌑")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="embed", description="Send a custom embed message.")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g. ff00ff)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_cmd(self, interaction: discord.Interaction, title: str,
                        description: str, color: str = "7b2fff"):
        try:
            color_int = int(color.lstrip("#"), 16)
        except ValueError:
            color_int = 0x7b2fff
        embed = discord.Embed(
            title=title, description=description, color=color_int,
            timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        await interaction.response.send_message("✅ Embed sent!", ephemeral=True)
        await interaction.channel.send(embed=embed)

    @app_commands.command(name="announce", description="Send an announcement.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction,
                       channel: discord.TextChannel, message: str,
                       ping_everyone: bool = False):
        content = "@everyone\n" if ping_everyone else ""
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"By {interaction.user.display_name}")
        try:
            await channel.send(content=content, embed=embed)
            await interaction.response.send_message(
                f"✅ Announcement sent to {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to send in that channel.", ephemeral=True)

    # ================= AFK COMMAND =================
    @app_commands.command(name="afk", description="Set your AFK status")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        self.afk_users[interaction.user.id] = {
            "reason": reason,
            "time": datetime.datetime.utcnow()
        }
        await interaction.response.send_message(f"💤 You are now AFK: {reason}")

    # ================= MESSAGE LISTENER =================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # ✅ Remove AFK when user speaks
        if message.author.id in self.afk_users:
            del self.afk_users[message.author.id]
            await message.channel.send(f"👋 Welcome back {message.author.mention}, AFK removed.")

        # ✅ Check mentions
        for user in message.mentions:
            if user.id in self.afk_users:
                data = self.afk_users[user.id]
                await message.channel.send(
                    f"💤 {user.name} is AFK: {data['reason']}"
                )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        if not hasattr(self.bot, '_sniped'):
            self.bot._sniped = {}
        self.bot._sniped[message.channel.id] = {
            "content": message.content,
            "author": str(message.author),
            "avatar": message.author.display_avatar.url,
            "time": datetime.datetime.utcnow(),
        }

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ You don't have permission to use this command.", ephemeral=True)


# ================= SETUP =================
async def setup(bot):
    cog = Utility(bot)
    await bot.add_cog(cog)

    # ✅ FIX: Ensure commands are added to tree
    for command in cog.walk_app_commands():
        bot.tree.add_command(command)
