import discord
from discord.ext import commands
from discord import app_commands
import re, datetime, time, os
from collections import defaultdict, deque

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))
DEFAULT_BANNED_WORDS = ["nigger","nigga","faggot","retard","kike","spic","chink","cunt","fuck","shit","bitch","asshole","bastard"]
INVITE_REGEX = re.compile(r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/\S+", re.IGNORECASE)
LINK_REGEX   = re.compile(r"https?://\S+", re.IGNORECASE)

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = {}
        self.spam_tracker = defaultdict(lambda: defaultdict(lambda: deque(maxlen=10)))
        self.raid_tracker = defaultdict(lambda: deque(maxlen=20))

    def get_settings(self, gid):
        return self.settings.setdefault(gid, {
            "enabled": True, "filter_words": True, "banned_words": list(DEFAULT_BANNED_WORDS),
            "filter_invites": True, "filter_links": False, "allowed_link_roles": [],
            "anti_spam": True, "spam_threshold": 5, "spam_window": 5,
            "anti_caps": True, "caps_threshold": 70, "caps_min_length": 10,
            "anti_mass_mention": True, "mention_threshold": 5,
            "anti_raid": True, "raid_threshold": 10, "raid_window": 10,
            "log_channel": None, "whitelist_roles": [], "whitelist_channels": [],
        })

    async def log_action(self, guild, action, user, reason, message=None):
        ch_id = self.get_settings(guild.id).get("log_channel")
        if not ch_id: return
        ch = guild.get_channel(ch_id)
        if not ch: return
        e = discord.Embed(title=f"🛡️ AutoMod — {action}", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="User",    value=f"{user.mention} (`{user.id}`)", inline=True)
        e.add_field(name="Channel", value=message.channel.mention if message else "N/A", inline=True)
        e.add_field(name="Reason",  value=reason, inline=False)
        if message and message.content:
            e.add_field(name="Message", value=f"```{message.content[:400]}```", inline=False)
        try: await ch.send(embed=e)
        except discord.Forbidden: pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot: return
        if message.author.id == OWNER_ID: return
        s = self.get_settings(message.guild.id)
        if not s["enabled"]: return
        member = message.author
        rids = [r.id for r in member.roles]
        if any(r in rids for r in s["whitelist_roles"]): return
        if message.channel.id in s["whitelist_channels"]: return
        if member.guild_permissions.manage_messages: return

        # Anti-spam
        if s["anti_spam"]:
            now = time.time()
            dq = self.spam_tracker[message.guild.id][member.id]
            dq.append(now)
            if len([t for t in dq if now - t <= s["spam_window"]]) >= s["spam_threshold"]:
                await message.delete()
                try: await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=5), reason="AutoMod: Spam")
                except discord.Forbidden: pass
                await self.log_action(message.guild, "Spam Timeout", member, "Spam detected", message)
                return

        # Anti-caps
        if s["anti_caps"] and len(message.content) >= s["caps_min_length"]:
            letters = [c for c in message.content if c.isalpha()]
            if letters and sum(1 for c in letters if c.isupper()) / len(letters) * 100 >= s["caps_threshold"]:
                await message.delete()
                try: await message.channel.send(f"{member.mention} ⚠️ Avoid excessive CAPS.", delete_after=5)
                except Exception: pass
                await self.log_action(message.guild, "Caps Filter", member, "Excessive caps", message)
                return

        # Anti-mass-mention
        if s["anti_mass_mention"] and (len(message.mentions) + len(message.role_mentions)) >= s["mention_threshold"]:
            await message.delete()
            try: await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=10), reason="AutoMod: Mass mention")
            except discord.Forbidden: pass
            await self.log_action(message.guild, "Mass Mention", member, "Too many mentions", message)
            return

        # Invite filter
        if s["filter_invites"] and INVITE_REGEX.search(message.content):
            await message.delete()
            try: await message.channel.send(f"{member.mention} ⚠️ Invites not allowed here.", delete_after=5)
            except Exception: pass
            await self.log_action(message.guild, "Invite Blocked", member, "Posted invite", message)
            return

        # Link filter
        if s["filter_links"] and LINK_REGEX.search(message.content):
            if not any(r in rids for r in s["allowed_link_roles"]):
                await message.delete()
                try: await message.channel.send(f"{member.mention} ⚠️ Links not allowed here.", delete_after=5)
                except Exception: pass
                await self.log_action(message.guild, "Link Blocked", member, "Posted link", message)
                return

        # Banned words
        if s["filter_words"]:
            cl = message.content.lower()
            for w in s["banned_words"]:
                if re.search(rf"\b{re.escape(w)}\b", cl):
                    await message.delete()
                    try: await message.channel.send(f"{member.mention} ⚠️ Banned word detected.", delete_after=5)
                    except Exception: pass
                    await self.log_action(message.guild, "Banned Word", member, "Used banned word", message)
                    return

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        s = self.get_settings(member.guild.id)
        if not s["anti_raid"]: return
        now = time.time()
        dq  = self.raid_tracker[member.guild.id]
        dq.append(now)
        if len([t for t in dq if now - t <= s["raid_window"]]) >= s["raid_threshold"]:
            try:
                await member.guild.edit(verification_level=discord.VerificationLevel.high)
                ch_id = s.get("log_channel")
                if ch_id:
                    ch = member.guild.get_channel(ch_id)
                    if ch:
                        await ch.send(embed=discord.Embed(
                            title="🚨 RAID DETECTED",
                            description="Too many joins detected. Verification raised to HIGH.",
                            color=discord.Color.red(), timestamp=datetime.datetime.utcnow()))
            except discord.Forbidden: pass

    @app_commands.command(name="automod", description="View AutoMod settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_status(self, interaction: discord.Interaction):
        s = self.get_settings(interaction.guild_id)
        e = discord.Embed(title="🛡️ AutoMod Settings", color=discord.Color.purple())
        for k, label in [("enabled","Enabled"),("filter_words","Word Filter"),("anti_spam","Anti-Spam"),
                          ("anti_caps","Anti-Caps"),("anti_raid","Anti-Raid"),
                          ("filter_invites","Invite Filter"),("filter_links","Link Filter"),
                          ("anti_mass_mention","Mass Mention")]:
            e.add_field(name=label, value="✅" if s[k] else "❌", inline=True)
        e.add_field(name="Spam Threshold", value=f"{s['spam_threshold']} msgs/{s['spam_window']}s", inline=True)
        e.set_footer(text="Use /automod_set to configure")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="automod_set", description="Toggle an AutoMod feature.")
    @app_commands.describe(setting="Feature to toggle", value="true or false")
    @app_commands.choices(setting=[
        app_commands.Choice(name="enabled",           value="enabled"),
        app_commands.Choice(name="filter_words",      value="filter_words"),
        app_commands.Choice(name="filter_invites",    value="filter_invites"),
        app_commands.Choice(name="filter_links",      value="filter_links"),
        app_commands.Choice(name="anti_spam",         value="anti_spam"),
        app_commands.Choice(name="anti_caps",         value="anti_caps"),
        app_commands.Choice(name="anti_mass_mention", value="anti_mass_mention"),
        app_commands.Choice(name="anti_raid",         value="anti_raid"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_set(self, interaction: discord.Interaction, setting: str, value: str):
        self.get_settings(interaction.guild_id)[setting] = value.lower() in ("true","1","yes","on")
        await interaction.response.send_message(f"✅ `{setting}` = `{value}`.")

    @app_commands.command(name="automod_logchannel", description="Set the AutoMod log channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.get_settings(interaction.guild_id)["log_channel"] = channel.id
        await interaction.response.send_message(f"✅ AutoMod logs → {channel.mention}.")

    @app_commands.command(name="addword", description="Add a banned word.")
    @app_commands.checks.has_permissions(administrator=True)
    async def addword(self, interaction: discord.Interaction, word: str):
        s = self.get_settings(interaction.guild_id)
        if word.lower() not in s["banned_words"]: s["banned_words"].append(word.lower())
        await interaction.response.send_message(f"✅ Added `{word}` to banned words.", ephemeral=True)

    @app_commands.command(name="removeword", description="Remove a banned word.")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeword(self, interaction: discord.Interaction, word: str):
        s = self.get_settings(interaction.guild_id)
        if word.lower() in s["banned_words"]:
            s["banned_words"].remove(word.lower())
            await interaction.response.send_message(f"✅ Removed `{word}`.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Not in list.", ephemeral=True)

    @app_commands.command(name="badwords", description="Show the banned words list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def badwords(self, interaction: discord.Interaction):
        words = self.get_settings(interaction.guild_id)["banned_words"]
        e = discord.Embed(title="🚫 Banned Words", color=discord.Color.red())
        e.description = ", ".join(f"||{w}||" for w in words) or "None"
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="whitelistrole", description="Whitelist a role from AutoMod.")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelistrole(self, interaction: discord.Interaction, role: discord.Role):
        s = self.get_settings(interaction.guild_id)
        if role.id not in s["whitelist_roles"]: s["whitelist_roles"].append(role.id)
        await interaction.response.send_message(f"✅ {role.mention} whitelisted.")

    @app_commands.command(name="whitelistchannel", description="Whitelist a channel from AutoMod.")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelistchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        s = self.get_settings(interaction.guild_id)
        if channel.id not in s["whitelist_channels"]: s["whitelist_channels"].append(channel.id)
        await interaction.response.send_message(f"✅ {channel.mention} whitelisted.")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))