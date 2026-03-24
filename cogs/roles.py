import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict


class Roles(commands.Cog):
    """🏷️ Reaction roles, auto roles, and role management."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> { message_id -> { emoji -> role_id } }
        self.reaction_roles = defaultdict(lambda: defaultdict(dict))
        # guild_id -> role_id
        self.auto_roles = {}

    @app_commands.command(name="reactionroles",
                          description="Add a reaction role to a message.")
    @app_commands.describe(
        message_id="ID of the message",
        emoji="The emoji to react with",
        role="The role to assign"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionroles(self, interaction: discord.Interaction,
                            message_id: str, emoji: str, role: discord.Role):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return

        self.reaction_roles[interaction.guild_id][msg_id][emoji] = role.id

        try:
            msg = await interaction.channel.fetch_message(msg_id)
            await msg.add_reaction(emoji)
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ React with {emoji} on message `{message_id}` to get {role.mention}.",
            ephemeral=True)

    @app_commands.command(name="removereactionrole",
                          description="Remove a reaction role from a message.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removereactionrole(self, interaction: discord.Interaction,
                                 message_id: str, emoji: str):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return

        guild_rr = self.reaction_roles[interaction.guild_id]
        if msg_id in guild_rr and emoji in guild_rr[msg_id]:
            del guild_rr[msg_id][emoji]
            await interaction.response.send_message(
                f"✅ Removed reaction role for {emoji} on `{message_id}`.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ No reaction role found for that emoji/message.", ephemeral=True)

    @app_commands.command(name="listreactionroles",
                          description="List all reaction roles in this server.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def listreactionroles(self, interaction: discord.Interaction):
        guild_rr = self.reaction_roles[interaction.guild_id]
        if not guild_rr:
            await interaction.response.send_message("No reaction roles set up.", ephemeral=True)
            return
        embed = discord.Embed(title="🏷️ Reaction Roles", color=discord.Color.purple())
        for msg_id, emojis in guild_rr.items():
            lines = []
            for emoji, role_id in emojis.items():
                role = interaction.guild.get_role(role_id)
                lines.append(f"{emoji} → {role.mention if role else f'Role {role_id}'}")
            embed.add_field(name=f"Message {msg_id}", value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="autorole",
                          description="Set a role to auto-assign to all new members.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        if role:
            self.auto_roles[interaction.guild_id] = role.id
            await interaction.response.send_message(
                f"✅ {role.mention} will be auto-assigned to new members.")
        else:
            self.auto_roles.pop(interaction.guild_id, None)
            await interaction.response.send_message("✅ Auto-role disabled.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        guild_rr = self.reaction_roles.get(payload.guild_id, {})
        msg_rr = guild_rr.get(payload.message_id, {})
        emoji_str = str(payload.emoji)
        role_id = msg_rr.get(emoji_str)
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)
        if member and role:
            try:
                await member.add_roles(role, reason="Reaction Role")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        guild_rr = self.reaction_roles.get(payload.guild_id, {})
        msg_rr = guild_rr.get(payload.message_id, {})
        emoji_str = str(payload.emoji)
        role_id = msg_rr.get(emoji_str)
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)
        if member and role:
            try:
                await member.remove_roles(role, reason="Reaction Role Removed")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_id = self.auto_roles.get(member.guild.id)
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto Role")
                except discord.Forbidden:
                    pass


async def setup(bot):
    await bot.add_cog(Roles(bot))
