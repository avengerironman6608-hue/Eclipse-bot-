import discord
from discord.ext import commands
from discord import app_commands
import datetime


class Welcome(commands.Cog):
    """👋 Standalone welcome/goodbye message customization."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> config dict
        self.configs = {}

    def get_config(self, guild_id: int) -> dict:
        return self.configs.setdefault(guild_id, {
            "welcome_channel": None,
            "goodbye_channel": None,
            "welcome_message": "Welcome {mention} to **{server}**! You are member #{count}. 🌑",
            "goodbye_message": "**{name}** has left **{server}**. We now have {count} members.",
            "dm_welcome": False,
            "dm_message": "Welcome to **{server}**! Check out the rules channel. 🌑",
        })

    def format_message(self, template: str, member: discord.Member) -> str:
        return template.format(
            mention=member.mention,
            name=str(member),
            display=member.display_name,
            server=member.guild.name,
            count=member.guild.member_count,
            id=member.id,
        )

    @app_commands.command(name="welcomeset",
                          description="Configure the welcome system.")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcomeset(self, interaction: discord.Interaction,
                         channel: discord.TextChannel = None,
                         message: str = None):
        config = self.get_config(interaction.guild_id)
        if channel:
            config["welcome_channel"] = channel.id
        if message:
            config["welcome_message"] = message

        embed = discord.Embed(title="✅ Welcome Config Updated", color=discord.Color.green())
        ch_id = config.get("welcome_channel")
        ch = interaction.guild.get_channel(ch_id) if ch_id else None
        embed.add_field(name="Channel", value=ch.mention if ch else "Not set", inline=True)
        embed.add_field(name="Message", value=config["welcome_message"][:200], inline=False)
        embed.add_field(
            name="Variables",
            value="`{mention}` `{name}` `{display}` `{server}` `{count}` `{id}`",
            inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="goodbyeset",
                          description="Configure the goodbye message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def goodbyeset(self, interaction: discord.Interaction,
                         channel: discord.TextChannel = None,
                         message: str = None):
        config = self.get_config(interaction.guild_id)
        if channel:
            config["goodbye_channel"] = channel.id
        if message:
            config["goodbye_message"] = message
        await interaction.response.send_message("✅ Goodbye config updated.")

    @app_commands.command(name="testwelcome",
                          description="Test the welcome message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def testwelcome(self, interaction: discord.Interaction):
        await self._send_welcome(interaction.user)
        await interaction.response.send_message("✅ Test welcome message sent!", ephemeral=True)

    async def _send_welcome(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        ch_id = config.get("welcome_channel")
        channel = member.guild.get_channel(ch_id) if ch_id else None

        if not channel:
            # fallback to a channel named welcome
            channel = (discord.utils.get(member.guild.text_channels, name="welcome") or
                       discord.utils.get(member.guild.text_channels, name="👋│welcome"))

        if channel:
            msg = self.format_message(config["welcome_message"], member)
            embed = discord.Embed(
                description=msg,
                color=discord.Color.purple(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Eclipse Bot • {member.guild.name}")
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

        # DM welcome
        if config.get("dm_welcome"):
            try:
                dm_msg = config["dm_message"].format(server=member.guild.name)
                await member.send(dm_msg)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        ch_id = config.get("goodbye_channel") or config.get("welcome_channel")
        channel = member.guild.get_channel(ch_id) if ch_id else None
        if not channel:
            channel = (discord.utils.get(member.guild.text_channels, name="welcome") or
                       discord.utils.get(member.guild.text_channels, name="👋│welcome"))
        if channel:
            msg = self.format_message(config["goodbye_message"], member)
            embed = discord.Embed(
                description=msg,
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.set_footer(text=f"Eclipse Bot • {member.guild.name}")
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))

