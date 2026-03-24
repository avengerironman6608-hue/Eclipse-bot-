import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
    help_command=None,
    description="Eclipse Bot — Your all-in-one Discord companion 🌑",
    owner_id=OWNER_ID,
)

# Store owner ID on bot object so cogs can access it
bot.owner_id_override = OWNER_ID

COGS = [
    "cogs.moderation",
    "cogs.automod",
    "cogs.leveling",
    "cogs.music",
    "cogs.onboarding",
    "cogs.chat",
    "cogs.utility",
    "cogs.welcome",
    "cogs.roles",
    "cogs.bot_logging",  # Renamed from cogs.logging to avoid shadowing Python's built-in logging module
]


@bot.event
async def on_ready():
    print(f"🌑 Eclipse Bot is online as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the Eclipse 🌑 | /help"
        )
    )
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Command error: {error}")


async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  ✅ Loaded {cog}")
        except Exception as e:
            print(f"  ❌ Failed to load {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("❌ DISCORD_TOKEN not set in environment variables!")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
