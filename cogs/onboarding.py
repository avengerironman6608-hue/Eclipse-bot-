import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio

CHANNEL_STRUCTURE = {
    "📋 Information": [
        ("📌│rules", "Server rules and guidelines"),
        ("📢│announcements", "Server announcements"),
        ("👋│welcome", "Welcome messages"),
    ],
    "🌐 General": [
        ("💬│general", "General chat"),
        ("🤖│bot-commands", "Use bot commands here"),
        ("😂│memes", "Memes and fun content"),
        ("🖼️│media", "Share images and videos"),
    ],
    "🎵 Music": [
        ("🎵│music-commands", "Use music commands here"),
    ],
    "📊 Logs": [
        ("📊│mod-logs", "Moderation logs"),
        ("🛡️│automod-logs", "AutoMod logs"),
    ],
}

VOICE_CHANNELS = ["🔊 General", "🎵 Music Lounge", "🎮 Gaming"]

ROLE_STRUCTURE = [
    {
        "name": "🌑 Eclipse Admin",
        "color": discord.Color.red(),
        "permissions": discord.Permissions(administrator=True)
    },
    {
        "name": "🛡️ Moderator",
        "color": discord.Color.orange(),
        "permissions": discord.Permissions(
            manage_messages=True, kick_members=True, ban_members=True,
            moderate_members=True
        )
    },
    {
        "name": "⭐ VIP",
        "color": discord.Color.gold(),
        "permissions": discord.Permissions.none()
    },
    {
        "name": "✅ Verified",
        "color": discord.Color.green(),
        "permissions": discord.Permissions.none()
    },
    {
        "name": "🤖 Bot",
        "color": discord.Color.blurple(),
        "permissions": discord.Permissions.none()
    },
    {
        "name": "👋 Member",
        "color": discord.Color.light_grey(),
        "permissions": discord.Permissions.none()
    },
]

RULES_CONTENT = """## 📜 Server Rules

**1. Be Respectful**
Treat all members with kindness and respect. Harassment, discrimination, or hate speech will result in a ban.

**2. No Spam**
Do not spam messages, emojis, or mentions. Keep conversations relevant to the channel topic.

**3. No NSFW Content**
Keep all content appropriate. NSFW content is strictly prohibited.

**4. No Advertising**
Do not advertise other Discord servers, products, or services without admin permission.

**5. No Doxxing**
Never share personal information of other members without their consent.

**6. Follow Discord ToS**
All members must follow Discord's Terms of Service and Community Guidelines.

**7. Listen to Staff**
Moderators and Admins have final say. If you disagree, contact staff — don't argue publicly.

**8. Have Fun!**
This server is a community. Enjoy your time here! 🌑

*Breaking rules may result in warnings, timeouts, kicks, or permanent bans.*"""


class Onboarding(commands.Cog):
    """🚀 Auto-setup: channels, roles, welcome, rules, verification."""

    def __init__(self, bot):
        self.bot = bot
        self.guild_config = {}

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await asyncio.sleep(2)
        owner = guild.owner
        if owner:
            try:
                embed = discord.Embed(
                    title="🌑 Eclipse Bot Has Arrived!",
                    description=(
                        f"Hey **{owner.display_name}**! Eclipse Bot has joined **{guild.name}**.\n\n"
                        "To auto-setup your server with channels, roles, and configuration, "
                        "run `/setup` in your server.\n\n"
                        "Make sure Eclipse Bot has **Administrator** permissions for full functionality."
                    ),
                    color=discord.Color.purple(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.set_footer(text="Eclipse Bot — Your all-in-one companion 🌑")
                await owner.send(embed=embed)
            except discord.Forbidden:
                pass

    @app_commands.command(name="setup",
                          description="Auto-setup your server with channels, roles, and config.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild

        embed = discord.Embed(
            title="🚀 Eclipse Bot — Server Setup",
            description="Setting up your server... This may take a moment.",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        msg = await interaction.followup.send(embed=embed)

        created = {"categories": [], "channels": [], "roles": [], "errors": []}

        # ── Create Roles ──────────────────────────────────────────────────────
        embed.description = "⏳ Creating roles..."
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

        role_map = {}
        for role_data in ROLE_STRUCTURE:
            existing = discord.utils.get(guild.roles, name=role_data["name"])
            if existing:
                role_map[role_data["name"]] = existing
                continue
            try:
                role = await guild.create_role(
                    name=role_data["name"],
                    color=role_data["color"],
                    permissions=role_data["permissions"],
                    hoist=role_data["name"] in ["🌑 Eclipse Admin", "🛡️ Moderator"],
                    mentionable=False,
                    reason="Eclipse Bot Setup"
                )
                role_map[role_data["name"]] = role
                created["roles"].append(role.name)
            except Exception as e:
                created["errors"].append(f"Role {role_data['name']}: {e}")

        # ── Create Channels ───────────────────────────────────────────────────
        embed.description = "⏳ Creating channels..."
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

        channel_map = {}
        for category_name, channels in CHANNEL_STRUCTURE.items():
            existing_cat = discord.utils.get(guild.categories, name=category_name)
            if existing_cat:
                cat = existing_cat
            else:
                try:
                    cat = await guild.create_category(category_name, reason="Eclipse Bot Setup")
                    created["categories"].append(cat.name)
                except Exception as e:
                    created["errors"].append(f"Category {category_name}: {e}")
                    continue

            for ch_name, ch_topic in channels:
                slug = ch_name.split("│")[1] if "│" in ch_name else ch_name
                existing_ch = discord.utils.get(cat.text_channels, name=slug)
                if existing_ch:
                    channel_map[ch_name] = existing_ch
                    continue
                try:
                    ch = await cat.create_text_channel(
                        name=ch_name, topic=ch_topic, reason="Eclipse Bot Setup")
                    channel_map[ch_name] = ch
                    created["channels"].append(ch.name)
                except Exception as e:
                    created["errors"].append(f"Channel {ch_name}: {e}")

        # ── Create Voice Channels ─────────────────────────────────────────────
        try:
            voice_cat = discord.utils.get(guild.categories, name="🔊 Voice")
            if not voice_cat:
                voice_cat = await guild.create_category("🔊 Voice", reason="Eclipse Bot Setup")
            for vc_name in VOICE_CHANNELS:
                if not discord.utils.get(voice_cat.voice_channels, name=vc_name):
                    await voice_cat.create_voice_channel(vc_name, reason="Eclipse Bot Setup")
        except Exception as e:
            created["errors"].append(f"Voice channels: {e}")

        # ── Post Rules ────────────────────────────────────────────────────────
        rules_ch = channel_map.get("📌│rules")
        if not rules_ch:
            rules_ch = (discord.utils.get(guild.text_channels, name="rules") or
                        discord.utils.get(guild.text_channels, name="📌│rules"))
        if rules_ch:
            try:
                await rules_ch.purge(limit=5)
                await rules_ch.send(RULES_CONTENT)
            except Exception:
                pass

        # ── Store config ──────────────────────────────────────────────────────
        self.guild_config[guild.id] = {
            "welcome_channel": channel_map.get("👋│welcome"),
            "log_channel": channel_map.get("📊│mod-logs"),
            "automod_channel": channel_map.get("🛡️│automod-logs"),
            "bot_channel": channel_map.get("🤖│bot-commands"),
            "member_role": role_map.get("👋 Member"),
        }

        # ── Final report ──────────────────────────────────────────────────────
        embed = discord.Embed(
            title="✅ Server Setup Complete!",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="📁 Categories",
                        value=f"{len(created['categories'])} created", inline=True)
        embed.add_field(name="💬 Channels",
                        value=f"{len(created['channels'])} created", inline=True)
        embed.add_field(name="🏷️ Roles",
                        value=f"{len(created['roles'])} created", inline=True)
        if created["errors"]:
            embed.add_field(name="⚠️ Errors",
                            value="\n".join(created["errors"][:5]), inline=False)
        embed.add_field(
            name="🔧 Next Steps",
            value=(
                "• `/automod_logchannel` — Set AutoMod log channel\n"
                "• `/levelchannel` — Set level-up announcement channel\n"
                "• `/setwelcome` — Customize welcome messages\n"
                "• `/reactionroles` — Set up reaction roles"
            ),
            inline=False
        )
        embed.set_footer(text="Eclipse Bot — All-in-One Discord Bot 🌑")
        try:
            await msg.edit(embed=embed)
        except Exception:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="setwelcome", description="Set the welcome channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.guild_config.setdefault(interaction.guild_id, {})
        config["welcome_channel"] = channel
        await interaction.response.send_message(
            f"✅ Welcome messages will be sent to {channel.mention}.")

    @app_commands.command(name="setmemberrole",
                          description="Set the role given to new members.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setmemberrole(self, interaction: discord.Interaction, role: discord.Role):
        config = self.guild_config.setdefault(interaction.guild_id, {})
        config["member_role"] = role
        await interaction.response.send_message(
            f"✅ New members will receive {role.mention}.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = self.guild_config.get(member.guild.id, {})

        member_role = config.get("member_role")
        if member_role:
            try:
                await member.add_roles(member_role, reason="Auto-role on join")
            except discord.Forbidden:
                pass

        welcome_ch = config.get("welcome_channel")
        if not welcome_ch:
            welcome_ch = (discord.utils.get(member.guild.text_channels, name="welcome") or
                          discord.utils.get(member.guild.text_channels, name="👋│welcome"))
        if welcome_ch:
            embed = discord.Embed(
                title=f"🌑 Welcome to {member.guild.name}!",
                description=(
                    f"Hey {member.mention}, welcome to **{member.guild.name}**!\n\n"
                    f"You are member **#{member.guild.member_count}**.\n"
                    f"Please read the rules and enjoy your stay! 🌑"
                ),
                color=discord.Color.purple(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Eclipse Bot — Welcome System")
            try:
                await welcome_ch.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = self.guild_config.get(member.guild.id, {})
        welcome_ch = config.get("welcome_channel")
        if not welcome_ch:
            welcome_ch = (discord.utils.get(member.guild.text_channels, name="welcome") or
                          discord.utils.get(member.guild.text_channels, name="👋│welcome"))
        if welcome_ch:
            embed = discord.Embed(
                title="👋 Member Left",
                description=(f"**{member}** has left the server. "
                             f"We now have **{member.guild.member_count}** members."),
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await welcome_ch.send(embed=embed)
            except discord.Forbidden:
                pass

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ You need Administrator permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Onboarding(bot))

