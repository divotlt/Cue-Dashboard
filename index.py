import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from ollama import Client
import asyncio
import time

# ========================
# KEEP ALIVE (Render free tier)
# ========================
@app.route('/')
def home() -> str:
    """Health check endpoint to verify the bot is running."""
    return "Bot is alive and running."

def run_web() -> None:
    """Starts the Flask web server."""
    # Fetch the port from environment variables, defaulting to 10000
    port = int(os.environ.get("PORT", 10000))
    
    # Run the app with debug and reloader disabled for better performance/security
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive() -> None:
    """Spawns a daemon thread to run the web server in the background."""
    server_thread = Thread(target=run_web, daemon=True)
    server_thread.start()
    logger.info("Keep-alive server initialized and running.")
    
# ========================
# DISCORD SETUP
# ========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# OLLAMA CLIENT
# ========================
client = Client(
    host="http://localhost:11434"  # change if you're actually hosting it somewhere
)

# ========================
# SIMPLE COOLDOWN
# ========================
user_cooldowns = {}

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
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        await bot.process_commands(message)
        return

    if await is_on_cooldown(message.author.id):
        return

    try:
        # Run blocking call in a thread
        response = await asyncio.to_thread(
            client.chat,
            model="minimax-m2.1:cloud",
            messages=[{"role": "user", "content": message.content}]
        )

        reply = response.get("message", {}).get("content", "No response.")

        # Truncate safely
        if len(reply) > 1900:
            reply = reply[:1900]

        await message.reply(reply)

    except Exception as e:
        err = str(e)

        # Basic rate limit handling
        if "429" in err:
            await asyncio.sleep(5)
            return

        await message.reply(f"Error: {err}")

    await bot.process_commands(message)

# ========================
# COMMANDS
# ========================
@bot.command()
async def ping(ctx):
    await ctx.send("Pong.")

# ========================
# STARTUP
# ========================
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
