import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import datetime
import random

POLLINATIONS_URL = "https://text.pollinations.ai/openai"

SYSTEM_PROMPT = (
    "You are Eclipse Bot, a friendly and helpful Discord bot. "
    "Keep replies short (1–3 sentences), casual and fun. "
    "Do not mention being an AI unless asked."
)

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
        "max_tokens": 150,  # faster
        "temperature": 0.85,
    }

    for attempt in range(3):  # retry system
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    POLLINATIONS_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=40)  # increased timeout
                ) as resp:

                    if resp.status != 200:
                        continue

                    data = await resp.json(content_type=None)

                    reply = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )

                    if reply:
                        history.append({"role": "assistant", "content": reply})
                        return reply

        except asyncio.TimeoutError:
            if attempt == 2:
                return "⏳ Servers are slow right now, try again in a moment."
        except Exception as e:
            print(f"[Chat Error]: {e}")
            return "⚠️ Something went wrong. Try again."

    return "😕 Couldn't get a response. Try again!"


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


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @app_commands.command(name="chat", description="Chat with Eclipse AI.")
    async def chat_cmd(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        reply = await ask_pollinations(
            interaction.guild_id or interaction.channel_id,
            f"{interaction.user.display_name}: {message}"
        )

        embed = discord.Embed(description=reply, color=discord.Color.purple())
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Chat(bot))
