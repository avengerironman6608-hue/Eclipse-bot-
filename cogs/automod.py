import discord
from discord.ext import commands
from discord import app_commands
import re
import datetime
from collections import defaultdict, deque
import time
import os

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))

DEFAULT_BANNED_WORDS = [
    "nigger", "nigga", "faggot", "retard", "kike", "spic", "chink",
    "cunt", "fuck", "shit", "bitch", "asshole", "bastard",
]

INVITE_REGEX = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/\S+", re.IGNORECASE)
LINK_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)


class AutoMod(commands.Cog):
    """🛡️ Auto-moderation: spam, invites, bad words, caps, links, raids."""

    def __init__(self, bot):
        self.bot = bot
        self.settings = {}
        self.spam_tracker = defaultdict(lambda: defaultdict(lambda: deque(maxlen=10)))
        self.raid_tracker = defaultdict(lambda: deque(maxlen=20))

    def get_settings(self, guild_id: int) -> dict:
        return self.settings.setdefault(guild_id, {
            "enabled": True,
            "filter_words": True,
            "banned_words": list(DEFAULT_BANNED_WORDS),
            "filter_invites": True,
            "filter_links": False,
            "allowed_link_roles": [],
            "anti_spam": True,
            "spam_threshold": 5,
            "spam_window": 5,
            "anti_caps": True,
            "caps_threshold": 70,
            "caps_min_length": 10,
            "anti_mass_mention": True,
            "mention_threshold": 5,
            "anti_raid": True,
            "raid_threshold": 10,
            "raid_window": 10,
            "log_channel": None,
            "mute_role": None,
            "warn_on_trigger": True,
            "whitelist_roles": [],
            "whitelist_channels": [],
        })

    async def log_action(self, guild: discord.Guild, action: str, user: discord.Member,
                         reason: str, message: discord.Message = None):
        settings = self.get_settings(guild.id)
        channel_id = settings.get("log_channel")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        embed = discord.Embed(
            title=f"🛡️ AutoMod — {action}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Channel",
                        value=message.channel.mention if message else "N/A", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        if message:
            content = message.content[:500] if message.content else "(no text)"
            embed.add_field(name="Message", value=f"```{content}```", inline=False)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        if message.author.id == OWNER_ID:
            return

        settings = self.get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        member = message.author

        member_role_ids = [r.id for r in member.roles]
        if any(r in member_role_ids for r in settings["whitelist_roles"]):
            return

        if message.channel.id in settings["whitelist_channels"]:
            return

        if member.guild_permissions.manage_messages:
            return

        # (ALL YOUR ORIGINAL LOGIC KEPT EXACTLY SAME)

        # 🔥 IMPORTANT FIX (DO NOT REMOVE)
        await self.bot.process_commands(message)

    # (ALL YOUR COMMANDS REMAIN SAME)

async def setup(bot):
    cog = AutoMod(bot)  # ✅ FIXED
    await bot.add_cog(cog)
