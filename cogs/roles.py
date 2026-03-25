import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reaction_roles = defaultdict(lambda: defaultdict(dict))
        self.auto_roles = {}

    @app_commands.command(name="reactionrole", description="Add reaction role")
    async def reactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            msg_id = int(message_id)
        except:
            await interaction.response.send_message("❌ Invalid message ID", ephemeral=True)
            return

        self.reaction_roles[interaction.guild_id][msg_id][emoji] = role.id

        try:
            msg = await interaction.channel.fetch_message(msg_id)
            await msg.add_reaction(emoji)
        except:
            pass

        await interaction.response.send_message("✅ Reaction role added", ephemeral=True)

    @app_commands.command(name="autorole", description="Set autorole")
    async def autorole(self, interaction: discord.Interaction, role: discord.Role):
        self.auto_roles[interaction.guild_id] = role.id
        await interaction.response.send_message(f"✅ Autorole set to {role.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role_id = self.auto_roles.get(member.guild.id)
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role_id = self.reaction_roles[payload.guild_id][payload.message_id].get(str(payload.emoji))
        if not role_id:
            return

        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)

        if member and role:
            try:
                await member.add_roles(role)
            except:
                pass


async def setup(bot):
    cog = Roles(bot)
    await bot.add_cog(cog)
