import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import random

# ================= CONFIG =================

POLLINATIONS_URL = "https://text.pollinations.ai/openai"

SYSTEM_PROMPT = (
    "You are Eclipse Bot, a friendly and helpful Discord bot. "
    "Keep replies short (1–3 sentences), casual and fun."
)

conversation_history: dict[int, list] = {}
MAX_HISTORY = 8

# ================= SESSION (FIXED) =================
session = None

async def get_session():
    global session
    if session is None or session.closed:
        timeout = aiohttp.ClientTimeout(total=15)  # faster timeout
        session = aiohttp.ClientSession(timeout=timeout)
    return session

# ================= POLLINATIONS FIX =================
async def ask_pollinations(guild_id: int, user_message: str) -> str:
    history = conversation_history.setdefault(guild_id, [])
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    payload = {
        "model": "openai",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "max_tokens": 120,   # optimized for speed
        "temperature": 0.7   # stable replies
    }

    try:
        session = await get_session()

        async with session.post(
            POLLINATIONS_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as resp:

            if resp.status != 200:
                return "⚠️ AI busy, try again."

            data = await resp.json(content_type=None)

            reply = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if not reply:
                return "😐 No response, try again."

            history.append({"role": "assistant", "content": reply})
            return reply

    except asyncio.TimeoutError:
        return "⏳ AI timeout, try again."
    except Exception as e:
        print(f"[Pollinations Error]: {e}")
        return "⚠️ AI error, try later."

# ================= FUN DATA =================
MAGIC_8_BALL = [
    "✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely.",
    "🤔 Reply hazy, try again.", "❌ Don't count on it.", "❌ Very doubtful."
]

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything! 😄"),
    ("Why don't programmers like nature?", "Too many bugs! 🐛"),
]

SPACE_FACTS = [
    "🌑 A solar eclipse can only happen during a new moon.",
    "🌌 The Milky Way has 100–400 billion stars.",
]

# ================= COG =================
class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔥 CLEANUP SESSION
    def cog_unload(self):
        global session
        if session and not session.closed:
            asyncio.create_task(session.close())

    # ================= AI LISTENER =================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not (self.bot.user in message.mentions or "eclipse" in message.content.lower()):
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

    # ================= CHAT =================
    @app_commands.command(name="chat", description="Chat with Eclipse AI.")
    async def chat_cmd(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        reply = await ask_pollinations(
            interaction.guild_id or interaction.channel_id,
            f"{interaction.user.display_name}: {message}"
        )

        embed = discord.Embed(description=reply, color=discord.Color.purple())
        embed.set_author(name="Eclipse AI 🌑", icon_url=self.bot.user.display_avatar.url)

        await interaction.followup.send(embed=embed)

    # ================= CLEAR CHAT =================
    @app_commands.command(name="clearchat", description="Clear AI chat history.")
    async def clearchat(self, interaction: discord.Interaction):
        conversation_history.pop(interaction.guild_id or interaction.channel_id, None)
        await interaction.response.send_message("🗑️ Chat cleared!", ephemeral=True)

    # ================= FUN COMMANDS =================
    @app_commands.command(name="8ball", description="Ask 8ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        await interaction.response.send_message(f"🎱 {random.choice(MAGIC_8_BALL)}")

    @app_commands.command(name="joke", description="Get a joke")
    async def joke(self, interaction: discord.Interaction):
        j = random.choice(JOKES)
        await interaction.response.send_message(f"{j[0]}\n||{j[1]}||")

    @app_commands.command(name="fact", description="Space fact")
    async def fact(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(SPACE_FACTS))

    # ================= HELP =================
    @app_commands.command(name="help", description="View all commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌑 Eclipse Bot Commands",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="🎵 Music",
            value="`/play` `/skip` `/stop` `/queue` `/loop` `/volume`",
            inline=False
        )

        embed.add_field(
            name="💬 Chat & Fun",
            value="`/chat` `/clearchat` `/8ball` `/joke` `/fact`",
            inline=False
        )

        embed.set_footer(text="AI powered by Pollinations ⚡")

        await interaction.response.send_message(embed=embed)

# ================= SETUP =================
async def setup(bot):
    await bot.add_cog(Chat(bot))
