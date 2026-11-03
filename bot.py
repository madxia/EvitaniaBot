import os
import certifi
from aiohttp import web

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
    "target_time": None,
    "helps_applied": 0,
    "mins_per_help": 44,
    "timer_task": None
}

# --- GLOBAL ROADMAP STATE ---
roadmap_state = {
    "phase1": "Guild EXP & Growth Level 6",
    "phase2": "New Heights Level 6",
    "phase3": "Expanded Stock Level 1"
}

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "0s"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0:
        parts.append(f"{seconds}s")
    return " ".join(parts)

def parse_time_input(time_str):
    pattern = r'(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?'
    match = re.fullmatch(pattern, time_str.strip())
    if not match or not any(match.groups()):
        return None
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

async def send_guild_roadmap(channel):
    embed = discord.Embed(
        title="📜 Evitania Guild Progression Roadmap",
        description="Current priorities for guild research and development:",
        color=discord.Color.blue()
    )
    embed.add_field(name="📌 Phase 1 (Immediate)", value=f"`{roadmap_state['phase1']}`", inline=False)
    embed.add_field(name="🚀 Phase 2 (Next Up)", value=f"`{roadmap_state['phase2']}`", inline=False)
    embed.add_field(name="🔮 Phase 3 (Future Goal)", value=f"`{roadmap_state['phase3']}`", inline=False)
    embed.set_footer(text="Updated by Officers • Use !setplan to update goals")
    await channel.send(embed=embed)

async def start_research_timer(ctx, name, remaining_seconds):
    global research_state
    if research_state["timer_task"]:
        research_state["timer_task"].cancel()

    target_time = datetime.now(timezone.utc) + timedelta(seconds=remaining_seconds)
    research_state["name"] = name
    research_state["target_time"] = target_time
    research_state["helps_applied"] = 0

    perk = research_state["mins_per_help"]
    total_reduction_mins = perk * 30
    reduction_str = f"-{total_reduction_mins // 60}h {total_reduction_mins % 60}m" if total_reduction_mins >= 60 else f"-{total_reduction_mins}m"

    target_local = target_time.astimezone()
    time_str = target_local.strftime("%A, %B %d, %Y at %I:%M %p")
    rel_time = f"<t:{int(target_time.timestamp())}:R>"

    embed = discord.Embed(
        title="🔬 Guild Research Timer Set!",
        color=discord.Color.green()
    )
    embed.add_field(name="Project Name", value=f"`{name}`", inline=True)
    embed.add_field(name="Help Cutdown Perk", value=f"`{perk}m / help` ({reduction_str} per 30 helps)", inline=True)
    embed.add_field(name="Estimated Completion", value=f"{time_str} ({rel_time})", inline=False)
    embed.add_field(name="🚨 Automated Pings", value="Scheduled for 10m, 5m, and 1m before completion!", inline=False)

    role = discord.utils.get(ctx.guild.roles, name=OFFICER_ROLE_NAME)
    role_ping = role.mention if role else f"@{OFFICER_ROLE_NAME}"
    await ctx.send(content=f"📣 Attention {role_ping}!", embed=embed)

    task = asyncio.create_task(start_countdown_loops(ctx, channel_name=TARGET_CHANNEL_NAME, role_ping=role_ping))
    research_state["timer_task"] = task

async def start_countdown_loops(ctx, channel_name, role_ping):
    global research_state
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name) or ctx.channel

    async def wait_until_warning(minutes_before, warning_title, color_code):
        while True:
            now = datetime.now(timezone.utc)
            remaining = (research_state["target_time"] - now).total_seconds()
            target_wait = remaining - (minutes_before * 60)

            if target_wait <= 0:
                break
            await asyncio.sleep(min(target_wait, 10))

        now = datetime.now(timezone.utc)
        if research_state["target_time"] > now:
            embed_warn = discord.Embed(
                title=f"⚠️ {minutes_before}-Minute Research Warning!",
                description=f"Research **'{research_state['name']}'** will finish in **{minutes_before} minutes**! Get ready to apply Water!",
                color=color_code
            )
            await channel.send(content=f"🔔 {role_ping}", embed=embed_warn)

    # 10m Warning
    await wait_until_warning(10, "10-Minute Research Warning", discord.Color.gold())

    # 5m Warning
    await wait_until_warning(5, "5-Minute Research Warning", discord.Color.orange())

    # 1m Warning
    await wait_until_warning(1, "1-Minute Research Warning", discord.Color.red())

    # Final Wait
    while True:
        now = datetime.now(timezone.utc)
        remaining = (research_state["target_time"] - now).total_seconds()
        if remaining <= 0:
            break
        await asyncio.sleep(min(remaining, 5))

    embed_done = discord.Embed(
        title="💧 GUILD RESEARCH FINISHED!",
        description=f"Research **'{research_state['name']}'** is complete! Apply Water now to maximize boost!",
        color=discord.Color.purple()
    )
    await channel.send(content=f"🚨 {role_ping}", embed=embed_done)

@bot.command(name="setresearch")
@commands.has_role(OFFICER_ROLE_NAME)
async def setresearch_command(ctx, name: str, *, time_input: str):
    td = parse_time_input(time_input)
    if not td:
        await ctx.send("❌ Invalid time format! Example usage: `!setresearch \"New Heights Lvl 6\" 4d 11h 24m`")
        return
    await start_research_timer(ctx, name, td.total_seconds())

@bot.command(name="setperk")
@commands.has_role(OFFICER_ROLE_NAME)
async def setperk_command(ctx, mins: int):
    global research_state
    research_state["mins_per_help"] = mins
    await ctx.send(f"✅ Research perk set to `{mins}` mins/help!")

@bot.command(name="setplan")
@commands.has_role(OFFICER_ROLE_NAME)
async def setplan_command(ctx, phase: str, *, new_goal: str):
    global roadmap_state
    phase_key = phase.lower().strip()
    if phase_key in roadmap_state:
        roadmap_state[phase_key] = new_goal
        await ctx.send(f"✅ Updated **{phase_key.upper()}** objective to `{new_goal}`.")
        await send_guild_roadmap(ctx.channel)
    else:
        await ctx.send("❌ Invalid phase selection! Use `phase1`, `phase2`, or `phase3`.")

@bot.command(name="plan")
async def plan_command(ctx):
    await send_guild_roadmap(ctx.channel)

@bot.command(name="help")
async def help_command(ctx):
    embed_add_field = discord.Embed(
        title="📜 Evitania Guild Bot Commands",
        description="Commands for managing guild research timers and officer pings:",
        color=discord.Color.blue()
    )
    embed_add_field.add_field(
        name="!setresearch <\"Name\"> <RemainingTime> *(Officer Only)*",
        value="Sets new research timer using remaining in-game time directly.\n*Examples:*\n• `!setresearch \"New Heights Lvl 6\" 4d 11h 24m`\n• `!setresearch \"Guild Growth Lvl 4\" 1d 8h`\n• `!setresearch \"Expanded Stock Lvl 1\" 48h`",
        inline=False
    )
    embed_add_field.add_field(
        name="!setperk <MinsPerHelp> *(Officer Only)*",
        value="Updates minutes shaved per help across calculations.\n*Examples:*\n• `!setperk 44` (Level 6 Perk)\n• `!setperk 48` (Level 7 Perk)",
        inline=False
    )
    embed_add_field.add_field(
        name="!setplan <phase1/phase2/phase3> <New Goal> *(Officer Only)*",
        value="Updates the guild roadmap priorities card.\n*Example:* `!setplan phase1 Guild EXP & Growth Level 6`",
        inline=False
    )
    embed_add_field.add_field(
        name="!plan",
        value="Displays the active guild progression planner and roadmap card.",
        inline=False
    )
    await ctx.send(embed=embed_add_field)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name="Evitania Online | !help"))

    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=TARGET_CHANNEL_NAME)
        if channel:
            await send_guild_roadmap(channel)

# --- DUMMY WEB SERVER FOR RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@bot.event
async def setup_hook():
    bot.loop.create_task(start_dummy_server())

# --- BOT RUNNER ---
bot.run(os.environ.get("BOT_TOKEN"))