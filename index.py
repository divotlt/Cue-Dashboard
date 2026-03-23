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
# LOGGING
# ========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================
# STATS
# ========================
bot_stats = {
    "total_queries": 0,
    "start_time": time.time()
}

user_cooldowns = {}

# ========================
# FLASK DASHBOARD
# ========================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bot Dashboard</title>
<meta http-equiv="refresh" content="5">

<style>
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: white;
}

.container {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    padding: 40px;
}

.card {
    background: #1e293b;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 0 15px rgba(0,0,0,0.4);
}

.title {
    font-size: 14px;
    color: #94a3b8;
}

.value {
    font-size: 28px;
    font-weight: bold;
    margin-top: 10px;
}

.status {
    display: flex;
    align-items: center;
    gap: 10px;
}

.dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #22c55e;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.5); opacity: 0.5; }
    100% { transform: scale(1); opacity: 1; }
}
</style>
</head>

<body>

<div class="container">

    <div class="card status">
        <div class="dot"></div>
        <div>
            <div class="title">Status</div>
            <div class="value">Online</div>
        </div>
    </div>

    <div class="card">
        <div class="title">AI Queries</div>
        <div class="value">{{ queries }}</div>
    </div>

    <div class="card">
        <div class="title">Uptime</div>
        <div class="value">{{ uptime }}</div>
    </div>

    <div class="card">
        <div class="title">Latency</div>
        <div class="value">{{ latency }} ms</div>
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

    return render_template_string(
        HTML_TEMPLATE,
        queries=bot_stats["total_queries"],
        uptime=f"{h}h {m}m {s}s",
        latency=int(bot.latency * 1000) if bot.latency else 0
    )

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

def keep_alive():
    Thread(target=run_web, daemon=True).start()
    logger.info("Dashboard running")

# ========================
# DISCORD BOT
# ========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# COOLDOWN
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
    await bot.change_presence(activity=discord.Game("AI Chat | !stats"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if not (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        return

    if await is_on_cooldown(message.author.id):
        await message.add_reaction("⏳")
        return

    status_msg = await message.reply("⏳ Thinking...")

    start = time.time()

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_KEY"))

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            config=types.GenerateContentConfig(
                system_instruction="You are Cue: short, slang-heavy, vague answers."
            ),
            contents=f"{message.author.name}: {message.content}"
        )

        reply_text = response.text or ""

        if not reply_text.strip():
            raise ValueError("Empty response")

        if len(reply_text) > 4000:
            reply_text = reply_text[:4000] + "..."

        bot_stats["total_queries"] += 1

        embed = discord.Embed(
            description=reply_text,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Generated in {round(time.time() - start, 2)}s")

        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        logger.exception("AI error")
        await status_msg.edit(content=f"❌ Error: `{e}`")

# ========================
# COMMANDS
# ========================
@bot.command()
async def ping(ctx):
    await ctx.send("Pong 🏓")

@bot.command()
async def stats(ctx):
    uptime = int(time.time() - bot_stats["start_time"])
    m, s = divmod(uptime, 60)
    h, m = divmod(m, 60)

    embed = discord.Embed(title="Stats", color=discord.Color.green())
    embed.add_field(name="Queries", value=bot_stats["total_queries"])
    embed.add_field(name="Uptime", value=f"{h}h {m}m {s}s")
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms")

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
        logger.error("Missing DISCORD_TOKEN")
