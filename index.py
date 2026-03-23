import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from ollama import Client

# ========================
# KEEP ALIVE (Render free tier)
# ========================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ========================
# DISCORD SETUP
# ========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# OLLAMA CLOUD CLIENT
# ========================
client = Client(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY')}"
    }
)

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

    # Respond if bot is mentioned OR in DMs
    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        try:
            response = client.chat(
                model="minimax-m2.1:cloud",
                messages=[
                    {"role": "user", "content": message.content}
                ]
            )

            reply = response['message']['content']

            if len(reply) > 1900:
                reply = reply[:1900]

            await message.reply(reply)

        except Exception as e:
            await message.reply(f"Error: {e}")

    # IMPORTANT: keeps commands working
    await bot.process_commands(message)

# ========================
# BASIC COMMANDS
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
