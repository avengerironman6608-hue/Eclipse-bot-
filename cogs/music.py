import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import defaultdict, deque
import datetime
import random

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

# Removed postprocessors — we stream directly, no download needed
FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    ),
    "options": "-vn",
}


class Song:
    def __init__(self, data, requester):
        self.title = data.get("title", "Unknown")
        self.url = data.get("url") or data.get("webpage_url", "")
        self.webpage_url = data.get("webpage_url", "")
        self.thumbnail = data.get("thumbnail", "")
        self.duration = data.get("duration") or 0
        self.requester = requester
        self.channel = data.get("channel") or data.get("uploader", "Unknown")

    def duration_str(self):
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


class GuildMusicState:
    def __init__(self):
        self.queue: deque = deque()
        self.voice_client: discord.VoiceClient = None
        self.current: Song = None
        self.loop = False
        self.volume = 0.5
        self.skip_votes = set()
        self.text_channel: discord.TextChannel = None


class Music(commands.Cog):
    """🎵 Full-featured music player — play, queue, skip, loop, volume & more."""

    def __init__(self, bot):
        self.bot = bot
        self.states: dict = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        return self.states.setdefault(guild_id, GuildMusicState())

    async def ensure_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel first!", ephemeral=True)
            return False
        return True

    async def fetch_song(self, query: str, requester) -> Song | None:
        loop = asyncio.get_event_loop()
        ydl_opts = dict(YDL_OPTIONS)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not query.startswith("http"):
                query = f"ytsearch:{query}"
            try:
                data = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(query, download=False))
                if not data:
                    return None
                if "entries" in data:
                    data = data["entries"][0]
                return Song(data, requester)
            except Exception as e:
                print(f"[Music] Error fetching song: {e}")
                return None

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
                    await state.text_channel.send("✅ Queue finished. Leaving voice channel.")
                except Exception:
                    pass
            await state.voice_client.disconnect()
            state.voice_client = None
            return

        try:
            source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
        except Exception as e:
            print(f"[Music] Source error: {e}")
            if state.text_channel:
                await state.text_channel.send(f"❌ Couldn't play that track. Skipping...")
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
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{song.title}]({song.webpage_url})",
                color=discord.Color.purple(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Duration", value=song.duration_str(), inline=True)
            embed.add_field(name="Channel", value=song.channel, inline=True)
            embed.add_field(name="Requested by", value=song.requester.mention, inline=True)
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            try:
                await state.text_channel.send(embed=embed)
            except Exception:
                pass

    @app_commands.command(name="play", description="Play a song or add it to the queue.")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        if not await self.ensure_voice(interaction):
            return
        await interaction.response.defer()

        state = self.get_state(interaction.guild_id)
        state.text_channel = interaction.channel

        # Connect or move to voice channel
        if not state.voice_client or not state.voice_client.is_connected():
            try:
                state.voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"❌ Couldn't connect to voice: {e}")
                return

        song = await self.fetch_song(query, interaction.user)
        if not song:
            await interaction.followup.send("❌ Could not find that song. Try a different search.")
            return

        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.queue.append(song)
            embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"[{song.title}]({song.webpage_url})",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Position", value=str(len(state.queue)), inline=True)
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

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{song.title}]({song.webpage_url})",
                color=discord.Color.purple()
            )
            embed.add_field(name="Duration", value=song.duration_str(), inline=True)
            embed.add_field(name="Requested by", value=song.requester.mention, inline=True)
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            await interaction.followup.send(embed=embed)

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
        if state.voice_client:
            await state.voice_client.disconnect()
            state.voice_client = None
        state.current = None
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
                inline=False
            )
        if state.queue:
            queue_list = "\n".join(
                f"`{i+1}.` [{s.title}]({s.webpage_url}) — {s.duration_str()}"
                for i, s in enumerate(list(state.queue)[:10])
            )
            embed.add_field(
                name=f"📋 Up Next ({len(state.queue)} songs)",
                value=queue_list, inline=False)
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set the playback volume (0–200).")
    async def volume(self, interaction: discord.Interaction, level: int):
        state = self.get_state(interaction.guild_id)
        level = max(0, min(200, level))
        state.volume = level / 100
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**.")

    @app_commands.command(name="loop", description="Toggle queue loop.")
    async def loop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.loop = not state.loop
        await interaction.response.send_message(
            f"🔁 Loop **{'enabled' if state.loop else 'disabled'}**.")

    @app_commands.command(name="nowplaying", description="Show the current song.")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.current:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        s = state.current
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{s.title}]({s.webpage_url})",
            color=discord.Color.purple()
        )
        embed.add_field(name="Duration", value=s.duration_str(), inline=True)
        embed.add_field(name="Requested by", value=s.requester.mention, inline=True)
        if s.thumbnail:
            embed.set_thumbnail(url=s.thumbnail)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)
        await interaction.response.send_message("🔀 Queue shuffled!")

    @app_commands.command(name="remove", description="Remove a song from the queue by position.")
    async def remove(self, interaction: discord.Interaction, position: int):
        state = self.get_state(interaction.guild_id)
        queue_list = list(state.queue)
        if 1 <= position <= len(queue_list):
            removed = queue_list.pop(position - 1)
            state.queue = deque(queue_list)
            await interaction.response.send_message(
                f"🗑️ Removed **{removed.title}** from the queue.")
        else:
            await interaction.response.send_message("❌ Invalid position.", ephemeral=True)

    @app_commands.command(name="disconnect", description="Disconnect the bot from voice.")
    async def disconnect(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if state.voice_client:
            await state.voice_client.disconnect()
            state.voice_client = None
            state.current = None
            state.queue.clear()
            await interaction.response.send_message("👋 Disconnected from voice channel.")
        else:
            await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-disconnect when alone in VC."""
        if member.bot:
            return
        guild_id = member.guild.id
        state = self.states.get(guild_id)
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


async def setup(bot):
    await bot.add_cog(Music(bot))
