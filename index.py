import os
import time
import asyncio
import logging
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask
from ollama import Client

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================
# KEEP ALIVE (Render free tier)
# ========================
app = Flask(__name__)

@app.route('/')
def home() -> str:
    return "Bot is alive and running."

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

client = Client(host="http://localhost:11434")

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
        # Run blocking AI call
        response = await asyncio.to_thread(
            client.chat,
            model="minimax-m2.1:cloud",
            messages=[{"role": "user", "content": message.content}]
        )
        
        reply = response.get("message", {}).get("content", "No response.")
        
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
