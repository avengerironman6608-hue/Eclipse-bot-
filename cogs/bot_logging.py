import discord
from discord.ext import commands
from discord import app_commands
import datetime


class Logging(commands.Cog):
    """📋 Comprehensive server event logging."""

    def __init__(self, bot):
        self.bot = bot
        self.log_channels = {}
        self.enabled_events = {}

    ALL_EVENTS = {
        "message_delete", "message_edit", "member_join", "member_leave",
        "member_ban", "member_unban", "role_create", "role_delete",
        "channel_create", "channel_delete", "voice_join", "voice_leave",
        "nickname_change", "role_add", "role_remove",
    }

    def get_log_channel(self, guild_id: int):
        ch_id = self.log_channels.get(guild_id)
        if not ch_id:
            return None
        return self.bot.get_channel(ch_id)

    def is_enabled(self, guild_id: int, event: str) -> bool:
        events = self.enabled_events.get(guild_id)
        if events is None:
            return True
        return event in events

    async def send_log(self, guild_id: int, event: str, embed: discord.Embed):
        if not self.log_channels.get(guild_id):
            return
        if not self.is_enabled(guild_id, event):
            return
        ch = self.get_log_channel(guild_id)
        if ch:
            try:
                await ch.send(embed=embed)
            except discord.Forbidden:
                pass

    @app_commands.command(name="setlogchannel", description="Set the server log channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlogchannel(self, interaction: discord.Interaction,
                            channel: discord.TextChannel):
        self.log_channels[interaction.guild_id] = channel.id
        await interaction.response.send_message(f"✅ Log channel set to {channel.mention}.")

    @app_commands.command(name="togglelog",
                          description="Enable or disable a specific log event.")
    @app_commands.describe(event="Event type to toggle")
    @app_commands.choices(event=[app_commands.Choice(name=e, value=e) for e in sorted([
        "message_delete", "message_edit", "member_join", "member_leave",
        "member_ban", "role_create", "channel_create", "voice_join"
    ])])
    @app_commands.checks.has_permissions(administrator=True)
    async def togglelog(self, interaction: discord.Interaction, event: str):
        if interaction.guild_id not in self.enabled_events:
            self.enabled_events[interaction.guild_id] = set(self.ALL_EVENTS)
        events = self.enabled_events[interaction.guild_id]
        if event in events:
            events.remove(event)
            await interaction.response.send_message(f"✅ Logging for `{event}` **disabled**.")
        else:
            events.add(event)
            await interaction.response.send_message(f"✅ Logging for `{event}` **enabled**.")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        content = message.content[:500] if message.content else "(no text)"
        embed.add_field(name="Content", value=f"```{content}```", inline=False)
        await self.send_log(message.guild.id, "message_delete", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=f"```{before.content[:250]}```", inline=False)
        embed.add_field(name="After", value=f"```{after.content[:250]}```", inline=False)
        embed.add_field(name="Jump", value=f"[View Message]({after.jump_url})", inline=False)
        await self.send_log(before.guild.id, "message_edit", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="✅ Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(
            name="Account Age", value=member.created_at.strftime("%b %d, %Y"), inline=True)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await self.send_log(member.guild.id, "member_join", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="👋 Member Left",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=f"{member} (`{member.id}`)", inline=True)
        roles = [r.mention for r in member.roles if r != member.guild.default_role]
        embed.add_field(name="Roles", value=" ".join(roles[:5]) or "None", inline=False)
        await self.send_log(member.guild.id, "member_leave", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=True)
        await self.send_log(guild.id, "member_ban", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="✅ Member Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=True)
        await self.send_log(guild.id, "member_unban", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(
            title="🏷️ Role Created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Role", value=role.mention, inline=True)
        await self.send_log(role.guild.id, "role_create", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(
            title="🏷️ Role Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Role", value=role.name, inline=True)
        await self.send_log(role.guild.id, "role_delete", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="📢 Channel Created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(
            name="Channel",
            value=channel.mention if hasattr(channel, 'mention') else channel.name,
            inline=True)
        embed.add_field(name="Type", value=str(channel.type), inline=True)
        await self.send_log(channel.guild.id, "channel_create", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="📢 Channel Deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Channel", value=channel.name, inline=True)
        await self.send_log(channel.guild.id, "channel_delete", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            embed = discord.Embed(
                title="🔊 Joined Voice",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow())
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=after.channel.name, inline=True)
            await self.send_log(member.guild.id, "voice_join", embed)
        elif before.channel and not after.channel:
            embed = discord.Embed(
                title="🔇 Left Voice",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow())
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=before.channel.name, inline=True)
            await self.send_log(member.guild.id, "voice_leave", embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))
