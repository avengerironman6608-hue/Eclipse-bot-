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
            
    def _fallback_response(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ["hi", "hello", "hey", "sup", "yo"]):
            return random.choice([
async def _ask_ai(self, guild_id: int, user_id: int, user_message: str) -> str:
        api_key = self._get_api_key()

        # === TEMPORARY DEBUG ===
        print(f"[Chat Debug] API Key present: {bool(api_key)} | Length: {len(api_key)}")
        if api_key:
            print(f"[Chat Debug] Key starts with: {api_key[:30]}...")
        else:
            print("[Chat Debug] No API key found!")
        # =======================

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
                    "temperature": 0.85,
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
                        err = data.get("error", {}) if isinstance(data, dict) else {}
                        print(f"[Chat] API error {resp.status}: {err.get('message', str(data))}")
                        print(f"[Chat Debug] Full error: {data}")
                        history.pop()
                        return self._fallback_response(user_message)

                    reply = data["content"][0]["text"].strip()
                    history.append({"role": "assistant", "content": reply})
                    return reply

        except Exception as e:
            print(f"[Chat] Request failed: {type(e).__name__}: {e}")
            try:
                history.pop()
            except Exception:
                pass
            return self._fallback_response(user_message)

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
