"""
Coded entirely by ChatGPT and Gemini, because I'm not going to try leaking my actual code I use for running my script. 
I may use some code from this file and use the ideas similar in this file. Otherthan that, this is entirely just vibe-coded.
"""


import os
import time
import asyncio
import logging
import aiohttp
from collections import defaultdict
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# ========================
# CONFIG & LOGGING
# ========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_stats = {"queries": 0, "start_time": time.time()}
bot_loop = None 

# Memory buffer: Stores the last 10 messages per channel ID
conversation_history = defaultdict(list)
MAX_MEMORY = 10

# The AI's personality
SYSTEM_PROMPT = """You are a helpful, casual, and highly intelligent Discord user. 
Speak naturally, use standard capitalization, and avoid sounding like a robotic assistant. 
Do not use overly formal language. Keep your answers concise unless asked for details.
You are aware of the server context and recent message history provided to you."""

# ========================
# FLASK C2 DASHBOARD
# ========================
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", os.urandom(24))
DASH_PASSWORD = os.getenv("DASH_PASSWORD", "admin123") 

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI System | C2 Matrix</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #050505; color: white; font-family: 'Space Grotesk', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .bg { position: fixed; width: 100%; height: 100%; background: radial-gradient(circle at 50% 50%, #1e293b 0%, #050505 100%); z-index: -1; }
        .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 40px; width: 100%; max-width: 600px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
        h1 { margin-top: 0; color: #3b82f6; text-shadow: 0 0 20px rgba(59, 130, 246, 0.5); text-align: center;}
        input, select, button { width: 100%; padding: 12px; margin-top: 10px; margin-bottom: 20px; background: rgba(0,0,0,0.5); border: 1px solid #334155; color: white; border-radius: 8px; font-family: inherit; box-sizing: border-box;}
        button { background: #3b82f6; border: none; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { background: #2563eb; box-shadow: 0 0 15px rgba(59, 130, 246, 0.6); }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .stat-card { background: rgba(0,0,0,0.3); padding: 15px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.05); }
        .label { color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
        .val { font-size: 24px; font-weight: 700; color: #f8fafc; margin-top: 5px; }
        .success { color: #22c55e; text-align: center; margin-bottom: 15px; display: none; }
    </style>
</head>
<body>
    <div class="bg"></div>
    <div class="glass">
        {% if not session.logged_in %}
            <h1>System Override</h1>
            <form method="POST" action="/login">
                <label class="label">Authorization Key</label>
                <input type="password" name="password" placeholder="Enter password..." required>
                {% if error %}<p style="color: #ef4444; font-size: 12px;">{{ error }}</p>{% endif %}
                <button type="submit">Access Matrix</button>
            </form>
        {% else %}
            <h1>C2 Control Panel</h1>
            <div class="grid">
                <div class="stat-card"><div class="label">Total Queries</div><div class="val">{{ stats.queries }}</div></div>
                <div class="stat-card"><div class="label">Bot Latency</div><div class="val">{{ stats.latency }}ms</div></div>
            </div>
            <hr style="border-color: #334155; margin-bottom: 20px;">
            <div class="label">Transmit Message as Bot</div>
            <form id="sendForm">
                <select id="serverSelect" onchange="loadChannels()">
                    <option value="">-- Select Server --</option>
                    {% for guild in guilds %}
                        <option value="{{ guild.id }}">{{ guild.name }}</option>
                    {% endfor %}
                </select>
                <select id="channelSelect" required disabled>
                    <option value="">-- Select Channel --</option>
                </select>
                <input type="text" id="messageBox" placeholder="Type message to send as bot..." required>
                <div id="statusMsg" class="success">Message Transmitted!</div>
                <button type="submit" id="sendBtn">Send Payload</button>
            </form>
            <div style="text-align: center; margin-top: 20px;">
                <a href="/logout" style="color: #ef4444; text-decoration: none; font-size: 12px;">[ Disconnect Session ]</a>
            </div>
            <script>
                async function loadChannels() {
                    const guildId = document.getElementById('serverSelect').value;
                    const chanSelect = document.getElementById('channelSelect');
                    chanSelect.innerHTML = '<option value="">-- Loading --</option>';
                    chanSelect.disabled = true;
                    if (!guildId) return;
                    const res = await fetch('/api/channels/' + guildId);
                    const channels = await res.json();
                    chanSelect.innerHTML = '<option value="">-- Select Channel --</option>';
                    channels.forEach(ch => { chanSelect.innerHTML += `<option value="${ch.id}">#${ch.name}</option>`; });
                    chanSelect.disabled = false;
                }
                document.getElementById('sendForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const btn = document.getElementById('sendBtn');
                    const channelId = document.getElementById('channelSelect').value;
                    const content = document.getElementById('messageBox').value;
                    btn.innerText = "Sending...";
                    btn.disabled = true;
                    await fetch('/api/send', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ channel_id: channelId, content: content })
                    });
                    document.getElementById('messageBox').value = '';
                    document.getElementById('statusMsg').style.display = 'block';
                    btn.innerText = "Send Payload";
                    btn.disabled = false;
                    setTimeout(() => { document.getElementById('statusMsg').style.display = 'none'; }, 3000);
                });
            </script>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def dashboard():
    if not session.get("logged_in"):
        return render_template_string(HTML_TEMPLATE)
    safe_latency = int(bot.latency * 1000) if bot.latency and bot.latency != float('inf') else 0
    stats = {"queries": bot_stats["queries"], "latency": safe_latency}
    guilds = [{"id": str(g.id), "name": g.name} for g in bot.guilds]
    return render_template_string(HTML_TEMPLATE, stats=stats, guilds=guilds)

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == DASH_PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("dashboard"))
    return render_template_string(HTML_TEMPLATE, error="Invalid credentials.")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("dashboard"))

@app.route("/api/channels/<guild_id>")
def api_channels(guild_id):
    if not session.get("logged_in"): return jsonify([])
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify([])
    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
    return jsonify(channels)

@app.route("/api/send", methods=["POST"])
def api_send():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    channel_id, content = int(data.get("channel_id")), data.get("content")

    async def send_to_discord():
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                webhooks = await channel.webhooks()
                wh = next((w for w in webhooks if w.name == bot.user.name), None)
                if not wh: wh = await channel.create_webhook(name=bot.user.name)
                await wh.send(content=content, username=bot.user.display_name, avatar_url=bot.user.display_avatar.url)
            except discord.Forbidden:
                await channel.send(content) # Fallback if webhook permission is missing

    if bot_loop:
        asyncio.run_coroutine_threadsafe(send_to_discord(), bot_loop)
    return jsonify({"status": "success"})

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)

# ========================
# DISCORD BOT LOGIC
# ========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def scrape_context(guild):
    """Safely fetch server rules if available."""
    context_data = {"rules": "None"}
    if not guild: return context_data
    try:
        for ch in guild.text_channels:
            if "rule" in ch.name.lower() or "info" in ch.name.lower():
                if ch.permissions_for(guild.me).read_message_history:
                    messages = [m.content async for m in ch.history(limit=5)]
                    context_data["rules"] = "\n".join(messages)[:800]
                    break
    except Exception as e:
        logger.warning(f"Could not fetch rules: {e}")
    return context_data

@bot.event
async def on_ready():
    global bot_loop
    bot_loop = asyncio.get_running_loop()
    logger.info(f"AI Matrix Active: {bot.user}")

@bot.command(name="wipe")
async def wipe_memory(ctx):
    """Clears the AI's short-term memory for the current channel."""
    conversation_history[ctx.channel.id].clear()
    await ctx.send("🧠 Memory wiped for this channel.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    # Process standard commands first (!wipe, etc)
    await bot.process_commands(message)

    # Trigger AI if pinged or in DMs
    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            try:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key: raise ValueError("OPENAI_API_KEY missing from environment.")

                # Gather context
                guild_info = await scrape_context(message.guild)
                pins = []
                if message.channel.permissions_for(message.guild.me).read_message_history if message.guild else True:
                    pins = [p.content for p in await message.channel.pins()]
                
                context_header = f"""[SERVER DATA] Name: {message.guild.name if message.guild else "DMs"}, Rules: {guild_info['rules']}, Pinned: {", ".join(pins[:3]) if pins else "None"}"""

                # Update memory
                history = conversation_history[message.channel.id]
                history.append({"role": "user", "content": f"{message.author.display_name}: {message.clean_content}"})
                
                # Build payload
                messages_payload = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + context_header}] + history

                api_url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "gpt-4o-mini", # Change to whatever model you prefer
                    "messages": messages_payload,
                    "max_tokens": 500
                }

                # Make the API call
                async with aiohttp.ClientSession() as session_http:
                    async with session_http.post(api_url, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply = data["choices"][0]["message"]["content"]
                        else:
                            raise Exception(f"API Error {resp.status}: {await resp.text()}")

                # Save AI response to memory
                history.append({"role": "assistant", "content": reply})
                if len(history) > MAX_MEMORY:
                    history = history[-MAX_MEMORY:]
                    conversation_history[message.channel.id] = history

                bot_stats["queries"] += 1

                # Send via Webhook to match persona (or fallback to normal message)
                if message.guild:
                    try:
                        webhooks = await message.channel.webhooks()
                        wh = next((w for w in webhooks if w.name == bot.user.name), None)
                        if not wh: wh = await message.channel.create_webhook(name=bot.user.name)
                        await wh.send(content=reply, username=bot.user.display_name, avatar_url=bot.user.display_avatar.url, wait=True)
                    except discord.Forbidden:
                        await message.reply(reply)
                else:
                    await message.reply(reply)

            except Exception as e:
                logger.error(f"AI Failure: {e}")
                await message.reply(f"⚠️ `System Error: {e}`")

if __name__ == "__main__":
    # Start web server FIRST so Replit doesn't kill the process
    Thread(target=run_web, daemon=True).start()
    bot.run(os.getenv("DISCORD_TOKEN"))
