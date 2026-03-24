import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
import re
import os
import aiohttp
from collections import defaultdict, deque

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))

HISTORY_LIMIT = 12

SYSTEM_PROMPT = """You are Eclipse Bot 🌑, a friendly and witty Discord bot assistant for a server called Eclipse.

Your personality:
- Warm, casual, and conversational — like a cool friend, not a corporate assistant
- You love space, astronomy, and cosmic themes
- You tell engaging stories when asked, chat about everyday things, share opinions
- You use light Discord-style language (occasional emojis, casual phrasing) but never overdo it
- You have a playful sense of humor and enjoy jokes and banter
- You remember what was said earlier in the conversation and refer back to it naturally
- When someone shares something personal, you respond with genuine empathy

What you can talk about:
- Casual conversation, life topics, stories, opinions, debates
- Space facts, science, astronomy
- Games, music, movies, food, travel — anything humans enjoy chatting about
- Discord server help (moderation, leveling, music commands)
- Creative storytelling on request

Rules:
- Keep responses concise for casual chat (1-3 sentences usually), longer only for stories or detailed questions
- Never be rude, harmful, or inappropriate
- If someone asks about bot commands, mention /help
- Sign off with 🌑 occasionally but don't spam emojis
- Never say you are an AI language model — you are Eclipse Bot
- Respond in the language the user writes in"""


class Chat(commands.Cog):
    """💬 AI-powered chat — real conversations, stories, and fun commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.history: dict = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=HISTORY_LIMIT)))

    def _get_api_key(self) -> str:
        """Read key at call time so Railway variables are always fresh."""
        return os.environ.get("ANTHROPIC_API_KEY", "").strip()

    async def _ask_ai(self, guild_id: int, user_id: int, user_message: str) -> str:
        api_key = self._get_api_key()

        if not api_key:
            print("[Chat] WARNING: ANTHROPIC_API_KEY not set — using fallback.")
            return self._fallback_response(user_message)

        history = self.history[guild_id][user_id]
        history.append({"role": "user", "content": user_message})
        messages = list(history)

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "claude-haiku-4-5",
                    "max_tokens": 500,
                    "temperature": 0.8,  
                    "system": SYSTEM_PROMPT,
                    "messages": messages,
                }
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    data = await resp.json()

                    if resp.status != 200:
                        err = data.get("error", {}).get("message", "Unknown error")
                        print(f"[Chat] API error {resp.status}: {err}")
                        history.pop()
                        return self._fallback_response(user_message)

                    reply = data["content"][0]["text"].strip()
                    history.append({"role": "assistant", "content": reply})
                    return reply

        except Exception as e:
            print(f"[Chat] Request failed: {e}")
            try:
                history.pop()
            except Exception:
                pass
            return self._fallback_response(user_message)

    def _fallback_response(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ["hi", "hello", "hey", "sup", "yo"]):
            return random.choice([
                "Hey there! 🌑 What's up?",
                "Hello! The Eclipse is watching over you ✨",
                "Yo! What can I do for you? 😎",
            ])
        if any(w in msg for w in ["bye", "goodbye", "cya", "later"]):
            return random.choice(["See you around! 🌑", "Catch you later! ✨", "Bye! 🌙"])
        if "how are you" in msg:
            return random.choice([
                "Eclipse-powered and fully operational! ✨",
                "Doing great! Watching the cosmos 🌑",
                "Feeling astronomical! How about you? 🌙",
            ])
        if any(w in msg for w in ["thanks", "thank you", "thx", "ty"]):
            return random.choice([
                "No problem! 🌑", "Anytime! ✨", "Happy to help! 😄"])
        return random.choice([
            "Interesting! 🤔 Ask me anything or try `/help`!",
            "Hmm, tell me more! 🌑 I'm all ears.",
            "That's cool! What else is on your mind? ✨",
        ])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.strip()
        bot_mentioned = self.bot.user in message.mentions
        name_used = "eclipse" in content.lower()

        if not (bot_mentioned or name_used):
            return

        clean = re.sub(r"<@!?\d+>", "", content).strip()
        clean = re.sub(r"\beclipse\b", "", clean, flags=re.IGNORECASE).strip()

        if not clean:
            if message.author.id == OWNER_ID:
                await message.channel.send(
                    f"Welcome back, my creator {message.author.mention}! 🌑👑")
            else:
                await message.channel.send(
                    f"Hey {message.author.mention}! 🌑 What's up? Ask me anything!")
            return

        guild_id = message.guild.id if message.guild else 0
        async with message.channel.typing():
            reply = await self._ask_ai(guild_id, message.author.id, clean)

        await message.channel.send(f"{message.author.mention} {reply}")

    @app_commands.command(name="ask", description="Ask Eclipse anything — AI-powered.")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        guild_id = interaction.guild_id or 0
        reply = await self._ask_ai(guild_id, interaction.user.id, question)
        embed = discord.Embed(
            description=reply, color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow())
        embed.set_author(
            name=f"{interaction.user.display_name} asked:",
            icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Eclipse AI 🌑")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="story", description="Ask Eclipse to tell you a story.")
    @app_commands.describe(prompt="What kind of story? e.g. 'a space adventure'")
    async def story(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer()
        guild_id = interaction.guild_id or 0
        reply = await self._ask_ai(
            guild_id, interaction.user.id,
            f"Tell me a short engaging story about: {prompt}")
        embed = discord.Embed(
            title="📖 Eclipse Story", description=reply,
            color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Story for {interaction.user.display_name} 🌑")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="clearchat",
                          description="Clear your conversation history with Eclipse.")
    async def clearchat(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id or 0
        self.history[guild_id][interaction.user.id].clear()
        await interaction.response.send_message(
            "🧹 Cleared! Fresh start! 🌑", ephemeral=True)

    MAGIC_8_BALL = [
        "✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely.",
        "✅ Most likely.", "🤔 Reply hazy, try again.", "🤔 Ask again later.",
        "🤔 Cannot predict now.", "❌ Don't count on it.", "❌ My reply is no.",
        "❌ Very doubtful.", "❌ Outlook not so good.",
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

    FUN_FACTS = [
        "🌑 A solar eclipse can only happen during a new moon.",
        "⭐ The Sun is ~400× wider than the Moon but also ~400× farther away.",
        "🌍 A total solar eclipse moves at ~1,700 km/h across Earth's surface.",
        "🌙 The Moon drifts from Earth at about 3.8 cm per year.",
        "🪐 Jupiter has 95 known moons!",
        "🌌 The Milky Way has an estimated 100–400 billion stars.",
        "💫 More stars exist in the universe than grains of sand on all Earth's beaches.",
        "🚀 It would take over 9 years to drive to the Moon at highway speed.",
    ]

    @app_commands.command(name="8ball", description="Ask the Magic 8-Ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(color=discord.Color.purple())
        embed.add_field(name="❓ Question", value=question, inline=False)
        embed.add_field(name="🎱 Answer", value=random.choice(self.MAGIC_8_BALL), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction):
        setup, punchline = random.choice(self.JOKES)
        embed = discord.Embed(color=discord.Color.yellow())
        embed.add_field(name="😄 Setup", value=setup, inline=False)
        embed.add_field(name="🥁 Punchline", value=f"||{punchline}||", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="fact", description="Get a random space fact.")
    async def fact(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔭 Space Fact",
                description=random.choice(self.FUN_FACTS),
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
            await interaction.response.send_message(
                "❌ Provide at least 2 options separated by commas.", ephemeral=True)
            return
        await interaction.response.send_message(f"🌑 I choose: **{random.choice(choices)}**!")

    @app_commands.command(name="poll", description="Create a poll.")
    @app_commands.describe(
        question="Poll question", option1="Option 1", option2="Option 2",
        option3="Option 3 (optional)", option4="Option 4 (optional)")
    async def poll(self, interaction: discord.Interaction, question: str,
                   option1: str, option2: str,
                   option3: str = None, option4: str = None):
        options = [o for o in [option1, option2, option3, option4] if o]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        embed = discord.Embed(
            title=f"📊 {question}",
            description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)),
            color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Poll by {interaction.user.display_name} | React to vote!")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            try:
                await msg.add_reaction(emojis[i])
            except Exception:
                pass

    @app_commands.command(name="avatar", description="View a member's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar", color=discord.Color.purple())
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="View information about a member.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed = discord.Embed(
            title=f"👤 {member}", color=member.color,
            timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="Joined Server",
            value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "Unknown",
            inline=True)
        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles[:10]) or "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="View server information.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(
            title=f"🌑 {g.name}", color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(g.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Boosts", value=str(g.premium_subscription_count), inline=True)
        embed.add_field(name="Created", value=g.created_at.strftime("%b %d, %Y"), inline=True)
        embed.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="View all Eclipse Bot commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌑 Eclipse Bot — Commands",
            description="Here's everything I can do:",
            color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
        embed.add_field(
            name="🔨 Moderation",
            value="`/ban` `/kick` `/warn` `/timeout` `/untimeout` `/softban` "
                  "`/purge` `/lock` `/unlock` `/slowmode` `/nick` `/addrole` `/removerole`",
            inline=False)
        embed.add_field(
            name="🛡️ AutoMod",
            value="`/automod` `/automod_set` `/automod_logchannel` `/addword` `/removeword`",
            inline=False)
        embed.add_field(
            name="📈 Leveling",
            value="`/rank` `/leaderboard` `/setlevel` `/setxp` `/addxp` `/resetxp` "
                  "`/levelrole` `/levelchannel` `/setlevelschannel`",
            inline=False)
        embed.add_field(
            name="🎵 Music",
            value="`/play` `/skip` `/pause` `/resume` `/stop` `/queue` "
                  "`/nowplaying` `/volume` `/loop` `/shuffle` `/remove` `/disconnect`",
            inline=False)
        embed.add_field(
            name="💬 AI Chat",
            value="`/ask` `/story` `/clearchat` — or @mention me / say 'eclipse'!",
            inline=False)
        embed.add_field(
            name="🎲 Fun",
            value="`/8ball` `/joke` `/fact` `/roll` `/coinflip` `/choose` `/poll`",
            inline=False)
        embed.add_field(
            name="👤 Info", value="`/avatar` `/userinfo` `/serverinfo`", inline=False)
        embed.add_field(
            name="🔧 Utility",
            value="`/ping` `/botinfo` `/embed` `/announce` `/snipe`", inline=False)
        embed.set_footer(text="Eclipse Bot 🌑 | @mention or say 'eclipse' to chat!")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Chat(bot))
