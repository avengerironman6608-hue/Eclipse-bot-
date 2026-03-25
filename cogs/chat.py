import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import datetime
import random

# ── Pollinations AI — FREE, no API key needed ─────────────────────────────────
POLLINATIONS_URL = "https://text.pollinations.ai/openai"

SYSTEM_PROMPT = (
    "You are Eclipse Bot, a friendly and helpful Discord bot. "
    "You have a chill, casual personality. Keep replies short and conversational — "
    "1 to 3 sentences max unless the user asks something detailed. "
    "Never use asterisks for actions. Never mention being an AI unless directly asked. "
    "Be helpful, friendly, and occasionally funny."
)

# Per-guild conversation history (last 10 messages for context)
conversation_history: dict[int, list] = {}
MAX_HISTORY = 10


async def ask_pollinations(guild_id: int, user_message: str) -> str:
    history = conversation_history.setdefault(guild_id, [])
    history.append({"role": "user", "content": user_message})
    if len(history) > MAX_HISTORY:
        conversation_history[guild_id] = history[-MAX_HISTORY:]
        history = conversation_history[guild_id]

    payload = {
        "model": "openai",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "max_tokens": 300,
        "temperature": 0.85,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                POLLINATIONS_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status != 200:
                    return "Sorry, I'm having trouble thinking right now. Try again!"
                data = await resp.json(content_type=None)
                reply = (data.get("choices", [{}])[0]
                             .get("message", {})
                             .get("content", "")
                             .strip())
                if not reply:
                    return "Hmm, got nothing. Try asking again!"
                history.append({"role": "assistant", "content": reply})
                return reply
    except asyncio.TimeoutError:
        return "I'm thinking too hard — timed out! Try again."
    except Exception as e:
        print(f"[Chat] Pollinations error: {e}")
        return "Something went wrong on my end. Try again!"


MAGIC_8_BALL = [
    "✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely.",
    "✅ You may rely on it.", "✅ As I see it, yes.", "✅ Most likely.",
    "🤔 Reply hazy, try again.", "🤔 Ask again later.", "🤔 Cannot predict now.",
    "❌ Don't count on it.", "❌ My reply is no.", "❌ Very doubtful.",
    "❌ Outlook not so good.",
]

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything! 😄"),
    ("What do you call fake spaghetti?", "An impasta! 🍝"),
    ("Why did the robot go on vacation?", "To recharge its batteries! 🤖"),
    ("Why don't programmers like nature?", "It has too many bugs! 🐛"),
    ("What did the ocean say to the beach?", "Nothing, it just waved! 🌊"),
    ("Why did the moon skip dinner?", "Because it was already full! 🌕"),
    ("How do astronomers organize a party?", "They planet! 🪐"),
]

SPACE_FACTS = [
    "🌑 A solar eclipse can only happen during a new moon.",
    "☀️ The Sun is 400x wider than the Moon — that's why they look the same size during a total eclipse!",
    "🌙 The Moon drifts ~3.8 cm further from Earth every year.",
    "🪐 Jupiter has 95 known moons!",
    "🌌 The Milky Way has an estimated 100–400 billion stars.",
    "🚀 It would take over 9 years to drive to the Moon at highway speed.",
    "🔭 The corona of the Sun is only visible during a total solar eclipse.",
    "⭐ Neutron stars can spin up to 700 times per second.",
]


class Chat(commands.Cog):
    """💬 AI chat via Pollinations AI + fun commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        bot_mentioned = self.bot.user in message.mentions
        name_trigger  = "eclipse" in message.content.lower()
        if not (bot_mentioned or name_trigger):
            return

        clean = message.content
        for m in message.mentions:
            clean = clean.replace(f"<@{m.id}>", "").replace(f"<@!{m.id}>", "")
        clean = clean.replace("eclipse", "").strip() or "hey"

        async with message.channel.typing():
            reply = await ask_pollinations(
                message.guild.id if message.guild else message.channel.id,
                f"{message.author.display_name}: {clean}"
            )
        await message.reply(reply, mention_author=False)

    @app_commands.command(name="chat", description="Chat with Eclipse AI.")
    @app_commands.describe(message="What do you want to say?")
    async def chat_cmd(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        reply = await ask_pollinations(
            interaction.guild_id or interaction.channel_id,
            f"{interaction.user.display_name}: {message}"
        )
        embed = discord.Embed(description=reply, color=discord.Color.purple())
        embed.set_author(name="Eclipse AI 🌑", icon_url=self.bot.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="clearchat", description="Clear your AI chat history with Eclipse.")
    async def clearchat(self, interaction: discord.Interaction):
        conversation_history.pop(interaction.guild_id or interaction.channel_id, None)
        await interaction.response.send_message("🗑️ Conversation history cleared!", ephemeral=True)

    @app_commands.command(name="8ball", description="Ask the Magic 8-Ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(color=discord.Color.purple())
        embed.add_field(name="❓ Question", value=question,                    inline=False)
        embed.add_field(name="🎱 Answer",   value=random.choice(MAGIC_8_BALL), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction):
        setup, punchline = random.choice(JOKES)
        embed = discord.Embed(color=discord.Color.yellow())
        embed.add_field(name="😄 Setup",     value=setup,              inline=False)
        embed.add_field(name="🥁 Punchline", value=f"||{punchline}||", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="fact", description="Get a random space fact.")
    async def fact(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(
            title="🔭 Space Fact", description=random.choice(SPACE_FACTS),
            color=discord.Color.blurple()))

    @app_commands.command(name="roll", description="Roll a dice.")
    @app_commands.describe(sides="Number of sides (default 6)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        await interaction.response.send_message(
            f"🎲 You rolled a **{random.randint(1, max(2, sides))}** (d{sides})")

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"The coin landed on: **{random.choice(['Heads 🪙', 'Tails 🪙'])}**!")

    @app_commands.command(name="choose", description="Let Eclipse choose between options.")
    @app_commands.describe(options="Comma-separated options e.g. pizza,tacos,sushi")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            await interaction.response.send_message("❌ Give me at least 2 options!", ephemeral=True)
            return
        await interaction.response.send_message(f"🌑 I choose: **{random.choice(choices)}**!")

    @app_commands.command(name="poll", description="Create a poll.")
    @app_commands.describe(question="Poll question", option1="Option 1", option2="Option 2",
                           option3="Option 3 (optional)", option4="Option 4 (optional)")
    async def poll(self, interaction: discord.Interaction, question: str,
                   option1: str, option2: str, option3: str = None, option4: str = None):
        options = [o for o in [option1, option2, option3, option4] if o]
        emojis  = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        embed = discord.Embed(
            title=f"📊 {question}",
            description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)),
            color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Poll by {interaction.user.display_name} | React to vote!")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

    @app_commands.command(name="avatar", description="View a member's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.purple())
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="View info about a member.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles  = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed = discord.Embed(title=f"👤 {member}", color=member.color, timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID",             value=str(member.id),   inline=True)
        embed.add_field(name="Nickname",        value=member.nick or "None", inline=True)
        embed.add_field(name="Bot",             value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Joined",          value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "?", inline=True)
        embed.add_field(name="Created",         value=member.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]) or "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="View server information.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(title=f"🌑 {g.name}", color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner",    value=g.owner.mention if g.owner else "?", inline=True)
        embed.add_field(name="Members",  value=str(g.member_count),                  inline=True)
        embed.add_field(name="Channels", value=str(len(g.channels)),                 inline=True)
        embed.add_field(name="Roles",    value=str(len(g.roles)),                     inline=True)
        embed.add_field(name="Boosts",   value=str(g.premium_subscription_count),     inline=True)
        embed.add_field(name="Created",  value=g.created_at.strftime("%b %d, %Y"),    inline=True)
        embed.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="snipe", description="See the last deleted message.")
    async def snipe(self, interaction: discord.Interaction):
        sniped = getattr(self.bot, "_sniped", {}).get(interaction.channel_id)
        if not sniped:
            await interaction.response.send_message("Nothing to snipe! 🎯", ephemeral=True)
            return
        embed = discord.Embed(title="🎯 Sniped Message", description=sniped["content"] or "(no text)",
                              color=discord.Color.purple(), timestamp=sniped["time"])
        embed.set_author(name=sniped["author"], icon_url=sniped["avatar"])
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        if not hasattr(self.bot, "_sniped"):
            self.bot._sniped = {}
        self.bot._sniped[message.channel.id] = {
            "content": message.content, "author": str(message.author),
            "avatar": message.author.display_avatar.url, "time": datetime.datetime.utcnow(),
        }

    @app_commands.command(name="help", description="View all Eclipse Bot commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌑 Eclipse Bot — All Commands",
            description="Every available slash command:",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="🔨 Moderation",
            value="`/ban` `/unban` `/kick` `/warn` `/warnings` `/clearwarnings` "
                  "`/timeout` `/untimeout` `/purge` `/slowmode` `/lock` `/unlock` "
                  "`/nick` `/addrole` `/removerole`", inline=False)
        embed.add_field(name="🛡️ AutoMod",
            value="`/automod` `/automod_set` `/automod_logchannel` `/addword` `/removeword`",
            inline=False)
        embed.add_field(name="📈 Leveling",
            value="`/rank` `/leaderboard` `/setxp` `/addxp` `/resetxp` `/levelrole` `/levelchannel`",
            inline=False)
        embed.add_field(name="🎵 Music",
            value="`/play` `/skip` `/pause` `/resume` `/stop` `/queue` "
                  "`/nowplaying` `/volume` `/loop` `/shuffle` `/remove` `/disconnect`",
            inline=False)
        embed.add_field(name="🚀 Setup & Welcome",
            value="`/setup` `/setwelcome` `/setmemberrole`", inline=False)
        embed.add_field(name="🏷️ Roles",
            value="`/reactionroles` `/removereactionrole` `/listreactionroles` `/autorole`",
            inline=False)
        embed.add_field(name="📋 Logging",
            value="`/setlogchannel` `/togglelog`", inline=False)
        embed.add_field(name="🔧 Utility",
            value="`/ping` `/botinfo` `/embed` `/announce` `/snipe`", inline=False)
        embed.add_field(name="💬 Fun & Chat",
            value="`/chat` `/clearchat` `/8ball` `/joke` `/fact` `/roll` "
                  "`/coinflip` `/choose` `/poll` `/avatar` `/userinfo` `/serverinfo`",
            inline=False)
        embed.set_footer(text="💡 Mention me or say 'eclipse' to chat with AI!")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Chat(bot))
