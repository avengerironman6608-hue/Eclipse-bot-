import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque
import datetime
import random
import subprocess
import sys

try:
    import nacl  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyNaCl>=1.5.0"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ====================== yt-dlp OPTIONS ======================
YDL_SEARCH_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    "extract_flat": False,
}

YDL_STREAM_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": False,
}

YDL_PLAYLIST_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "playlistend": 25,
}

# Spotify metadata extraction (no API key needed)
YDL_SPOTIFY_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "noplaylist": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def _check_nacl() -> bool:
    try:
        import nacl.secret  # noqa: F401
        return True
    except Exception:
        return False


def _extract(opts: dict, query: str):
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            return ydl.sanitize_info(info)
        except Exception as e:
            print(f"[Music] yt-dlp error: {e}")
            return None


async def _async_extract(opts, query):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _extract(opts, query))


class Song:
    def __init__(self, data: dict, requester):
        self.title       = data.get("title", "Unknown Title")
        self.stream_url  = data.get("url", "")
        self.webpage_url = data.get("webpage_url") or data.get("original_url") or self.stream_url
        self.thumbnail   = data.get("thumbnail", "")
        self.duration    = int(data.get("duration") or 0)
        self.requester   = requester
        self.channel     = data.get("channel") or data.get("uploader", "Unknown")

    def duration_str(self):
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


class GuildMusicState:
    def __init__(self):
        self.queue        = deque()
        self.voice_client = None
        self.current      = None
        self.loop         = False
        self.volume       = 0.5
        self.skip_votes   = set()
        self.text_channel = None


class Music(commands.Cog):
    """🎵 Music player with Spotify support."""

    def __init__(self, bot):
        self.bot    = bot
        self.states = {}
        print("[Music] PyNaCl ready." if _check_nacl() else "[Music] WARNING: PyNaCl not found.")

    def get_state(self, guild_id):
        return self.states.setdefault(guild_id, GuildMusicState())

    # ====================== NEW: Spotify Resolver ======================
    async def _resolve_spotify(self, url: str, requester):
        """Extract Spotify track/playlist metadata and convert to YouTube searches."""
        data = await _async_extract(YDL_SPOTIFY_OPTS, url)
        if not data:
            return []

        songs = []

        # Playlist / Album
        if "entries" in data:
            await asyncio.sleep(0)  # keep responsive
            for entry in data["entries"][:25]:  # limit to 25
                if not entry or not entry.get("title"):
                    continue
                title = entry.get("title", "")
                artist = entry.get("artist") or entry.get("uploader", "")
                search_query = f"{title} - {artist}" if artist else title
                song = await self.fetch_song(search_query, requester)
                if song:
                    songs.append(song)
            return songs

        # Single track
        title = data.get("title", "")
        artist = data.get("artist") or data.get("uploader", "")
        search_query = f"{title} - {artist}" if artist else title
        song = await self.fetch_song(search_query, requester)
        return [song] if song else []

    # ====================== Rest of your original methods (unchanged) ======================
    async def ensure_voice(self, interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
            return False
        return True

    async def safe_connect(self, interaction, state):
        if state.voice_client and state.voice_client.is_connected():
            if state.voice_client.channel != interaction.user.voice.channel:
                await state.voice_client.move_to(interaction.user.voice.channel)
            return True
        if not _check_nacl():
            await interaction.followup.send("❌ PyNaCl/libsodium missing. Add `libsodium` to nixpacks.toml and redeploy.")
            return False
        try:
            state.voice_client = await interaction.user.voice.channel.connect(timeout=15.0, reconnect=True)
            return True
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["nacl", "sodium"]):
                await interaction.followup.send("❌ Voice Error: PyNaCl/libsodium not found.")
            else:
                await interaction.followup.send(f"❌ Couldn't connect to voice: `{e}`")
            return False

    async def fetch_song(self, query: str, requester) -> "Song | None":
        search_query = query if query.startswith("http") else f"ytsearch1:{query}"
        data = await _async_extract(YDL_SEARCH_OPTS, search_query)
        if not data:
            return None
        entry = data
        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                return None
            entry = entries[0]

        # Pass 2 for stream URL if needed
        webpage_url = entry.get("webpage_url") or entry.get("original_url", "")
        needs_pass2 = (
            not entry.get("url")
            or "youtube.com/watch" in str(entry.get("url", ""))
            or "youtu.be/" in str(entry.get("url", ""))
        )
        if needs_pass2 and webpage_url:
            data2 = await _async_extract(YDL_STREAM_OPTS, webpage_url)
            if data2:
                e2 = data2.get("entries", [data2])[0] if data2.get("entries") else data2
                entry["url"] = e2.get("url", entry.get("url"))
                for k in ("title", "thumbnail", "duration", "channel", "uploader", "webpage_url"):
                    if e2.get(k):
                        entry[k] = e2[k]

        if not entry.get("url"):
            return None
        return Song(entry, requester)

    async def fetch_playlist(self, url, requester):
        data = await _async_extract(YDL_PLAYLIST_OPTS, url)
        if not data or "entries" not in data:
            return []
        songs = []
        for entry in data["entries"]:
            if not entry:
                continue
            vid_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
            if not vid_url:
                continue
            songs.append(Song({
                "title": entry.get("title", "Unknown"),
                "url": vid_url,
                "webpage_url": vid_url,
                "thumbnail": entry.get("thumbnail", ""),
                "duration": entry.get("duration", 0),
                "channel": entry.get("channel") or entry.get("uploader", "Unknown"),
            }, requester))
        return songs

    async def _resolve_stream(self, song: Song) -> str:
        url = song.stream_url
        if not url or "youtube.com/watch" in url or "youtu.be/" in url:
            data = await _async_extract(YDL_STREAM_OPTS, song.webpage_url)
            if data:
                r = data.get("entries", [data])[0] if data.get("entries") else data
                url = r.get("url", url)
                song.stream_url = url
        return url

    async def play_next(self, guild_id):
        state = self.get_state(guild_id)
        if not state.voice_client or not state.voice_client.is_connected():
            return

        if state.loop and state.current:
            song = state.current
        elif state.queue:
            song = state.queue.popleft()
            state.current = song
        else:
            state.current = None
            if state.text_channel:
                await state.text_channel.send("✅ Queue finished — leaving VC. 🌑")
            try:
                await state.voice_client.disconnect()
            except Exception:
                pass
            state.voice_client = None
            return

        stream_url = await self._resolve_stream(song)
        if not stream_url:
            if state.text_channel:
                await state.text_channel.send(f"❌ Couldn't resolve stream for **{song.title}** — skipping.")
            asyncio.create_task(self.play_next(guild_id))
            return

        try:
            source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
        except Exception as e:
            print(f"[Music] FFmpeg error: {e}")
            asyncio.create_task(self.play_next(guild_id))
            return

        def after(error):
            if error:
                print(f"[Music] Playback error: {error}")
            asyncio.create_task(self.play_next(guild_id))

        state.voice_client.play(source, after=after)
        state.skip_votes.clear()
        if state.text_channel:
            await state.text_channel.send(embed=self._np_embed(song))

    def _np_embed(self, song):
        embed = discord.Embed(title="🎵 Now Playing",
                              description=f"[{song.title}]({song.webpage_url})",
                              color=discord.Color.purple(),
                              timestamp=datetime.datetime.utcnow())
        embed.add_field(name="⏱ Duration", value=song.duration_str(), inline=True)
        embed.add_field(name="📺 Channel", value=song.channel, inline=True)
        embed.add_field(name="👤 Requested by", value=song.requester.mention, inline=True)
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text="Eclipse Music 🌑")
        return embed

    # ====================== UPDATED /play COMMAND ======================
    @app_commands.command(name="play", description="Play a song — YouTube, Spotify track/playlist, or search name.")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify link")
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.ensure_voice(interaction):
            return
        await interaction.response.defer()
        state = self.get_state(interaction.guild_id)
        state.text_channel = interaction.channel
        if not await self.safe_connect(interaction, state):
            return

        # === Spotify Support ===
        if "spotify.com" in query.lower():
            await interaction.followup.send("🔍 Resolving Spotify link...")
            songs = await self._resolve_spotify(query, interaction.user)
            if not songs:
                await interaction.followup.send("❌ Couldn't resolve Spotify link. Make sure it's public.")
                return

            if len(songs) > 1:  # Playlist / Album
                for s in songs:
                    state.queue.append(s)
                if not state.voice_client.is_playing() and not state.voice_client.is_paused():
                    await self.play_next(interaction.guild_id)
                await interaction.followup.send(f"📋 Added **{len(songs)}** songs from Spotify!")
                return
            else:  # Single track
                song = songs[0]

        # === YouTube Playlist ===
        elif "youtube.com/playlist" in query or ("list=" in query and "watch" not in query):
            await interaction.followup.send("⏳ Loading YouTube playlist...")
            songs = await self.fetch_playlist(query, interaction.user)
            if not songs:
                await interaction.followup.send("❌ Couldn't load playlist.")
                return
            for s in songs:
                state.queue.append(s)
            if not state.voice_client.is_playing() and not state.voice_client.is_paused():
                await self.play_next(interaction.guild_id)
            await interaction.followup.send(f"📋 Added **{len(songs)}** songs to the queue!")
            return

        # === Normal search / YouTube link / Spotify single (already resolved) ===
        else:
            await interaction.followup.send("🔍 Searching...")
            song = await self.fetch_song(query, interaction.user) if 'song' not in locals() else song

        if not song:
            await interaction.followup.send("❌ Couldn't find that song.")
            return

        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.queue.append(song)
            embed = discord.Embed(title="➕ Added to Queue", description=f"[{song.title}]({song.webpage_url})", color=discord.Color.blurple())
            embed.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
            embed.add_field(name="Duration", value=song.duration_str(), inline=True)
            await interaction.followup.send(embed=embed)
        else:
            state.current = song
            stream_url = await self._resolve_stream(song)
            if not stream_url:
                await interaction.followup.send("❌ Couldn't resolve audio stream.")
                return
            try:
                source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
                source = discord.PCMVolumeTransformer(source, volume=state.volume)
            except Exception as e:
                await interaction.followup.send(f"❌ Playback error: `{e}`")
                return

            def after(error):
                asyncio.create_task(self.play_next(interaction.guild_id))

            state.voice_client.play(source, after=after)
            await interaction.followup.send(embed=self._np_embed(song))

    # ====================== Rest of your commands (unchanged) ======================
    # (skip, pause, resume, stop, queue, nowplaying, volume, loop, shuffle, remove, disconnect, on_voice_state_update, etc.)
    # ... [I kept them exactly the same as you provided - just omitted here for brevity] ...

    # (Copy-paste all your remaining commands from the original code you sent - they are unchanged)

async def setup(bot):
    await bot.add_cog(Music(bot))
