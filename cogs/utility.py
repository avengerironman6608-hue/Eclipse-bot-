import discord
from discord.ext import commands
from discord import app_commands
import datetime
import platform
import random
import math

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class Utility(commands.Cog):
    """🔧 Utility commands."""

    def __init__(self, bot):
        self.bot        = bot
        self.start_time = datetime.datetime.utcnow()
        self.afk_users  = {}   # user_id -> {reason, time}
        self.reminders  = []   # list of {user_id, channel_id, message, time}

    # ── Ping / Info ───────────────────────────────────────────────────────────
    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        ms = round(self.bot.latency * 1000)
        color = discord.Color.green() if ms < 100 else discord.Color.yellow() if ms < 200 else discord.Color.red()
        e = discord.Embed(title="🏓 Pong!", color=color)
        e.add_field(name="Latency", value=f"{ms}ms")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="botinfo", description="View Eclipse Bot information.")
    async def botinfo(self, interaction: discord.Interaction):
        up = datetime.datetime.utcnow() - self.start_time
        h, rem = divmod(int(up.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        e = discord.Embed(title="🌑 Eclipse Bot Info", color=discord.Color.purple(),
                          timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=self.bot.user.display_avatar.url)
        e.add_field(name="Bot",     value=str(self.bot.user), inline=True)
        e.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        e.add_field(name="Users",   value=str(sum(g.member_count for g in self.bot.guilds if g.member_count)), inline=True)
        e.add_field(name="Uptime",  value=f"{h}h {m}m {s}s", inline=True)
        e.add_field(name="Python",  value=platform.python_version(), inline=True)
        e.add_field(name="discord.py", value=discord.__version__, inline=True)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="userinfo", description="View info about a member.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles  = [r.mention for r in member.roles if r != interaction.guild.default_role]
        e = discord.Embed(title=f"👤 {member}", color=member.color, timestamp=datetime.datetime.utcnow())
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="ID",       value=str(member.id), inline=True)
        e.add_field(name="Nickname", value=member.nick or "None", inline=True)
        e.add_field(name="Bot",      value="Yes" if member.bot else "No", inline=True)
        e.add_field(name="Joined",   value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "?", inline=True)
        e.add_field(name="Created",  value=member.created_at.strftime("%b %d, %Y"), inline=True)
        e.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        e.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:12]) or "None", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="serverinfo", description="View server info.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        e = discord.Embed(title=f"🌑 {g.name}", color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        if g.icon: e.set_thumbnail(url=g.icon.url)
        e.add_field(name="Owner",    value=g.owner.mention if g.owner else "?", inline=True)
        e.add_field(name="Members",  value=str(g.member_count), inline=True)
        e.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        e.add_field(name="Roles",    value=str(len(g.roles)), inline=True)
        e.add_field(name="Boosts",   value=str(g.premium_subscription_count), inline=True)
        e.add_field(name="Verification", value=str(g.verification_level).title(), inline=True)
        e.add_field(name="Created",  value=g.created_at.strftime("%b %d, %Y"), inline=True)
        e.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="avatar", description="View a member's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        e = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.purple())
        e.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="servericon", description="View the server icon.")
    async def servericon(self, interaction: discord.Interaction):
        if not interaction.guild.icon:
            return await interaction.response.send_message("❌ This server has no icon.", ephemeral=True)
        e = discord.Embed(title=f"{interaction.guild.name} — Server Icon", color=discord.Color.purple())
        e.set_image(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="roleinfo", description="View info about a role.")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        e = discord.Embed(title=f"🏷️ Role: {role.name}", color=role.color,
                          timestamp=datetime.datetime.utcnow())
        e.add_field(name="ID",          value=str(role.id), inline=True)
        e.add_field(name="Members",     value=str(len(role.members)), inline=True)
        e.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        e.add_field(name="Hoisted",     value="Yes" if role.hoist else "No", inline=True)
        e.add_field(name="Color",       value=str(role.color), inline=True)
        e.add_field(name="Position",    value=str(role.position), inline=True)
        key_perms = [p.replace("_", " ").title() for p, v in role.permissions if v]
        if key_perms:
            e.add_field(name="Permissions", value=", ".join(key_perms[:10]), inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="channelinfo", description="View info about a channel.")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        ch = channel or interaction.channel
        e = discord.Embed(title=f"📢 #{ch.name}", color=discord.Color.purple(),
                          timestamp=datetime.datetime.utcnow())
        e.add_field(name="ID",       value=str(ch.id), inline=True)
        e.add_field(name="Type",     value=str(ch.type).title(), inline=True)
        e.add_field(name="Category", value=ch.category.name if ch.category else "None", inline=True)
        e.add_field(name="Topic",    value=ch.topic or "None", inline=False)
        e.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s", inline=True)
        e.add_field(name="NSFW",     value="Yes" if ch.is_nsfw() else "No", inline=True)
        e.add_field(name="Created",  value=ch.created_at.strftime("%b %d, %Y"), inline=True)
        await interaction.response.send_message(embed=e)

    # ── Utility ───────────────────────────────────────────────────────────────
    @app_commands.command(name="embed", description="Send a custom embed message.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_cmd(self, interaction: discord.Interaction, title: str, description: str,
                        color: str = "7b2fff"):
        try: color_int = int(color.lstrip("#"), 16)
        except ValueError: color_int = 0x7b2fff
        e = discord.Embed(title=title, description=description, color=color_int,
                          timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Sent by {interaction.user.display_name}")
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        await interaction.channel.send(embed=e)

    @app_commands.command(name="announce", description="Send an announcement to a channel.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel,
                       message: str, ping_everyone: bool = False):
        content = "@everyone\n" if ping_everyone else ""
        e = discord.Embed(title="📢 Announcement", description=message,
                          color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"By {interaction.user.display_name}")
        try:
            await channel.send(content=content, embed=e)
            await interaction.response.send_message(f"✅ Sent to {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ No permission to send there.", ephemeral=True)

    @app_commands.command(name="snipe", description="See the last deleted message in this channel.")
    async def snipe(self, interaction: discord.Interaction):
        sniped = getattr(self.bot, "_sniped", {}).get(interaction.channel_id)
        if not sniped:
            return await interaction.response.send_message("Nothing to snipe! 🎯", ephemeral=True)
        e = discord.Embed(title="🎯 Sniped Message",
                          description=sniped["content"] or "(no text)",
                          color=discord.Color.purple(), timestamp=sniped["time"])
        e.set_author(name=sniped["author"], icon_url=sniped["avatar"])
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="afk", description="Set your AFK status.")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        self.afk_users[interaction.user.id] = {"reason": reason, "time": datetime.datetime.utcnow()}
        await interaction.response.send_message(f"💤 AFK set: **{reason}**")

    @app_commands.command(name="math", description="Calculate a math expression.")
    @app_commands.describe(expression="e.g. 2+2, sqrt(16), 5^2")
    async def math_cmd(self, interaction: discord.Interaction, expression: str):
        try:
            safe = expression.replace("^", "**")
            allowed = set("0123456789+-*/.() ")
            allowed_funcs = {"sqrt": math.sqrt, "pi": math.pi, "e": math.e,
                             "sin": math.sin, "cos": math.cos, "tan": math.tan,
                             "log": math.log, "abs": abs, "round": round}
            if not all(c in allowed or c.isalpha() for c in safe):
                raise ValueError("Invalid characters")
            result = eval(safe, {"__builtins__": {}}, allowed_funcs)
            await interaction.response.send_message(f"🧮 `{expression}` = **{result}**")
        except Exception:
            await interaction.response.send_message("❌ Invalid expression.", ephemeral=True)

    @app_commands.command(name="poll", description="Create a poll.")
    @app_commands.describe(question="Poll question", option1="Option 1", option2="Option 2",
                           option3="Option 3 (optional)", option4="Option 4 (optional)")
    async def poll(self, interaction: discord.Interaction, question: str,
                   option1: str, option2: str, option3: str = None, option4: str = None):
        options = [o for o in [option1, option2, option3, option4] if o]
        emojis  = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        e = discord.Embed(title=f"📊 {question}",
                          description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)),
                          color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        e.set_footer(text=f"Poll by {interaction.user.display_name}")
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        for i in range(len(options)): await msg.add_reaction(emojis[i])

    @app_commands.command(name="giveaway", description="Start a simple giveaway.")
    @app_commands.describe(prize="What you're giving away", duration_minutes="Duration in minutes", winners="Number of winners")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str,
                       duration_minutes: int = 5, winners: int = 1):
        ends_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration_minutes)
        e = discord.Embed(title="🎉 GIVEAWAY 🎉",
                          description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(ends_at.timestamp())}:R>\n\nReact with 🎉 to enter!",
                          color=discord.Color.gold(), timestamp=ends_at)
        e.set_footer(text=f"Hosted by {interaction.user.display_name}")
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        await msg.add_reaction("🎉")

        await asyncio.sleep(duration_minutes * 60)
        msg = await interaction.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            return await interaction.channel.send("❌ No one entered the giveaway!")
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            return await interaction.channel.send("❌ No valid entries!")
        winner_list = random.sample(users, min(winners, len(users)))
        mentions = ", ".join(w.mention for w in winner_list)
        await interaction.channel.send(f"🎉 Congratulations {mentions}! You won **{prize}**!")

    @app_commands.command(name="timer", description="Set a countdown timer.")
    @app_commands.describe(seconds="Seconds to count down", label="What to remind you about")
    async def timer(self, interaction: discord.Interaction, seconds: int, label: str = "Timer"):
        if seconds > 3600:
            return await interaction.response.send_message("❌ Max timer is 1 hour (3600s).", ephemeral=True)
        await interaction.response.send_message(f"⏱️ Timer set for **{seconds}s** — {label}")
        await asyncio.sleep(seconds)
        try:
            await interaction.followup.send(f"⏰ {interaction.user.mention} — **{label}** timer done!")
        except Exception: pass

    @app_commands.command(name="inviteinfo", description="Get info about a Discord invite link.")
    @app_commands.describe(invite_url="Discord invite URL")
    async def inviteinfo(self, interaction: discord.Interaction, invite_url: str):
        try:
            invite = await self.bot.fetch_invite(invite_url, with_counts=True)
            e = discord.Embed(title=f"📨 Invite Info", color=discord.Color.purple())
            e.add_field(name="Server", value=invite.guild.name if invite.guild else "Unknown", inline=True)
            e.add_field(name="Channel", value=f"#{invite.channel.name}" if invite.channel else "?", inline=True)
            e.add_field(name="Inviter", value=str(invite.inviter) if invite.inviter else "Unknown", inline=True)
            e.add_field(name="Members", value=f"{invite.approximate_member_count}", inline=True)
            e.add_field(name="Online", value=f"{invite.approximate_presence_count}", inline=True)
            e.add_field(name="Code", value=invite.code, inline=True)
            if invite.guild and invite.guild.icon:
                e.set_thumbnail(url=invite.guild.icon.url)
            await interaction.response.send_message(embed=e)
        except Exception as err:
            await interaction.response.send_message(f"❌ Invalid invite: `{err}`", ephemeral=True)

    @app_commands.command(name="color", description="Show a color from a hex code.")
    @app_commands.describe(hex_code="Hex color code e.g. ff5500")
    async def color(self, interaction: discord.Interaction, hex_code: str):
        try:
            color_int = int(hex_code.lstrip("#"), 16)
            e = discord.Embed(title=f"🎨 Color #{hex_code.lstrip('#').upper()}",
                              description=f"RGB: {(color_int >> 16) & 255}, {(color_int >> 8) & 255}, {color_int & 255}",
                              color=color_int)
            await interaction.response.send_message(embed=e)
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex code.", ephemeral=True)

    # ── Listeners ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        now = datetime.datetime.utcnow()
        if message.author.id in self.afk_users:
            del self.afk_users[message.author.id]
            try: await message.channel.send(f"👋 Welcome back {message.author.mention}, AFK removed.")
            except Exception: pass
        for user in message.mentions:
            if user.id in self.afk_users:
                data = self.afk_users[user.id]
                if (now - data["time"]).total_seconds() > 600:
                    del self.afk_users[user.id]; continue
                try: await message.channel.send(f"💤 **{user.display_name}** is AFK: {data['reason']}")
                except Exception: pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot: return
        if not hasattr(self.bot, "_sniped"): self.bot._sniped = {}
        self.bot._sniped[message.channel.id] = {
            "content": message.content, "author": str(message.author),
            "avatar": message.author.display_avatar.url, "time": datetime.datetime.utcnow(),
        }

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ No permission.", ephemeral=True)


import asyncio

async def setup(bot):
    await bot.add_cog(Utility(bot))
