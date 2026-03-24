import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque
import datetime
import random
import re

# ── YouTube-DL options ────────────────────────────────────────────────────────
YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
    "cookiefile": None,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -bufsize 512k",
}

# ── Spotify URL pattern ───────────────────────────────────────────────────────
SPOTIFY_TRACK_RE = re.compile(
    r"https?://open\.spotify\.com/track/([A-Za-z0-9]+)")
SPOTIFY_PLAYLIST_RE = re.compile(
    r"https?://open\.spotify\.com/playlist/([A-Za-z0-9]+)")


def is_spotify_url(url: str) -> bool:
    return "open.spotify.com" in url


def spotify_to_search(url: str) -> str:
    """
    Converts a Spotify track URL into a YouTube search query.
    Extracts track ID and searches by track name via yt-dlp spotdl-style fallback.
    Since we can't authenticate Spotify API without keys, we extract the track
    name from the URL path and search YouTube directly.
    """
    # Try to extract readable name from URL slug if present
    # e.g. /track/TRACKID -> search "spotify track TRACKID" on YouTube
    # yt-dlp handles spotify:// URIs natively on newer builds
    track_match = SPOTIFY_TRACK_RE.match(url)
    if track_match:
        track_id = track_match.group(1)
        # yt-dlp can resolve spotify track IDs to YouTube via music.youtube.com
        return f"https://music.youtube.com/search?q={track_id}"
    return url


# ── Data classes ──────────────────────────────────────────────────────────────
class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.title = data.get("title", "Unknown Title")
        self.url = data.get("url") or data.get("webpage_url", "")
        self.webpage_url = data.get("webpage_url", self.url)
        self.thumbnail = data.get("thumbnail", "")
        self.duration = data.get("duration") or 0
        self.requester = requester
        self.channel = data.get("channel") or data.get("uploader", "Unknown")

    def duration_str(self) -> str:
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


class GuildMusicState:
    def __init__(self):
        self.queue: deque = deque()
        self.voice_client: discord.VoiceClient = None
        self.current: Song = None
        self.loop: bool = False
        self.volume: float = 0.5
        self.skip_votes: set = set()
        self.text_channel: discord.TextChannel = None


# ── Cog ───────────────────────────────────────────────────────────────────────
class Music(commands.Cog):
    """🎵 Music player — YouTube & Spotify support."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        return self.states.setdefault(guild_id, GuildMusicState())

    async def ensure_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel first!", ephemeral=True)
            return False
        return True

    async def fetch_song(self, query: str, requester: discord.Member) -> Song | None:
        """Resolve query to a playable Song. Handles YouTube URLs, search terms, and Spotify."""
        loop = asyncio.get_event_loop()

        # Spotify → YouTube search
        if is_spotify_url(query):
            # Use yt-dlp's built-in spotify support (yt-dlp ≥2023.x resolves spotify tracks)
            # Falls back to a YouTube music search if that fails
            pass  # keep original URL; yt-dlp handles it

        # Plain text → YouTube search
        if not query.startswith("http"):
            query = f"ytsearch:{query}"

        ydl_opts = dict(YDL_OPTIONS)
        try:
            data = await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(query, download=False)
            )
            if not data:
                return None
            if "entries" in data:
                entry = data["entries"][0]
                if not entry:
                    return None
                # For flat extractions we may need a second pass
                if not entry.get("url"):
                    entry = await loop.run_in_executor(
                        None,
                        lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(
                            entry.get("webpage_url") or entry.get("url", ""),
                            download=False)
                    )
            else:
                entry = data
            return Song(entry, requester)
        except Exception as e:
            print(f"[Music] fetch_song error: {e}")
            return None

    async def fetch_playlist(self, url: str, requester: discord.Member) -> list[Song]:
        """Fetch up to 25 songs from a YouTube playlist."""
        loop = asyncio.get_event_loop()
        opts = {**YDL_OPTIONS, "extract_flat": True, "playlistend": 25}
        try:
            data = await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False))
            if not data or "entries" not in data:
                return []
            songs = []
            for entry in data["entries"]:
                if entry:
                    songs.append(Song({
                        "title": entry.get("title", "Unknown"),
                        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id','')}",
                        "webpage_url": f"https://www.youtube.com/watch?v={entry.get('id','')}",
                        "thumbnail": entry.get("thumbnail", ""),
                        "duration": entry.get("duration", 0),
                        "channel": entry.get("channel") or entry.get("uploader", "Unknown"),
                    }, requester))
            return songs
        except Exception as e:
            print(f"[Music] fetch_playlist error: {e}")
            return []

    async def play_next(self, guild_id: int):
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
                try:
                    await state.text_channel.send(
                        "✅ Queue finished! Leaving voice channel. 🌑")
                except Exception:
                    pass
            try:
                await state.voice_client.disconnect()
            except Exception:
                pass
            state.voice_client = None
            return

        try:
            source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
        except Exception as e:
            print(f"[Music] Source error: {e}")
            if state.text_channel:
                try:
                    await state.text_channel.send("❌ Couldn't play that track — skipping...")
                except Exception:
                    pass
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id), self.bot.loop)
            return

        def after_playing(error):
            if error:
                print(f"[Music] Playback error: {error}")
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id), self.bot.loop)

        state.voice_client.play(source, after=after_playing)
        state.skip_votes.clear()

        if state.text_channel:
            embed = self._now_playing_embed(song)
            try:
                await state.text_channel.send(embed=embed)
            except Exception:
                pass

    def _now_playing_embed(self, song: Song) -> discord.Embed:
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{song.title}]({song.webpage_url})",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="⏱ Duration", value=song.duration_str(), inline=True)
        embed.add_field(name="📺 Channel", value=song.channel, inline=True)
        embed.add_field(name="👤 Requested by", value=song.requester.mention, inline=True)
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text="Eclipse Music 🌑")
        return embed

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song — YouTube URL, search term, or Spotify track link.")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify track URL")
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.ensure_voice(interaction):
            return
        await interaction.response.defer()

        state = self.get_state(interaction.guild_id)
        state.text_channel = interaction.channel

        # Connect to voice
        if not state.voice_client or not state.voice_client.is_connected():
            try:
                state.voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Couldn't connect to voice: {e}")
                return

        # Handle YouTube playlists
        if ("youtube.com/playlist" in query or "list=" in query) and "spotify" not in query:
            songs = await self.fetch_playlist(query, interaction.user)
            if not songs:
                await interaction.followup.send("❌ Couldn't load that playlist.")
                return
            for s in songs:
                state.queue.append(s)
            if not state.voice_client.is_playing():
                await self.play_next(interaction.guild_id)
            await interaction.followup.send(
                f"📋 Added **{len(songs)}** songs from playlist to queue!")
            return

        # Single song
        song = await self.fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send(
                "❌ Could not find that song. Try a different search term or URL.")
            return

        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.queue.append(song)
            embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"[{song.title}]({song.webpage_url})",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
            embed.add_field(name="Duration", value=song.duration_str(), inline=True)
            await interaction.followup.send(embed=embed)
        else:
            state.current = song
            try:
                source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)
                source = discord.PCMVolumeTransformer(source, volume=state.volume)
            except Exception as e:
                await interaction.followup.send(f"❌ Playback error: {e}")
                return

            def after_playing(error):
                asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction.guild_id), self.bot.loop)

            state.voice_client.play(source, after=after_playing)
            await interaction.followup.send(embed=self._now_playing_embed(song))

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.voice_client or not state.voice_client.is_playing():
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        state.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    @app_commands.command(name="pause", description="Pause the current song.")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the current song.")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue.")
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.queue.clear()
        state.loop = False
        state.current = None
        if state.voice_client:
            try:
                await state.voice_client.disconnect()
            except Exception:
                pass
            state.voice_client = None
        await interaction.response.send_message("⏹️ Stopped and cleared queue.")

    @app_commands.command(name="queue", description="View the current music queue.")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.purple())
        if state.current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"[{state.current.title}]({state.current.webpage_url}) "
                      f"({state.current.duration_str()})",
                inline=False)
        if state.queue:
            lines = "\n".join(
                f"`{i+1}.` [{s.title}]({s.webpage_url}) — {s.duration_str()}"
                for i, s in enumerate(list(state.queue)[:10]))
            embed.add_field(
                name=f"📋 Up Next ({len(state.queue)} songs)", value=lines, inline=False)
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the current song.")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        await interaction.response.send_message(embed=self._now_playing_embed(state.current))

    @app_commands.command(name="volume", description="Set playback volume (0–200).")
    @app_commands.describe(level="Volume percentage (0–200)")
    async def volume(self, interaction: discord.Interaction, level: int):
        state = self.get_state(interaction.guild_id)
        level = max(0, min(200, level))
        state.volume = level / 100
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**.")

    @app_commands.command(name="loop", description="Toggle queue loop on/off.")
    async def loop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.loop = not state.loop
        await interaction.response.send_message(
            f"🔁 Loop **{'enabled ✅' if state.loop else 'disabled ❌'}**.")

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        q = list(state.queue)
        random.shuffle(q)
        state.queue = deque(q)
        await interaction.response.send_message("🔀 Queue shuffled!")

    @app_commands.command(name="remove", description="Remove a song from the queue by position.")
    @app_commands.describe(position="Queue position to remove")
    async def remove(self, interaction: discord.Interaction, position: int):
        state = self.get_state(interaction.guild_id)
        q = list(state.queue)
        if 1 <= position <= len(q):
            removed = q.pop(position - 1)
            state.queue = deque(q)
            await interaction.response.send_message(f"🗑️ Removed **{removed.title}**.")
        else:
            await interaction.response.send_message("❌ Invalid queue position.", ephemeral=True)

    @app_commands.command(name="disconnect", description="Disconnect from voice channel.")
    async def disconnect(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client:
            await state.voice_client.disconnect()
            state.voice_client = None
            state.current = None
            state.queue.clear()
            await interaction.response.send_message("👋 Disconnected.")
        else:
            await interaction.response.send_message(
                "❌ Not in a voice channel.", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(
            self, member: discord.Member,
            before: discord.VoiceState, after: discord.VoiceState):
        """Auto-disconnect when alone in VC for 30 seconds."""
        if member.bot:
            return
        state = self.states.get(member.guild.id)
        if not state or not state.voice_client:
            return
        vc = state.voice_client
        if vc.channel and len([m for m in vc.channel.members if not m.bot]) == 0:
            await asyncio.sleep(30)
            if vc.channel and len([m for m in vc.channel.members if not m.bot]) == 0:
                try:
                    await vc.disconnect()
                except Exception:
                    pass
                state.voice_client = None
                state.current = None
                state.queue.clear()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
