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

        # Owner is never moderated
        if message.author.id == OWNER_ID:
            return

        settings = self.get_settings(message.guild.id)
        if not settings["enabled"]:
            return

        member = message.author

        # Skip whitelisted roles
        member_role_ids = [r.id for r in member.roles]
        if any(r in member_role_ids for r in settings["whitelist_roles"]):
            return

        # Skip whitelisted channels
        if message.channel.id in settings["whitelist_channels"]:
            return

        # Skip admins/mods
        if member.guild_permissions.manage_messages:
            return

        # ── Spam check ────────────────────────────────────────────────────────
        if settings["anti_spam"]:
            tracker = self.spam_tracker[message.guild.id][member.id]
            now = time.time()
            tracker.append(now)
            window = settings["spam_window"]
            threshold = settings["spam_threshold"]
            recent = [t for t in tracker if now - t <= window]
            if len(recent) >= threshold:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                timeout_until = discord.utils.utcnow() + datetime.timedelta(minutes=5)
                try:
                    await member.timeout(timeout_until, reason="AutoMod: Spam detected")
                except discord.Forbidden:
                    pass
                await self.log_action(message.guild, "Spam Timeout", member,
                                      f"Sent {len(recent)} msgs in {window}s", message)
                try:
                    await member.send(
                        "🛡️ **Eclipse AutoMod:** You were timed out for 5 minutes due to spamming.")
                except Exception:
                    pass
                return

        # ── Caps check ────────────────────────────────────────────────────────
        if settings["anti_caps"] and len(message.content) >= settings["caps_min_length"]:
            letters = [c for c in message.content if c.isalpha()]
            if letters:
                caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters) * 100
                if caps_ratio >= settings["caps_threshold"]:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                    try:
                        await message.channel.send(
                            f"{member.mention} ⚠️ Please avoid excessive CAPS.", delete_after=5)
                    except discord.Forbidden:
                        pass
                    await self.log_action(message.guild, "Caps Filter", member,
                                          f"{caps_ratio:.0f}% uppercase", message)
                    return

        # ── Mass mention check ────────────────────────────────────────────────
        if settings["anti_mass_mention"]:
            mentions = len(message.mentions) + len(message.role_mentions)
            if mentions >= settings["mention_threshold"]:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                timeout_until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
                try:
                    await member.timeout(timeout_until, reason="AutoMod: Mass mention")
                except discord.Forbidden:
                    pass
                await self.log_action(message.guild, "Mass Mention Timeout", member,
                                      f"{mentions} mentions", message)
                return

        # ── Invite filter ─────────────────────────────────────────────────────
        if settings["filter_invites"] and INVITE_REGEX.search(message.content):
            try:
                await message.delete()
            except discord.NotFound:
                pass
            try:
                await message.channel.send(
                    f"{member.mention} ⚠️ Discord invites are not allowed here.", delete_after=5)
            except discord.Forbidden:
                pass
            await self.log_action(message.guild, "Invite Blocked", member,
                                   "Posted Discord invite", message)
            return

        # ── Link filter ───────────────────────────────────────────────────────
        if settings["filter_links"] and LINK_REGEX.search(message.content):
            allowed = any(r in member_role_ids for r in settings["allowed_link_roles"])
            if not allowed:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                try:
                    await message.channel.send(
                        f"{member.mention} ⚠️ Links are not allowed here.", delete_after=5)
                except discord.Forbidden:
                    pass
                await self.log_action(message.guild, "Link Blocked", member,
                                       "Posted a link", message)
                return

        # ── Banned words ─────────────────────────────────────────────────────
        if settings["filter_words"]:
            content_lower = message.content.lower()
            for word in settings["banned_words"]:
                if re.search(rf"\b{re.escape(word)}\b", content_lower):
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                    try:
                        await message.channel.send(
                            f"{member.mention} ⚠️ That message contained a banned word.",
                            delete_after=5)
                    except discord.Forbidden:
                        pass
                    await self.log_action(message.guild, "Banned Word", member,
                                           f"Used word: ||{word}||", message)
                    return

    # ── Anti-Raid ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = self.get_settings(member.guild.id)
        if not settings["anti_raid"]:
            return

        tracker = self.raid_tracker[member.guild.id]
        now = time.time()
        tracker.append(now)
        window = settings["raid_window"]
        threshold = settings["raid_threshold"]
        recent = [t for t in tracker if now - t <= window]

        if len(recent) >= threshold:
            try:
                await member.guild.edit(verification_level=discord.VerificationLevel.high)
                channel_id = settings.get("log_channel")
                if channel_id:
                    ch = member.guild.get_channel(channel_id)
                    if ch:
                        embed = discord.Embed(
                            title="🚨 RAID DETECTED",
                            description=(f"**{len(recent)} joins in {window}s!**\n"
                                         "Verification level raised to HIGH automatically."),
                            color=discord.Color.red(),
                            timestamp=datetime.datetime.utcnow()
                        )
                        await ch.send(embed=embed)
            except discord.Forbidden:
                pass

    # ── Configuration commands ─────────────────────────────────────────────────

    @app_commands.command(name="automod", description="View AutoMod settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_status(self, interaction: discord.Interaction):
        s = self.get_settings(interaction.guild_id)
        embed = discord.Embed(title="🛡️ AutoMod Settings", color=discord.Color.purple())
        embed.add_field(name="Enabled", value="✅" if s["enabled"] else "❌", inline=True)
        embed.add_field(name="Word Filter", value="✅" if s["filter_words"] else "❌", inline=True)
        embed.add_field(name="Anti-Spam", value="✅" if s["anti_spam"] else "❌", inline=True)
        embed.add_field(name="Anti-Caps", value="✅" if s["anti_caps"] else "❌", inline=True)
        embed.add_field(name="Anti-Raid", value="✅" if s["anti_raid"] else "❌", inline=True)
        embed.add_field(name="Invite Filter", value="✅" if s["filter_invites"] else "❌", inline=True)
        embed.add_field(name="Link Filter", value="✅" if s["filter_links"] else "❌", inline=True)
        embed.add_field(name="Mass Mention", value="✅" if s["anti_mass_mention"] else "❌", inline=True)
        embed.set_footer(text="Use /automod_set to configure | Eclipse Bot")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="automod_set", description="Configure AutoMod settings.")
    @app_commands.describe(setting="Setting to change", value="true/false")
    @app_commands.choices(setting=[
        app_commands.Choice(name="enabled", value="enabled"),
        app_commands.Choice(name="filter_words", value="filter_words"),
        app_commands.Choice(name="filter_invites", value="filter_invites"),
        app_commands.Choice(name="filter_links", value="filter_links"),
        app_commands.Choice(name="anti_spam", value="anti_spam"),
        app_commands.Choice(name="anti_caps", value="anti_caps"),
        app_commands.Choice(name="anti_mass_mention", value="anti_mass_mention"),
        app_commands.Choice(name="anti_raid", value="anti_raid"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_set(self, interaction: discord.Interaction, setting: str, value: str):
        s = self.get_settings(interaction.guild_id)
        bool_val = value.lower() in ("true", "1", "yes", "on")
        s[setting] = bool_val
        await interaction.response.send_message(f"✅ `{setting}` set to `{bool_val}`.")

    @app_commands.command(name="automod_logchannel", description="Set the AutoMod log channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.get_settings(interaction.guild_id)["log_channel"] = channel.id
        await interaction.response.send_message(
            f"✅ AutoMod logs will be sent to {channel.mention}.")

    @app_commands.command(name="addword", description="Add a word to the banned words list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def addword(self, interaction: discord.Interaction, word: str):
        s = self.get_settings(interaction.guild_id)
        s["banned_words"].append(word.lower())
        await interaction.response.send_message(
            f"✅ Added `{word}` to the banned words list.", ephemeral=True)

    @app_commands.command(name="removeword", description="Remove a word from the banned words list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeword(self, interaction: discord.Interaction, word: str):
        s = self.get_settings(interaction.guild_id)
        if word.lower() in s["banned_words"]:
            s["banned_words"].remove(word.lower())
            await interaction.response.send_message(
                f"✅ Removed `{word}` from the banned words list.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ `{word}` was not in the list.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ You need Administrator permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
