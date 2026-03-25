import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque

# ================= FFMPEG =================
FFMPEG_PATH = "/usr/bin/ffmpeg"

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn -loglevel quiet"
}

# ================= YTDLP FIX =================
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "default_search": "ytsearch1",  # 🔥 FIXED
    "extract_flat": "in_playlist",
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "source_address": "0.0.0.0",  # 🔥 FIX
}

# ================= SONG =================
class Song:
    def __init__(self, data, requester):
        self.title = data.get("title")
        self.webpage_url = data.get("webpage_url")
        self.requester = requester

# ================= STATE =================
class GuildState:
    def __init__(self):
        self.queue = deque()
        self.voice = None
        self.current = None
        self.volume = 0.5
        self.text = None
        self.loop = False

# ================= BUTTON UI =================
class PlayerControls(discord.ui.View):
    def __init__(self, cog, gid):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(label="⏯", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(self.gid)
        if state.voice and state.voice.is_playing():
            state.voice.pause()
            await interaction.response.send_message("⏸ Paused", ephemeral=True)
        else:
            state.voice.resume()
            await interaction.response.send_message("▶️ Resumed", ephemeral=True)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(self.gid)
        if state.voice:
            state.voice.stop()
        await interaction.response.send_message("⏭ Skipped", ephemeral=True)

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.get_state(self.gid)
        if state.voice:
            await state.voice.disconnect()
            state.queue.clear()
        await interaction.response.send_message("🛑 Stopped", ephemeral=True)

# ================= MUSIC =================
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, gid):
        return self.states.setdefault(gid, GuildState())

    # ============== FETCH ==============
    async def fetch(self, query, requester):
        loop = asyncio.get_event_loop()

    def run():
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        return ydl.extract_info(f"ytsearch1:{query}", download=False)

        try:
            data = await loop.run_in_executor(None, run)

            if not data:
                return None

            if "entries" in data:
                if not data["entries"]:
                    return None
                data = data["entries"][0]

            if not data:
                return None

            return Song(data, requester)

        except Exception as e:
            print("[FETCH ERROR]:", str(e))  # 🔥 DEBUG
            return None

    # ============== STREAM ==============
    async def get_stream(self, song):
        loop = asyncio.get_event_loop()

        def run():
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                data = ydl.extract_info(song.webpage_url, download=False)
                return data

        try:
            data = await loop.run_in_executor(None, run)

            if not data:
                return None

            return data.get("url") or data.get("formats")[0].get("url")

        except Exception as e:
            print("[STREAM ERROR]:", str(e))  # 🔥 DEBUG
            return None

    # ============== PLAY NEXT ==============
    async def play_next(self, gid):
        state = self.get_state(gid)

        if state.loop and state.current:
            state.queue.appendleft(state.current)

        if not state.queue:
            if state.voice:
                await state.voice.disconnect()
            return

        song = state.queue.popleft()
        state.current = song

        stream = await self.get_stream(song)

        if not stream:
            if state.text:
                await state.text.send(f"❌ Skipping: **{song.title}**")
            await self.play_next(gid)
            return

        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    stream,
                    executable=FFMPEG_PATH,
                    **FFMPEG_OPTIONS
                ),
                volume=state.volume
            )
        except Exception as e:
            print("[FFMPEG ERROR]:", e)
            if state.text:
                await state.text.send("❌ FFmpeg error.")
            return

        def after(e):
            asyncio.run_coroutine_threadsafe(self.play_next(gid), self.bot.loop)

        state.voice.play(source, after=after)

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=song.title,
            color=discord.Color.purple()
        )

        view = PlayerControls(self, gid)

        if state.text:
            await state.text.send(embed=embed, view=view)

    # ============== PLAY ==============
    @app_commands.command(name="play", description="Play music")
    async def play(self, interaction: discord.Interaction, query: str):

        if not interaction.user.voice:
            await interaction.response.send_message("❌ Join VC first", ephemeral=True)
            return

        await interaction.response.defer()

        state = self.get_state(interaction.guild_id)
        state.text = interaction.channel

        if not state.voice:
            state.voice = await interaction.user.voice.channel.connect()

        song = await self.fetch(query, interaction.user)

        if not song:
            await interaction.followup.send("❌ Song not found")
            return

        state.queue.append(song)

        if not state.voice.is_playing():
            await self.play_next(interaction.guild_id)

        await interaction.followup.send(f"✅ Added: **{song.title}**")

    # ============== QUEUE ==============
    @app_commands.command(name="queue", description="Show queue")
    async def queue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)

        if not state.queue:
            await interaction.response.send_message("📭 Queue empty")
            return

        desc = "\n".join([f"{i+1}. {s.title}" for i, s in enumerate(state.queue)])

        embed = discord.Embed(title="📀 Queue", description=desc[:4000])
        await interaction.response.send_message(embed=embed)

    # ============== LOOP ==============
    @app_commands.command(name="loop", description="Toggle loop")
    async def loop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.loop = not state.loop
        await interaction.response.send_message(f"🔁 Loop: {state.loop}")

    # ============== VOLUME ==============
    @app_commands.command(name="volume", description="Set volume (0-100)")
    async def volume(self, interaction: discord.Interaction, vol: int):
        state = self.get_state(interaction.guild_id)

        state.volume = max(0, min(vol, 100)) / 100

        if state.voice and state.voice.source:
            state.voice.source.volume = state.volume

        await interaction.response.send_message(f"🔊 Volume set to {vol}%")

# ================= SETUP =================
async def setup(bot):
    await bot.add_cog(Music(bot))
