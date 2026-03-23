import os
import time
import asyncio
import logging
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask
import requests

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_KEY = os.getenv("OLLAMA_API_KEY")
# ========================
# KEEP ALIVE (Render free tier)
# ========================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #2c2f33; /* Discord-like dark theme */
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .dashboard {
            background-color: #23272a;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.5);
            text-align: center;
            width: 300px;
        }
        .status-container {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        /* The Animation */
        .pulse-dot {
            height: 16px;
            width: 16px;
            background-color: #43b581; /* Online green */
            border-radius: 50%;
            display: inline-block;
            margin-right: 12px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(67, 181, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(67, 181, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(67, 181, 129, 0); }
        }
        .divider {
            height: 2px;
            background-color: #2c2f33;
            margin: 20px 0;
            border: none;
        }
        .stats {
            text-align: left;
            font-size: 16px;
            line-height: 1.8;
        }
        .stat-label {
            color: #7289da; /* Blurple */
            font-weight: 600;
        }
    </style>
</head>
<body>

    <div class="dashboard">
        <div class="status-container">
            <span class="pulse-dot"></span> System Online
        </div>
        
        <hr class="divider">
        
        <div class="stats">
            <div><span class="stat-label">Total AI Queries:</span> {{ queries }}</div>
            <div><span class="stat-label">Server Uptime:</span> {{ uptime }}</div>
        </div>
    </div>

</body>
</html>
"""

@app.route('/')
def home() -> str:
    """Renders the web dashboard with live bot statistics."""
    # Calculate uptime dynamically when the page is refreshed
    uptime_seconds = int(time.time() - bot_stats["start_time"])
    m, s = divmod(uptime_seconds, 60)
    h, m = divmod(m, 60)
    uptime_str = f"{h}h {m}m {s}s"
    
    # Inject the stats into the HTML template
    return render_template_string(
        HTML_TEMPLATE, 
        queries=bot_stats["total_queries"], 
        uptime=uptime_str
    )

def run_web() -> None:
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive() -> None:
    server_thread = Thread(target=run_web, daemon=True)
    server_thread.start()
    logger.info("Keep-alive server initialized and running.")

# ========================
# DISCORD & AI SETUP
# ========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# TRACKERS & COOLDOWNS
# ========================
user_cooldowns = {}
bot_stats = {
    "total_queries": 0,
    "start_time": time.time()
}

async def is_on_cooldown(user_id: int, cooldown: int = 5):
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
    # Sets a "Playing" status UI on the bot's profile
    await bot.change_presence(activity=discord.Game(name="Chatting with AI | !stats"))

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Process standard commands first (like !ping or !stats)
    await bot.process_commands(message)

    # If it's not a mention or DM, ignore it for AI generation
    if not (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        return

    if await is_on_cooldown(message.author.id):
        # Optional: Send a cooldown warning UI
        await message.add_reaction("⏳") 
        return

    # 1. ANIMATION: Send a temporary loading message
    status_msg = await message.reply("⏳ *Thinking...*")
    start_gen_time = time.time()

    try:
        response = requests.post(
            "https://api.ollama.com/v1/chat",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "minimax-m2.1:cloud",
                "messages": [{"role": "user", "content": message.content}]
            }
        )
        
        data = response.json()
        reply = data["message"]["content"]
        
        # Discord Embed limits descriptions to 4096 chars
        if len(reply) > 4000:
            reply = reply[:4000] + "...\n*(Message truncated due to length)*"

        # Update Statistics
        bot_stats["total_queries"] += 1
        gen_time = round(time.time() - start_gen_time, 2)

        # 2. UI: Wrap the final response in a clean Embed
        embed = discord.Embed(
            description=reply,
            color=discord.Color.blurple() # Nice Discord blue
        )
        embed.set_footer(text=f"Minimax Model | Generated in {gen_time}s")

        # Edit the loading message to show the final Embed
        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        err = str(e)
        if "429" in err:
            await status_msg.edit(content="⚠️ **Rate limited!** Please try again in a few seconds.")
            return

        await status_msg.edit(content=f"❌ **Error:** `{err}`")

# ========================
# COMMANDS
# ========================
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

@bot.command()
async def stats(ctx):
    """3. STATISTICS: A UI dashboard showing bot usage."""
    uptime_seconds = int(time.time() - bot_stats["start_time"])
    
    # Format uptime nicely (e.g., 1h 2m 10s)
    m, s = divmod(uptime_seconds, 60)
    h, m = divmod(m, 60)
    uptime_str = f"{h}h {m}m {s}s"

    embed = discord.Embed(title="📊 Bot Statistics", color=discord.Color.green())
    embed.add_field(name="Total AI Queries", value=str(bot_stats["total_queries"]), inline=True)
    embed.add_field(name="Uptime", value=uptime_str, inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await ctx.send(embed=embed)

# ========================
# STARTUP
# ========================
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        logger.error("No DISCORD_TOKEN found in environment variables!")
