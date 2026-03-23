"""
Coded entirely by ChatGPT and Gemini, because I'm not going to try leaking my actual code I use for running my script. 
I may use some code from this file and use the ideas similar in this file. Otherthan that, this is entirely just vibe-coded.
"""

import os
import time
import asyncio
import logging
import aiohttp 
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask, render_template_string

# ========================
# CONFIG & LOGGING
# ========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_stats = {"queries": 0, "start_time": time.time()}

# ========================
# DASHBOARD
# ========================
app = Flask(__name__)
HTML_DASH = """
<!DOCTYPE html>
<html lang="en">
<head>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #050505; color: white; font-family: 'Space Grotesk', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }
        .bg { position: absolute; width: 100%; height: 100%; background: radial-gradient(circle at 50% 50%, #1e293b 0%, #050505 100%); z-index: -1; }
        .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 40px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
        .stat-card { padding: 20px; text-align: center; }
        .label { color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; }
        .val { font-size: 32px; font-weight: 700; margin-top: 5px; color: #3b82f6; text-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
    </style>
</head>
<body>
    <div class="bg"></div>
    <div class="glass">
        <div class="stat-card"><div class="label">Neural Links</div><div class="val">{{ queries }}</div></div>
        <div class="stat-card"><div class="label">Latency</div><div class="val">{{ latency }}ms</div></div>
        <div class="stat-card" style="grid-column: span 2;"><div class="label">System Uptime</div><div class="val">{{ uptime }}</div></div>
    </div>
</body>
</html>
"""

@app.route("/")
def dashboard():
    uptime = int(time.time() - bot_stats["start_time"])
    h, m = divmod(uptime // 60, 60)
    return render_template_string(HTML_DASH, queries=bot_stats["queries"], latency=int(bot.latency * 1000) if bot.latency else 0, uptime=f"{h}h {m}m {uptime%60}s")

def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ========================
# UTILS & HELPERS
# ========================
async def get_webhook(channel):
    """Finds or creates a webhook for the channel to allow mimicking."""
    webhooks = await channel.webhooks()
    for wh in webhooks:
        if wh.name == "apicuefree_p2h": return wh
    return await channel.create_webhook(name="apicuefree_p2h")

async def scrape_context(guild):
    """Scrapes rules and pins for AI context."""
    context_data = {"rules": "None"}
    if not guild: return context_data

    for ch in guild.text_channels:
        if "rule" in ch.name.lower() or "info" in ch.name.lower():
            messages = [m.content async for m in ch.history(limit=5)]
            context_data["rules"] = "\n".join(messages)[:800]
            break
    
    return context_data

# ========================
# BOT LOGIC
# ========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"AI Matrix Active: {bot.user}")
    Thread(target=run_web, daemon=True).start()

@bot.event
async def on_message(message):
    if message.author.bot or not (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)):
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            verba_key = os.getenv("VERBA_API")
            if not verba_key:
                raise ValueError("VERBA_API key is missing.")

            # 1. Gather Deep Context
            guild_info = await scrape_context(message.guild)
            pins = [p.content for p in await message.channel.pins()]
            
            # 2. Build the "Smuggled" Context Payload
            context_header = f"""
            [SYSTEM AWARENESS DATA - DO NOT REPLY TO THIS PART]
            Current Server: {message.guild.name if message.guild else "DMs"}
            Current Channel: {message.channel.name if message.guild else "DMs"}
            User Speaking: {message.author.display_name}
            Server Rules: {guild_info['rules']}
            Pinned Data: {", ".join(pins[:3]) if pins else "None"}
            [END AWARENESS DATA]
            
            """
            
            # Combine context with the actual user message
            user_input = message.clean_content
            full_prompt = context_header + user_input

            if message.embeds:
                full_prompt += f"\n[User also sent an embed: {message.embeds[0].description}]"

            # 3. Verba API Call
            api_url = "https://api.verba.ink/v1/response"
            headers = {
                "Authorization": f"Bearer {verba_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "character": "apicuefree_p2h",
                "messages": [
                    {"role": "user", "content": full_prompt}
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"]
                    else:
                        error_text = await resp.text()
                        raise Exception(f"API Error {resp.status}: {error_text}")

            bot_stats["queries"] += 1

            # 4. Webhook Mimicry Response
            if message.guild:
                webhook = await get_webhook(message.channel)
                await webhook.send(
                    content=reply,
                    username="apicuefree_p2h", 
                    avatar_url=bot.user.display_avatar.url,
                    wait=True
                )
            else:
                await message.reply(reply)

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            await message.reply(f"⚠️ `System Error: {e}`")

# ========================
# RUN
# ========================
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
