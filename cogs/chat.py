import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
import re
import os

OWNER_ID = int(os.getenv("OWNER_ID", "1247446254938624121"))

GREETINGS = ["hi", "hello", "hey", "sup", "yo", "hiya", "howdy", "greetings"]
GOODBYE = ["bye", "goodbye", "cya", "later", "seeya", "farewell", "peace"]
THANKS = ["thanks", "thank you", "thx", "ty", "appreciate", "cheers"]
BOT_QUESTIONS = ["are you a bot", "are you real", "are you human", "are you ai"]

GREETING_RESPONSES = [
    "Hey there {user}! 🌑 What's up?",
    "Hello {user}! Welcome to the Eclipse! ✨",
    "Yo {user}! 🌑 Good to see you!",
    "Hey hey {user}! What can I do for you? 😎",
    "Greetings, {user}! The Eclipse awaits 🌑",
]

OWNER_GREETING_RESPONSES = [
    "Welcome back, my creator {user}! 🌑👑 At your service!",
    "The boss is here! 👑 What do you need, {user}?",
    "Greetings, **Supreme Commander** {user}! 🌑✨ How can I serve you?",
]

GOODBYE_RESPONSES = [
    "See you around, {user}! 🌑",
    "Catch you later, {user}! ✨",
    "Bye {user}! Come back soon! 🌙",
    "Later {user}! Stay cool 😎",
]

THANKS_RESPONSES = [
    "No problem, {user}! 🌑 Always here to help!",
    "Anytime, {user}! That's what I'm here for ✨",
    "You're welcome, {user}! 😄",
    "Happy to help, {user}! 🌙",
]

FUN_FACTS = [
    "🌑 A solar eclipse can only happen during a new moon.",
    "⭐ The Sun is ~400× wider than the Moon but also ~400× farther away — that's why they appear the same size!",
    "🌍 A total solar eclipse moves at about 1,700 km/h across Earth's surface.",
    "🔭 The word 'eclipse' comes from the Greek 'ekleipsis' meaning abandonment.",
    "🌙 The Moon drifts from Earth at about 3.8 cm per year.",
    "☀️ The Sun's corona can only be seen during a total solar eclipse.",
    "🪐 Jupiter has 95 known moons!",
    "🌌 The Milky Way is estimated to have 100–400 billion stars.",
    "🚀 It would take over 9 years to drive to the Moon at highway speed.",
    "💫 There are more stars in the universe than grains of sand on all Earth's beaches.",
]

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything! 😄"),
    ("What do you call fake spaghetti?", "An impasta! 🍝"),
    ("Why did the robot go on vacation?", "To recharge its batteries! 🤖"),
    ("I told my computer I needed a break.", "Now it won't stop sending me vacation ads! 💻"),
    ("Why don't programmers like nature?", "It has too many bugs! 🐛"),
    ("What did the ocean say to the beach?", "Nothing, it just waved! 🌊"),
    ("Why did the moon skip dinner?", "Because it was already full! 🌕"),
    ("How do astronomers organize a party?", "They planet! 🪐"),
]

MAGIC_8_BALL = [
    "✅ It is certain.",
    "✅ Without a doubt.",
    "✅ Yes, definitely.",
    "✅ You may rely on it.",
    "✅ As I see it, yes.",
    "✅ Most likely.",
    "🤔 Reply hazy, try again.",
    "🤔 Ask again later.",
    "🤔 Cannot predict now.",
    "❌ Don't count on it.",
    "❌ My reply is no.",
    "❌ Very doubtful.",
    "❌ Outlook not so good.",
]


class Chat(commands.Cog):
    """💬 Chat interactions, fun commands, and conversational responses."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.lower().strip()
        bot_mentioned = self.bot.user in message.mentions
        name_used = "eclipse" in content

        if not (bot_mentioned or name_used):
            return

        clean = re.sub(r"<@!?\d+>", "", content).strip()
        clean = clean.replace("eclipse", "").strip()

        is_owner = message.author.id == OWNER_ID

        # Greeting
        if any(g in clean for g in GREETINGS) or clean == "":
            if is_owner:
                response = random.choice(OWNER_GREETING_RESPONSES).format(
                    user=message.author.mention)
            else:
                response = random.choice(GREETING_RESPONSES).format(
                    user=message.author.mention)
            await message.channel.send(response)
            return

        # Goodbye
        if any(g in clean for g in GOODBYE):
            await message.channel.send(
                random.choice(GOODBYE_RESPONSES).format(user=message.author.mention))
            return

        # Thanks
        if any(t in clean for t in THANKS):
            await message.channel.send(
                random.choice(THANKS_RESPONSES).format(user=message.author.mention))
            return

        # Bot identity
        if any(q in clean for q in BOT_QUESTIONS):
            await message.channel.send(
                f"I'm **Eclipse Bot** 🌑 — your all-in-one Discord assistant! "
                f"I can moderate, play music, level up members, and much more. Try `/help`!")
            return

        # How are you
        if "how are you" in clean or "how r u" in clean:
            responses = [
                "I'm doing great, thanks for asking! 🌑 Ready to serve the server!",
                "Eclipse-powered and fully operational! ✨ How about yourself?",
                "Feeling astronomical! 🌙 What can I help you with?",
            ]
            await message.channel.send(random.choice(responses))
            return

        # What can you do
        if "what can you do" in clean or "help" in clean:
            await message.channel.send(
                f"I can do a lot, {message.author.mention}! 🌑\n"
                "Use `/help` for a full list of commands, or try:\n"
                "🎵 `/play` — Music\n"
                "📈 `/rank` — Check your level\n"
                "🛡️ `/automod` — AutoMod settings\n"
                "🔨 `/ban`, `/kick`, `/warn` — Moderation\n"
                "🎲 `/8ball`, `/joke`, `/poll` — Fun stuff!")
            return

        # Default fallback
        fallbacks = [
            f"Interesting, {message.author.mention}! 🤔 Not sure what you mean — try `/help`.",
            f"Hmm, {message.author.mention}, I didn't catch that. Try `/help`! 🌑",
            f"🌑 I'm here, {message.author.mention}! Need something? Try `/help`.",
        ]
        await message.channel.send(random.choice(fallbacks))

    # ─── Fun Commands ──────────────────────────────────────────────────────────

    @app_commands.command(name="8ball", description="Ask the Magic 8-Ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answer = random.choice(MAGIC_8_BALL)
        embed = discord.Embed(color=discord.Color.purple())
        embed.add_field(name="❓ Question", value=question, inline=False)
        embed.add_field(name="🎱 Answer", value=answer, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction):
        setup, punchline = random.choice(JOKES)
        embed = discord.Embed(color=discord.Color.yellow())
        embed.add_field(name="😄 Setup", value=setup, inline=False)
        embed.add_field(name="🥁 Punchline", value=f"||{punchline}||", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="fact", description="Get a random space fact.")
    async def fact(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔭 Space Fact",
            description=random.choice(FUN_FACTS),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roll", description="Roll a dice (e.g. d20, d6).")
    @app_commands.describe(sides="Number of sides (default: 6)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        result = random.randint(1, max(2, sides))
        await interaction.response.send_message(f"🎲 You rolled a **{result}** (d{sides})")

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads 🪙", "Tails 🪙"])
        await interaction.response.send_message(f"The coin landed on: **{result}**!")

    @app_commands.command(name="choose",
                          description="Let Eclipse choose between options.")
    @app_commands.describe(options="Comma-separated options (e.g. pizza,tacos,sushi)")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            await interaction.response.send_message(
                "❌ Please provide at least 2 options separated by commas.", ephemeral=True)
            return
        picked = random.choice(choices)
        await interaction.response.send_message(f"🌑 I choose: **{picked}**!")

    @app_commands.command(name="poll", description="Create a poll.")
    @app_commands.describe(
        question="Poll question",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3 (optional)",
        option4="Option 4 (optional)"
    )
    async def poll(self, interaction: discord.Interaction, question: str,
                   option1: str, option2: str,
                   option3: str = None, option4: str = None):
        options = [opt for opt in [option1, option2, option3, option4] if opt]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        embed = discord.Embed(
            title=f"📊 {question}",
            description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)),
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"Poll by {interaction.user.display_name} | React to vote!")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            try:
                await msg.add_reaction(emojis[i])
            except Exception:
                pass

    @app_commands.command(name="avatar", description="View a member's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar", color=discord.Color.purple())
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="View information about a member.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed = discord.Embed(
            title=f"👤 {member}",
            color=member.color,
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="Joined Server",
            value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "Unknown",
            inline=True)
        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles[:10]) or "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="View server information.")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(
            title=f"🌑 {g.name}",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(g.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Boosts", value=str(g.premium_subscription_count), inline=True)
        embed.add_field(name="Created", value=g.created_at.strftime("%b %d, %Y"), inline=True)
        embed.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="View all Eclipse Bot commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌑 Eclipse Bot — Command Help",
            description="Here's a full overview of all available commands:",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(
            name="🔨 Moderation",
            value="`/ban` `/kick` `/warn` `/timeout` `/untimeout` `/softban` "
                  "`/purge` `/lock` `/unlock` `/slowmode` `/nick` `/addrole` `/removerole`",
            inline=False)
        embed.add_field(
            name="🛡️ AutoMod",
            value="`/automod` `/automod_set` `/automod_logchannel` `/addword` `/removeword`",
            inline=False)
        embed.add_field(
            name="📈 Leveling",
            value="`/rank` `/leaderboard` `/setxp` `/addxp` `/resetxp` "
                  "`/levelrole` `/levelchannel`",
            inline=False)
        embed.add_field(
            name="🎵 Music",
            value="`/play` `/skip` `/pause` `/resume` `/stop` `/queue` "
                  "`/nowplaying` `/volume` `/loop` `/shuffle` `/remove` `/disconnect`",
            inline=False)
        embed.add_field(
            name="🚀 Onboarding",
            value="`/setup` `/setwelcome` `/setmemberrole`",
            inline=False)
        embed.add_field(
            name="🏷️ Roles",
            value="`/reactionroles` `/removereactionrole` `/listreactionroles` `/autorole`",
            inline=False)
        embed.add_field(
            name="📋 Logging",
            value="`/setlogchannel` `/togglelog`",
            inline=False)
        embed.add_field(
            name="🔧 Utility",
            value="`/ping` `/botinfo` `/embed` `/announce` `/snipe`",
            inline=False)
        embed.add_field(
            name="💬 Fun & Chat",
            value="`/8ball` `/joke` `/fact` `/roll` `/coinflip` `/choose` "
                  "`/poll` `/avatar` `/userinfo` `/serverinfo`",
            inline=False)
        embed.set_footer(text="Eclipse Bot 🌑 | Say 'eclipse' or @mention me to chat!")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Chat(bot))
