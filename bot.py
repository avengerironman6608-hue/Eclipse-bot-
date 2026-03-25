import discord
from discord.ext import commands
import os
import asyncio
import traceback
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

# Make owner ID accessible in cogs
bot.owner_id_override = OWNER_ID

# ================= COGS =================
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
    "cogs.bot_logging",
]

# ================= LOAD COGS =================
async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception:
            print(f"❌ Failed to load {cog}")
            traceback.print_exc()

# ================= READY =================
@bot.event
async def on_ready():
    print(f"\n🌑 Logged in as {bot.user} (ID: {bot.user.id})")

    # ✅ ADDED DEBUG LINE (ONLY CHANGE)
    import shutil
    print("FFmpeg Path:", shutil.which("ffmpeg"))

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the Eclipse 🌑 | /help"
        )
    )

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")

        # Debug: show how many commands actually exist
        print(f"📊 Commands currently in tree: {len(bot.tree.get_commands())}")

    except Exception:
        print("❌ Sync error:")
        traceback.print_exc()

# ================= ERROR HANDLER =================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"⚠ Command error: {error}")

# ================= OWNER SYNC COMMAND =================
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} commands")
    except Exception:
        await ctx.send("❌ Sync failed")
        traceback.print_exc()

# ================= MAIN =================
async def main():
    async with bot:
        await load_cogs()  # ✅ Load BEFORE start

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("❌ DISCORD_TOKEN not set in environment variables!")

        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
