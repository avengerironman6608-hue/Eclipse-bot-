import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque
import datetime
import random
import re
import subprocess, sys

# ── Auto-install PyNaCl if missing ───────────────────────────────────────────
try:
    import nacl  # noqa
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyNaCl>=1.5.0"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ── Spotify regex ─────────────────────────────────────────────────────────────
SPOTIFY_TRACK    = re.compile(r"open\.spotify\.com/track/([A-Za-z0-9]+)")
SPOTIFY_PLAYLIST = re.compile(r"open\.spotify\.com/playlist/([A-Za-z0-9]+)")
SPOTIFY_ALBUM    = re.compile(r"open\.spotify\.com/album/([A-Za-z0-9]+)")

# ── yt-dlp options ────────────────────────────────────────────────────────────
YDL_BASE = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
}
YDL_SEARCH  = {**YDL_BASE, "default_search": "ytsearch1", "extract_flat": False}
YDL_STREAM  = {**YDL_BASE, "extract_flat": False}
YDL_FLAT    = {**YDL_BASE, "extract_flat": True, "noplaylist": False, "playlistend": 30}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn -loglevel quiet",
}


def _check_nacl():
    try:
        import nacl.secret  # noqa
        return True
    except Exception:
        return False


def _run_ydl(opts, query):
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            return ydl.sanitize_info(ydl.extract_info(query, download=False))
        except Exception as e:
            print(f"[Music] yt-dlp: {e}")
            return None


async def _extract(opts, query):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _run_ydl(opts, query))


# ── Spotify → YouTube search string ──────────────────────────────────────────
def spotify_to_search(url: str) -> str | None:
    """
    Converts Spotify URL → YouTube search query.
    yt-dlp can resolve Spotify track URLs natively on newer builds.
    We try yt-dlp first; if it fails we fall back to searching by track ID.
    """
    if SPOTIFY_TRACK.search(url):
        return url          # yt-dlp handles spotify track URLs natively
    if SPOTIFY_PLAYLIST.search(url) or SPOTIFY_ALBUM.search(url):
        return url          # yt-dlp handles spotify playlist/album natively
    return None


class Song:
    def __init__(self, data: dict, requester):
        self.title       = data.get("title", "Unknown")
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


class GuildState:
    def __init__(self):
        self.queue    = deque()
        self.voice    = None
        self.current  = None
        self.loop     = False
        self.volume   = 0.5
        self.text     = None


# ── Player button UI ──────────────────────────────────────────────────────────
class PlayerView(discord.ui.View):
    def __init__(self, cog, gid):
        super().__init__(timeout=None)
        self.cog = cog
        self.gid = gid

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, _):
        s = self.cog.get_state(self.gid)
        if not s.voice:
            return await interaction.response.send_message("Not in VC.", ephemeral=True)
        if s.voice.is_playing():
            s.voice.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        elif s.voice.is_paused():
            s.voice.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, _):
        s = self.cog.get_state(self.gid)
        if s.voice and (s.voice.is_playing() or s.voice.is_paused()):
            s.voice.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction: discord.Interaction, _):
        s = self.cog.get_state(self.gid)
        s.loop = not s.loop
        await interaction.response.send_message(
            f"🔁 Loop {'enabled' if s.loop else 'disabled'}.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _):
        s = self.cog.get_state(self.gid)
        s.queue.clear()
        s.loop    = False
        s.current = None
        if s.voice:
            await s.voice.disconnect()
            s.voice = None
        await interaction.response.send_message("⏹️ Stopped.", ephemeral=True)


class Music(commands.Cog):
    """🎵 Music — YouTube search, URLs, playlists, and Spotify → YouTube."""

    def __init__(self, bot):
        self.bot    = bot
        self.states = {}
        print("[Music] PyNaCl ready." if _check_nacl() else "[Music] ⚠️ PyNaCl missing.")

    def get_state(self, gid) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    async def ensure_voice(self, interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Join a voice channel first!", ephemeral=True)
            return False
        return True

    async def safe_connect(self, interaction, state) -> bool:
        if state.voice and state.voice.is_connected():
            if state.voice.channel != interaction.user.voice.channel:
                await state.voice.move_to(interaction.user.voice.channel)
            return True
        if not _check_nacl():
            await interaction.followup.send(
                "❌ PyNaCl/libsodium missing.\n"
                "Fix `nixpacks.toml`: `nixPkgs = [\"python311\", \"ffmpeg\", \"libsodium\"]` and redeploy.")
            return False
        try:
            state.voice = await interaction.user.voice.channel.connect(timeout=15.0, reconnect=True)
            return True
        except discord.ClientException as e:
            if "already connected" in str(e).lower():
                return True
            await interaction.followup.send(f"❌ Voice error: `{e}`")
            return False
        except Exception as e:
            if any(x in str(e).lower() for x in ["nacl", "sodium", "davey"]):
                await interaction.followup.send("❌ libsodium missing — fix nixpacks.toml and redeploy.")
            else:
                await interaction.followup.send(f"❌ Can't connect: `{e}`")
            return False

    # ── Two-pass song fetch ───────────────────────────────────────────────────
    async def fetch_song(self, query: str, requester) -> Song | None:
        # Spotify → yt-dlp native resolve or YouTube search
        is_spotify = "spotify.com" in query
        if is_spotify:
            search_q = spotify_to_search(query) or query
        elif query.startswith("http"):
            search_q = query
        else:
            search_q = f"ytsearch1:{query}"

        # Pass 1
        data = await _extract(YDL_SEARCH, search_q)
        if not data:
            # Fallback: if Spotify failed, search YouTube by the raw text
            if is_spotify:
                data = await _extract(YDL_SEARCH, f"ytsearch1:{query}")
            if not data:
                return None

        entry = data
        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                return None
            entry = entries[0]

        stream_url  = entry.get("url", "")
        webpage_url = entry.get("webpage_url") or entry.get("original_url", "")

        # Pass 2 — resolve direct audio stream if needed
        needs_p2 = (
            not stream_url
            or "youtube.com/watch" in stream_url
            or "youtu.be/" in stream_url
            or stream_url == webpage_url
        )
        if needs_p2 and webpage_url:
            d2 = await _extract(YDL_STREAM, webpage_url)
            if d2:
                e2 = d2
                if "entries" in d2:
                    lst = [x for x in d2["entries"] if x]
                    e2  = lst[0] if lst else d2
                stream_url = e2.get("url", stream_url)
                for k in ("title", "thumbnail", "duration", "channel", "uploader", "webpage_url"):
                    if e2.get(k):
                        entry[k] = e2[k]
                entry["url"] = stream_url

        if not entry.get("url"):
            return None
        return Song(entry, requester)

    async def fetch_playlist(self, url, requester) -> list:
        data = await _extract(YDL_FLAT, url)
        if not data or "entries" not in data:
            return []
        songs = []
        for e in data["entries"]:
            if not e:
                continue
            vid = e.get("url") or (f"https://www.youtube.com/watch?v={e['id']}" if e.get("id") else None)
            if not vid:
                continue
            songs.append(Song({
                "title": e.get("title", "Unknown"), "url": vid,
                "webpage_url": vid, "thumbnail": e.get("thumbnail", ""),
                "duration": e.get("duration", 0),
                "channel": e.get("channel") or e.get("uploader", "Unknown"),
            }, requester))
        return songs

    async def _resolve(self, song: Song) -> str:
        url = song.stream_url
        if not url or "youtube.com/watch" in url or "youtu.be/" in url:
            d = await _extract(YDL_STREAM, song.webpage_url)
            if d:
                r = d
                if "entries" in d:
                    lst = [x for x in d["entries"] if x]
                    r   = lst[0] if lst else d
                url = r.get("url", url)
                song.stream_url = url
        return url

    async def play_next(self, gid):
        state = self.get_state(gid)
        if not state.voice or not state.voice.is_connected():
            return

        if state.loop and state.current:
            song = state.current
        elif state.queue:
            song = state.queue.popleft()
            state.current = song
        else:
            state.current = None
            if state.text:
                try: await state.text.send("✅ Queue finished — leaving VC. 🌑")
                except Exception: pass
            try: await state.voice.disconnect()
            except Exception: pass
            state.voice = None
            return

        stream = await self._resolve(song)
        if not stream:
            if state.text:
                try: await state.text.send(f"❌ Skipping **{song.title}** — couldn't resolve stream.")
                except Exception: pass
            asyncio.run_coroutine_threadsafe(self.play_next(gid), self.bot.loop)
            return

        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS), volume=state.volume)
        except Exception as e:
            print(f"[Music] FFmpeg: {e}")
            asyncio.run_coroutine_threadsafe(self.play_next(gid), self.bot.loop)
            return

        def after(err):
            if err: print(f"[Music] After: {err}")
            asyncio.run_coroutine_threadsafe(self.play_next(gid), self.bot.loop)

        state.voice.play(source, after=after)
        if state.text:
            try: await state.text.send(embed=self._np_embed(song), view=PlayerView(self, gid))
            except Exception: pass

    def _np_embed(self, song: Song) -> discord.Embed:
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{song.title}]({song.webpage_url})",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="⏱ Duration",     value=song.duration_str(),    inline=True)
        embed.add_field(name="📺 Channel",      value=song.channel,           inline=True)
        embed.add_field(name="👤 Requested by", value=song.requester.mention, inline=True)
        if song.thumbnail: embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text="Eclipse Music 🌑")
        return embed

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song — YouTube search, URL, playlist, or Spotify link.")
    @app_commands.describe(query="Song name, YouTube URL, playlist URL, or Spotify link")
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.ensure_voice(interaction): return
        await interaction.response.defer()
        state = self.get_state(interaction.guild_id)
        state.text = interaction.channel
        if not await self.safe_connect(interaction, state): return

        # Playlist detection
        is_playlist = (
            ("youtube.com/playlist" in query or ("list=" in query and "watch" not in query))
            or SPOTIFY_PLAYLIST.search(query) or SPOTIFY_ALBUM.search(query)
        )
        if is_playlist:
            await interaction.followup.send("⏳ Loading playlist...")
            songs = await self.fetch_playlist(query, interaction.user)
            if not songs:
                await interaction.followup.send("❌ Couldn't load playlist.")
                return
            for s in songs: state.queue.append(s)
            if not state.voice.is_playing(): await self.play_next(interaction.guild_id)
            await interaction.followup.send(f"📋 Added **{len(songs)}** songs to the queue!")
            return

        await interaction.followup.send("🔍 Searching...")
        song = await self.fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send("❌ Couldn't find that song. Try a more specific name or a YouTube URL.")
            return

        if state.voice.is_playing() or state.voice.is_paused():
            state.queue.append(song)
            e = discord.Embed(title="➕ Added to Queue",
                              description=f"[{song.title}]({song.webpage_url})",
                              color=discord.Color.blurple())
            e.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
            e.add_field(name="Duration", value=song.duration_str(), inline=True)
            await interaction.followup.send(embed=e)
        else:
            state.current = song
            stream = await self._resolve(song)
            if not stream:
                await interaction.followup.send("❌ Couldn't resolve audio stream. Try another song.")
                return
            try:
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS), volume=state.volume)
            except Exception as e:
                await interaction.followup.send(f"❌ FFmpeg error: `{e}`")
                return

            def after(err):
                asyncio.run_coroutine_threadsafe(self.play_next(interaction.guild_id), self.bot.loop)

            state.voice.play(source, after=after)
            await interaction.followup.send(embed=self._np_embed(song), view=PlayerView(self, interaction.guild_id))

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        if not s.voice or not (s.voice.is_playing() or s.voice.is_paused()):
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        s.voice.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        if s.voice and s.voice.is_playing():
            s.voice.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        if s.voice and s.voice.is_paused():
            s.voice.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop music and clear the queue.")
    async def stop(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        s.queue.clear(); s.loop = False; s.current = None
        if s.voice:
            try: await s.voice.disconnect()
            except Exception: pass
            s.voice = None
        await interaction.response.send_message("⏹️ Stopped and cleared queue.")

    @app_commands.command(name="queue", description="View the music queue.")
    async def queue_cmd(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.purple())
        if s.current:
            embed.add_field(name="▶️ Now Playing",
                value=f"[{s.current.title}]({s.current.webpage_url}) ({s.current.duration_str()})", inline=False)
        if s.queue:
            lines = "\n".join(f"`{i+1}.` [{x.title}]({x.webpage_url}) — {x.duration_str()}"
                              for i, x in enumerate(list(s.queue)[:10]))
            embed.add_field(name=f"📋 Up Next ({len(s.queue)} songs)", value=lines, inline=False)
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the current song.")
    async def nowplaying(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        if not s.current:
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        await interaction.response.send_message(embed=self._np_embed(s.current))

    @app_commands.command(name="volume", description="Set playback volume (0–200).")
    @app_commands.describe(level="Volume 0–200")
    async def volume(self, interaction: discord.Interaction, level: int):
        s = self.get_state(interaction.guild_id)
        level = max(0, min(200, level))
        s.volume = level / 100
        if s.voice and s.voice.source: s.voice.source.volume = s.volume
        await interaction.response.send_message(f"🔊 Volume: **{level}%**")

    @app_commands.command(name="loop", description="Toggle loop.")
    async def loop(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        s.loop = not s.loop
        await interaction.response.send_message(f"🔁 Loop **{'enabled ✅' if s.loop else 'disabled ❌'}**.")

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction):
        s = self.get_state(interaction.guild_id)
        q = list(s.queue); random.shuffl