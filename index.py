"""
Coded entirely by ChatGPT and Gemini, because I'm not going to try leaking my actual code I use for running my script
"""

import os
import time
import asyncio
import logging
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask, render_template_string
from google import genai
from google.genai import types

# ========================
# LOGGING & SETUP
# ========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_stats = {
    "total_queries": 0,
    "start_time": time.time()
}
user_cooldowns = {}

# ========================
# FLASK DASHBOARD (UPGRADED UI)
# ========================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Bot Dashboard</title>
<meta http-equiv="refresh" content="5">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
    :root {
        --bg-color: #0b0f19;
        --card-bg: rgba(30, 41, 59, 0.7);
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --accent: #3b82f6;
        --glow: rgba(59, 130, 246, 0.5);
    }

    body {
        margin: 0;
        font-family: 'Inter', sans-serif;
        background: radial-gradient(circle at top left, #1e1b4b, var(--bg-color) 40%);
        color: var(--text-main);
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 40px 20px;
    }

    .header {
        text-align: center;
        margin-bottom: 40px;
    }

    .header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(to right, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 24px;
        width: 100%;
        max-width: 900px;
    }

    .card {
        background: var(--card-bg);
        backdrop-filter: blur(10px);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 30px var(--glow);
        border-color: rgba(255, 255, 255, 0.2);
    }

    .title {
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--text-muted);
        font-weight: 600;
    }

    .value {
        font-size: 2.5rem;
        font-weight: 800;
        margin-top: 12px;
        color: var(--text-main);
    }

    .status-wrapper {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 10px #22c55e;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }
</style>
</head>
<body>

<div class="header">
    <h1>System Override Console</h1>
    <p style="color: #94a3b8;">Real-time AI telemetry and diagnostics</p>
</div>

<div class="container">
    <div class="card">
        <div class="status-wrapper">
            <div class="dot"></div>
            <div>
                <div class="title">System Status</div>
                <div class="value" style="font-size: 1.5rem; margin-top: 4px;">Operational</div>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="title">Neural Queries</div>
        <div class="value">{{ queries }}</div>
    </div>

    <div class="card">
        <div class="title">Uptime</div>
        <div class="value" style="font-size: 1.75rem;">{{ uptime }}</div>
    </div>

    <div class="card">
        <div class="title">Gateway Latency</div>
        <div class="value">{{ latency }} <span style="font-size: 1rem; color: #94a3b8;">ms</span></div>
    </div>
</div>

</body>
</html>
"""

@app.route("/")
def dashboard():
    uptime_seconds = int(time.time() - bot_stats["start_time"])
    m, s = divmod(uptime_seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    
    uptime_str = f"{d}d {h}h {m}m" if d > 0 else f"{h}h {m}m {s}s"

    return render_template_string(
        HTML_TEMPLATE,
        queries=bot_stats["total_queries"],
        uptime=uptime_str,
        latency=int(bot.latency * 1000) if bot.latency else 0
    )

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

def keep_alive():
    Thread(target=run_web, daemon=True).start()
    logger.info("Dashboard UI running")

# ========================
# DISCORD BOT SETUP
# ========================
# Enabling default intents + message content. 
# For full member caching (to see all server members), enable Intents.members in Discord dev portal.
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# COOLDOWN LOGIC
# ========================
async def is_on_cooldown(user_id, cooldown=5):
    now = time.time()
    last = user_cooldowns.get(user_id, 0)
    if now - last < cooldown:
        return True
    user_cooldowns[user_id] = now
    return False

# ========================
# EVENTS
# ========================
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the server | !stats"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Process standard commands first (!ping, !stats)
    await bot.process_commands(message)

    # Only trigger AI if mentioned or in DMs
    if not (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        return

    if await is_on_cooldown(message.author.id):
        await message.add_reaction("⏳")
        return

    status_msg = await message.reply("⚡ Processing...")
    start = time.time()

    try:
        # --- ADVANCED CONTEXT BUILDING ---
        if message.guild:
            # Server context
            guild_name = message.guild.name
            channel_name = message.channel.name
            
            # Bot's context
            bot_member = message.guild.me
            bot_name = bot_member.display_name
            bot_roles = ", ".join([r.name for r in bot_member.roles if r.name != "@everyone"]) or "None"
            
            # User's context
            user_name = message.author.display_name
            user_roles = ", ".join([r.name for r in message.author.roles if r.name != "@everyone"]) or "None"
            
            # Get a list of up to 15 text channels to give the bot awareness of the server layout
            text_channels = [c.name for c in message.guild.text_channels][:15]
            channels_list = ", ".join(text_channels)

            system_instruction = f"""
            You are Cue, an advanced, highly aware Discord AI assistant. You use short, modern, slightly slang-heavy language, but you are deeply intelligent.
            
            CURRENT ENVIRONMENT DATA:
            - Server Name: {guild_name}
            - Current Channel: #{channel_name}
            - Available Channels: {channels_list}
            
            YOUR IDENTITY IN THIS SERVER:
            - Your Display Name: {bot_name}
            - Your Assigned Roles: {bot_roles}
            
            USER DATA (The person speaking to you):
            - User Name: {user_name}
            - User Roles: {user_roles}
            
            INSTRUCTIONS:
            Use this environment data naturally. If asked what your roles are, or where you are, use the data above. Treat the user according to their roles (e.g., respect Admins/Mods). Keep responses concise and formatted well for Discord.
            """
        else:
            system_instruction = "You are Cue. You are currently in a private Direct Message. Keep answers short, modern, and clever."

        # --- AI GENERATION ---
        client = genai.Client(api_key=os.getenv("GEMINI_KEY"))

        # Clean the mention out of the prompt so the AI just reads the text
        clean_content = message.clean_content.replace(f"@{bot.user.name}", "").strip()

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            ),
            contents=clean_content
        )

        reply_text = response.text or ""

        if not reply_text.strip():
            raise ValueError("Empty AI response")

        if len(reply_text) > 4000:
            reply_text = reply_text[:4000] + "..."

        bot_stats["total_queries"] += 1

        embed = discord.Embed(
            description=reply_text,
            color=0x3b82f6 # Nice modern blue
        )
        embed.set_footer(text=f"Processed in {round(time.time() - start, 2)}s | Model: gemini-3-flash")

        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        logger.exception("AI processing error")
        await status_msg.edit(content=f"❌ **System Error:** `{e}`")

# ========================
# COMMANDS
# ========================
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong 🏓 `{round(bot.latency * 1000)}ms`")

@bot.command()
async def stats(ctx):
    uptime = int(time.time() - bot_stats["start_time"])
    m, s = divmod(uptime, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    uptime_str = f"{d}d {h}h {m}m" if d > 0 else f"{h}h {m}m {s}s"

    embed = discord.Embed(title="📊 System Diagnostics", color=0x22c55e)
    embed.add_field(name="Neural Queries", value=f"`{bot_stats['total_queries']}`", inline=True)
    embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="Gateway Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.display_avatar else None)

    await ctx.send(embed=embed)

# ========================
# START
# ========================
if __name__ == "__main__":
    keep_alive()

    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        logger.error("Missing DISCORD_TOKEN in environment variables.")
