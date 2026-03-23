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
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# ========================
# CONFIG & LOGGING
# ========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_stats = {"queries": 0, "start_time": time.time()}

# We need this to safely talk to Discord from the Flask web thread
bot_loop = None 

# ========================
# FLASK C2 DASHBOARD
# ========================
app = Flask(__name__)
# Secure the session cookies
app.secret_key = os.getenv("FLASK_SECRET", os.urandom(24))
DASH_PASSWORD = os.getenv("DASH_PASSWORD", "admin123") # Change this in your .env!

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>apicuefree_p2h | C2 System</title>
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
                <div class="stat-card"><div class="label">Queries</div><div class="val">{{ stats.queries }}</div></div>
                <div class="stat-card"><div class="label">Latency</div><div class="val">{{ stats.latency }}ms</div></div>
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
                    channels.forEach(ch => {
                        chanSelect.innerHTML += `<option value="${ch.id}">#${ch.name}</option>`;
                    });
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
    
    # Pass bot stats and guild list to the template
    stats = {
        "queries": bot_stats["queries"],
        "latency": int(bot.latency * 1000) if bot.latency else 0
    }
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
    
    # Filter to only return text channels the bot can view
    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
    return jsonify(channels)

@app.route("/api/send", methods=["POST"])
def api_send():
    if not session.get("logged_in"): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    channel_id = int(data.get("channel_id"))
    content = data.get("content")

    # This creates an async function we can throw into the bot's event loop
    async def send_to_discord():
        channel = bot.get_channel(channel_id)
        if channel:
            # We use the webhook here so it matches the AI's persona exactly
            webhooks = await channel.webhooks()
            wh = next((w for w in webhooks if w.name == "apicuefree_p2h"), None)
            if not wh: wh = await channel.create_webhook(name="apicuefree_p2h")
            
            await wh.send(content=content, username="apicuefree_p2h", avatar_url=bot.user.display_avatar.url)

    # Safely execute the async function from the Flask thread
    if bot_loop:
        asyncio.run_coroutine_threadsafe(send_to_discord(), bot_loop)
        
    return jsonify({"status": "success"})

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)

# ========================
# DISCORD BOT LOGIC
# ========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Keep the scrape_context helper
async def scrape_context(guild):
    context_data = {"rules": "None"}
    if not guild: return context_data
    for ch in guild.text_channels:
        if "rule" in ch.name.lower() or "info" in ch.name.lower():
            messages = [m.content async for m in ch.history(limit=5)]
            context_data["rules"] = "\n".join(messages)[:800]
            break
    return context_data

@bot.event
async def on_ready():
    global bot_loop
    bot_loop = asyncio.get_running_loop() # Capture the event loop!
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
            if not verba_key: raise ValueError("VERBA_API key missing.")

            guild_info = await scrape_context(message.guild)
            pins = [p.content for p in await message.channel.pins()]
            
            context_header = f"""
            [SYSTEM AWARENESS DATA - DO NOT REPLY TO THIS PART]
            Current Server: {message.guild.name if message.guild else "DMs"}
            Current Channel: {message.channel.name if message.guild else "DMs"}
            User Speaking: {message.author.display_name}
            Server Rules: {guild_info['rules']}
            Pinned Data: {", ".join(pins[:3]) if pins else "None"}
            [END AWARENESS DATA]
            """
            
            full_prompt = context_header + message.clean_content
            if message.embeds: full_prompt += f"\n[User embed: {message.embeds[0].description}]"

            api_url = "https://api.verba.ink/v1/response"
            headers = {"Authorization": f"Bearer {verba_key}", "Content-Type": "application/json"}
            payload = {"character": "apicuefree_p2h", "messages": [{"role": "user", "content": full_prompt}]}

            async with aiohttp.ClientSession() as session_http:
                async with session_http.post(api_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"]
                    else:
                        raise Exception(f"API Error {resp.status}: {await resp.text()}")

            bot_stats["queries"] += 1

            if message.guild:
                webhooks = await message.channel.webhooks()
                wh = next((w for w in webhooks if w.name == "apicuefree_p2h"), None)
                if not wh: wh = await message.channel.create_webhook(name="apicuefree_p2h")
                
                await wh.send(content=reply, username="apicuefree_p2h", avatar_url=bot.user.display_avatar.url, wait=True)
            else:
                await message.reply(reply)

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            await message.reply(f"⚠️ `System Error: {e}`")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
