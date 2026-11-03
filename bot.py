import os
import certifi

# macOS SSL Certificate Fix
os.environ['SSL_CERT_FILE'] = certifi.where()

import re
import asyncio
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

TARGET_CHANNEL_NAME = "guild-research"
OFFICER_ROLE_NAME = "Officer"

# --- GLOBAL RESEARCH STATE ---
research_state = {
    "name": None,
    "mins_per_help": 44,          # Minutes shaved per member help (Default Lvl 6 = 44m)
    "finish_time": None,
    "timer_task": None
}

# --- GLOBAL ROADMAP PLANNER STATE ---
roadmap_plan = {
    "phase1": "Guild Shop Level 4",
    "phase2": "Guild EXP & Growth Level 6",
    "phase3": "Great Contributor Level 6 (If below Guild Lvl 4)"
}


def is_officer():
    """Check decorator to restrict commands strictly to the Officer role."""
    async def predicate(ctx):
        if not ctx.guild:
            return False
        role = discord.utils.get(ctx.guild.roles, name=OFFICER_ROLE_NAME)
        if role in ctx.author.roles or ctx.author.guild_permissions.administrator:
            return True
        await ctx.send(f"❌ Only members with the **@{OFFICER_ROLE_NAME}** role can use this command!")
        return False
    return commands.check(predicate)


def parse_time_input(time_str: str) -> int:
    """Parses time strings like '4d 11h 24m', '48h', '2d 5h', or '144h' into total seconds."""
    time_str = time_str.lower().strip()
    total_seconds = 0

    days = re.search(r'(\d+)\s*d', time_str)
    hours = re.search(r'(\d+)\s*h', time_str)
    minutes = re.search(r'(\d+)\s*m', time_str)

    if days or hours or minutes:
        if days:
            total_seconds += int(days.group(1)) * 86400
        if hours:
            total_seconds += int(hours.group(1)) * 3600
        if minutes:
            total_seconds += int(minutes.group(1)) * 60
        return total_seconds

    colon_match = re.search(r'(?:(\d+)d\s*)?(\d+):(\d+)', time_str)
    if colon_match:
        d = int(colon_match.group(1)) if colon_match.group(1) else 0
        h = int(colon_match.group(2))
        m = int(colon_match.group(3))
        return (d * 86400) + (h * 3600) + (m * 60)

    if time_str.isdigit():
        return int(time_str) * 3600

    return 0


async def send_guild_roadmap(channel):
    """Sends the Guild Progression Roadmap."""
    embed = discord.Embed(
        title="🏛️ Evitania Guild Progression Planner",
        description="Official guild research priorities roadmap:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🎯 Phase 1 (Active Priority)", value=f"**{roadmap_plan['phase1']}**", inline=False)
    embed.add_field(name="⏩ Phase 2 (Next Priority)", value=f"**{roadmap_plan['phase2']}**", inline=False)
    embed.add_field(name="⚡ Phase 3 (Contingency Route)", value=f"**{roadmap_plan['phase3']}**", inline=False)
    embed.set_footer(text="Officers can update roadmap steps using !setplan <phase1/phase2/phase3> <Text>")
    await channel.send(embed=embed)


async def start_countdown_loop(channel, role_ping):
    """Handles background sleep & 10m/5m/1m warnings."""
    try:
        now = datetime.now(timezone.utc)
        remaining_sec = int((research_state["finish_time"] - now).total_seconds())

        if remaining_sec <= 0:
            await channel.send(f"⚠️ Research **`{research_state['name']}`** is already finished or invalid time was entered.")
            return

        daily_saving_hours = (30 * research_state['mins_per_help']) // 60
        daily_saving_mins = (30 * research_state['mins_per_help']) % 60

        # Status Embed
        embed_start = discord.Embed(
            title="🔬 Guild Research Timer Set!",
            description=(
                f"• **Project Name:** `{research_state['name']}`\n"
                f"• **Help Cutdown Perk:** `{research_state['mins_per_help']}m / help` (-{daily_saving_hours}h {daily_saving_mins}m per 30 helps)\n"
                f"• **Estimated Completion:** <t:{int(research_state['finish_time'].timestamp())}:F> (<t:{int(research_state['finish_time'].timestamp())}:R>)\n\n"
                f"🚨 **Automated Pings:** Scheduled for 10m, 5m, and 1m before completion!"
            ),
            color=discord.Color.purple()
        )
        await channel.send(content=f"📢 Attention {role_ping}!", embed=embed_start)

        # Wait until 10 minutes remain
        time_to_10m = remaining_sec - 600
        if time_to_10m > 0:
            await asyncio.sleep(time_to_10m)

        # 10m Ping
        embed_10m = discord.Embed(
            title="⏳ 10-Minute Research Warning!",
            description=f"Research **`{research_state['name']}`** finishes in **10 minutes**!\nGet ready to queue the next research node.",
            color=discord.Color.gold()
        )
        await channel.send(content=f"🚨 {role_ping}", embed=embed_10m)

        # Wait 5 minutes
        await asyncio.sleep(300)

        # 5m Ping
        embed_5m = discord.Embed(
            title="⏳ 5-Minute Research Warning!",
            description=f"Research **`{research_state['name']}`** finishes in **5 minutes**!\nLog in now to prepare guild contribution funds.",
            color=discord.Color.orange()
        )
        await channel.send(content=f"🚨 {role_ping}", embed=embed_5m)

        # Wait 4 minutes
        await asyncio.sleep(240)

        # 1m Ping
        embed_1m = discord.Embed(
            title="🚨 1-Minute Final Warning!",
            description=f"Research **`{research_state['name']}`** finishes in **1 MINUTE**!\nStand by at the Guild Research tab in-game!",
            color=discord.Color.red()
        )
        await channel.send(content=f"🚨 {role_ping}", embed=embed_1m)

        # Final 60s
        await asyncio.sleep(60)

        # Finish Ping
        embed_done = discord.Embed(
            title="🎉 GUILD RESEARCH FINISHED!",
            description=f"Research **`{research_state['name']}`** is completed! Please check `!plan` for the next building upgrade.",
            color=discord.Color.green()
        )
        await channel.send(content=f"📢 {role_ping}", embed=embed_done)

    except asyncio.CancelledError:
        print("ℹ️ Timer restarted or updated by Officer.")


# ---------------------------------------------------------
# GUILD BOT COMMANDS
# ---------------------------------------------------------

@bot.command(name="help")
async def help_command(ctx):
    """Displays a list of all available commands."""
    embed = discord.Embed(
        title="📜 Evitania Guild Bot Commands",
        description="Commands for managing guild research timers and officer pings:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="`!setresearch <\"Name\"> <RemainingTime>` *(Officer Only)*",
        value=(
            "Sets new research timer using remaining in-game time directly.\n"
            "*Examples:*\n"
            "• `!setresearch \"New Heights Lvl 6\" 4d 11h 24m`\n"
            "• `!setresearch \"Guild Growth Lvl 4\" 1d 8h`\n"
            "• `!setresearch \"Expanded Stock Lvl 1\" 48h`"
        ),
        inline=False
    )
    embed.add_field(
        name="`!setperk <MinsPerHelp>` *(Officer Only)*",
        value=(
            "Updates minutes shaved per help across calculations.\n"
            "*Examples:*\n"
            "• `!setperk 44` (Level 6 Perk)\n"
            "• `!setperk 48` (Level 7 Perk)"
        ),
        inline=False
    )
    embed.add_field(
        name="`!setplan <phase1/phase2/phase3> <New Goal>` *(Officer Only)*",
        value=(
            "Updates the guild roadmap priorities card.\n"
            "*Example:* `!setplan phase1 Guild EXP & Growth Level 6`"
        ),
        inline=False
    )
    embed.add_field(
        name="`!plan`",
        value="Displays the active guild progression planner and roadmap card.",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name="commands")
async def commands_alias(ctx):
    """Alias for !help."""
    await help_command(ctx)


@bot.command(name="setresearch")
@is_officer()
async def setresearch(ctx, name: str, *, time_input: str):
    """Sets active research project and remaining in-game time."""
    remaining_seconds = parse_time_input(time_input)

    if remaining_seconds <= 0:
        await ctx.send("❌ Invalid time format! Example usage:\n`!setresearch \"Guild Growth Lvl 4\" 2d 5h` or `!setresearch \"New Heights Lvl 6\" 4d 11h 24m`")
        return

    if research_state["timer_task"] and not research_state["timer_task"].done():
        research_state["timer_task"].cancel()

    research_state["name"] = name
    research_state["finish_time"] = datetime.now(timezone.utc) + timedelta(seconds=remaining_seconds)

    role = discord.utils.get(ctx.guild.roles, name=OFFICER_ROLE_NAME)
    role_ping = role.mention if role else f"@{OFFICER_ROLE_NAME}"

    task = asyncio.create_task(start_countdown_loop(ctx.channel, role_ping))
    research_state["timer_task"] = task


@bot.command(name="setperk")
@is_officer()
async def setperk(ctx, mins: int):
    """Updates minutes reduced per help."""
    research_state["mins_per_help"] = mins
    daily_saving = (30 * mins) // 60
    await ctx.send(f"⚡ Research perk set to **{mins} mins/help**! Guild will save **~{daily_saving} hours per day** from 30 member helps.")


@bot.command(name="setplan")
@is_officer()
async def setplan(ctx, phase: str, *, new_goal: str):
    """Updates roadmap phases. Usage: !setplan phase1 <New Goal>"""
    phase_key = phase.lower().strip()
    if phase_key in roadmap_plan:
        roadmap_plan[phase_key] = new_goal
        await ctx.send(f"✅ Updated **{phase_key.upper()}** objective to: **{new_goal}**")
        await send_guild_roadmap(ctx.channel)
    else:
        await ctx.send("⚠️ Invalid phase selection! Use `phase1`, `phase2`, or `phase3`.\n*Example:* `!setplan phase1 Guild Shop Level 5`")


@bot.command(name="plan")
async def plan_command(ctx):
    """Displays the guild roadmap card."""
    await send_guild_roadmap(ctx.channel)


@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="Evitania Guild Assistant | !help"))

    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=TARGET_CHANNEL_NAME) or guild.text_channels[0]
        await send_guild_roadmap(channel)


# Paste your Discord Bot Token inside quotes below:
import os

bot.run(os.environ.get("BOT_TOKEN"))