import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from mcstatus import JavaServer, BedrockServer
from datetime import datetime
from flask import Flask
from threading import Thread
from motor.motor_asyncio import AsyncIOMotorClient

app = Flask('')

@app.route('/')
def home():
    return "LiveMC Pro V4 Zinda Hai! 🔥 34 Features Active"

def run():
  app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("TOKEN") # <-- NAYA TOKEN DAALNA BHAI
MONGO_URI = os.getenv("MONGO_URI")
UPDATE_INTERVAL = 120
# ============================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo_client["LiveMC"]
servers_collection = db["servers"]
print("MongoDB Connected ✅")
class MongoDict:
    def __init__(self):
        self.cache = {}
    
    async def load_all(self):
        async for doc in servers_collection.find({}):
            self.cache[doc["guild_id"]] = doc.get("servers", {})
    
    def __getitem__(self, guild_id):
        return self.cache.get(str(guild_id), {})
    
    def __setitem__(self, guild_id, value):
        self.cache[str(guild_id)] = value
        asyncio.create_task(self._save(str(guild_id)))
    
    async def _save(self, guild_id):
        await servers_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"servers": self.cache[guild_id]}},
            upsert=True
        )
    
    def __contains__(self, guild_id):
        return str(guild_id) in self.cache
    
    def items(self):
        return self.cache.items()
    
    def __delitem__(self, guild_id):
        if str(guild_id) in self.cache:
            del self.cache[str(guild_id)]
            asyncio.create_task(servers_collection.delete_one({"guild_id": str(guild_id)}))

servers_data = MongoDict()
# PURANI save_data CALLS KO IGNORE KARNE KE LIYE  
def save_data(data): pass
async def safe_mcping(ip, port):
    try:
        async with asyncio.timeout(5):
            server = JavaServer.lookup(f"{ip}:{port}")
            status = await server.async_status()
            return status, False
    except:
        pass
    try:
        async with asyncio.timeout(5):
            server = BedrockServer.lookup(f"{ip}:{port}")
            status = await server.async_status()
            return status, True
    except Exception as e:
        print(f"Ping Error: {e}")
        return None, None

def create_progress_bar(current, maximum, length=20):
    if maximum == 0:
        return "`[────────────────────]` **0.0%**"
    percent = (current / maximum) * 100
    filled = int((current / maximum) * length)
    if percent >= 85: bar = "🟩" * filled + "⬛" * (length - filled)
    elif percent >= 60: bar = "🟨" * filled + "⬛" * (length - filled)
    elif percent >= 30: bar = "🟧" * filled + "⬛" * (length - filled)
    else: bar = "🟥" * filled + "⬛" * (length - filled)
    return f"`{bar}` **{percent:.1f}%**"

# YAHI WALA PANEL HAI BHAI - SIRF BUGS FIX KIYE
def create_embed(server_name, status, data):
    uptime_data = data.get('uptime_data', {})
    online, offline = uptime_data.get('online_time', 0), uptime_data.get('offline_time', 0)
    total = online + offline
    uptime_percent = 100.0 if total == 0 else (online / total) * 100

    # OFFLINE PANEL - TERA SS WALA STYLE
    if status is None:
        color = 0x2b2d31
        embed = discord.Embed(color=color)
        display_name = data.get('custom_name', server_name)
        embed.set_author(name=f"⚫ {display_name}", icon_url="https://i.imgur.com/3J3t7yG.png")
        embed.description = f"### 🔴 **OFFLINE**\n{create_progress_bar(0, 1)}"
        embed.add_field(name="👥 Players", value="**0**/**0**", inline=True)
        embed.add_field(name="📶 Ping", value="`---ms`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"**{uptime_percent:.1f}%**", inline=True)
        embed.add_field(name="⚙️ Version", value="`Server Offline`", inline=True)
        embed.add_field(name="🔥 Peak", value=f"**{uptime_data.get('peak_players', 0)}**", inline=True)
        embed.add_field(name="🎮 Modes", value=f"{data.get('games', '`Not Set`')}", inline=True)
        embed.add_field(name="💬 MOTD", value=">>> *Server is offline. Start it to begin tracking.*", inline=False)
        embed.set_footer(text=f"{data.get('footer', 'LiveMC | Free Server Tracker • Auto-Update')}")
        # FIXED: IMAGE HATA DIYA - AB ERROR NAHI AAYEGA
        embed.timestamp = datetime.now()
        return embed

    # ONLINE PANEL - TERA SS WALA STYLE
    if status.latency < 50: color = 0x00ffc6
    elif status.latency < 100: color = 0x00d4ff
    elif status.latency < 200: color = 0x7B68EE
    elif status.latency < 400: color = 0xffb700
    else: color = 0xff3e3e

    version_clean = status.version.name.replace("Paper ", "").replace("Spigot ", "").replace("Purpur ", "").replace("Fabric ", "").replace("Forge ", "").replace("Waterfall ", "").replace("Velocity ", "")
    if not version_clean or version_clean.isspace(): version_clean = "Custom"

    status_text = f"🟢 **ONLINE**"
    players_text = f"**{status.players.online}**/**{status.players.max}**"
    motd = status.motd.to_plain().replace("\n", " ⏐ ")[:130]
    icon_url = f"https://api.mcsrvstat.us/icon/{data.get('ip')}"
    edition = "☕ **Java**" if not data.get('is_bedrock') else "📱 **Bedrock**"
    ping_text = f"`{int(status.latency)}ms`"

    embed = discord.Embed(color=data.get('color', color))
    display_name = data.get('custom_name', server_name)
    embed.set_author(name=f"⚡ {display_name}", icon_url=icon_url)
    embed.description = f"### {status_text} ⏐ {edition}\n{create_progress_bar(status.players.online, status.players.max)}"
    embed.add_field(name="👥 Players", value=players_text, inline=True)
    embed.add_field(name="📶 Ping", value=ping_text, inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"**{uptime_percent:.1f}%**", inline=True)
    embed.add_field(name="⚙️ Version", value=f"`{version_clean}`", inline=True)
    embed.add_field(name="🔥 Peak", value=f"**{uptime_data.get('peak_players', 0)}**", inline=True)
    embed.add_field(name="🎮 Modes", value=f"{data.get('games', '`Not Set`')}", inline=True)
    embed.add_field(name="💬 MOTD", value=f">>> {motd}", inline=False)
    embed.set_footer(text=f"{data.get('footer', 'LiveMC | Free Server Tracker • Auto-Update')}")
    embed.set_thumbnail(url=icon_url)
    # FIXED: IMAGE SIRF TAB JAB USER NE SET KI HO
    if data.get('banner'):
        embed.set_image(url=data['banner'])
    embed.timestamp = datetime.now()
    return embed

async def check_server_exists(interaction, server):
    guild_id = str(interaction.guild.id)
    if guild_id not in servers_data or server not in servers_data[guild_id]:
        try:
            await interaction.followup.send(f"❌ Server `{server}` not found! Use `/listservers` to check.", ephemeral=True)
        except:
            pass
        return False
    return True

@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_all_servers():
    tasks_list = []
    for guild_id, servers in servers_data.items():
        for server_name, data in servers.items():
            tasks_list.append(update_server_panel(guild_id, server_name, data))
            await asyncio.sleep(1)
    if tasks_list: await asyncio.gather(*tasks_list, return_exceptions=True)

class LiveMCView(discord.ui.View):
    def __init__(self, ip, port, server_name):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄", custom_id=f"refresh_{server_name}", row=0))
        self.add_item(discord.ui.Button(label="Vote", style=discord.ButtonStyle.link, emoji="⭐", url="https://top.gg", row=0))
        self.add_item(discord.ui.Button(label="Website", style=discord.ButtonStyle.link, emoji="🔗", url=f"https://mcsrvstat.us/server/{ip}:{port}", row=0))

async def update_server_panel(guild_id, server_name, data):
    try:
        channel = bot.get_channel(data['channel_id'])
        if not channel: return
        result = await safe_mcping(data['ip'], data['port'])
        status = result[0] if result[0] else None
        embed = create_embed(server_name, status, data)
        view = LiveMCView(data['ip'], data['port'], server_name)

        try:
            message = await channel.fetch_message(data['message_id'])
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            msg = await channel.send(embed=embed, view=view)
            servers_data[guild_id][server_name]['message_id'] = msg.id
            save_data(servers_data)
        except Exception as e:
            print(f"Edit Error: {e}")

        if status is None and data.get('was_online', True):
            role = channel.guild.get_role(data.get('alert_role'))
            if role:
                alert_embed = discord.Embed(title="⚠️ SERVER OFFLINE", description=f"**{server_name}** is now offline!", color=0xff3e3e)
                await channel.send(content=role.mention, embed=alert_embed)
            servers_data[guild_id][server_name]['was_online'] = False
            save_data(servers_data)
        elif status and not data.get('was_online', True):
            role = channel.guild.get_role(data.get('alert_role'))
            if role:
                alert_embed = discord.Embed(title="✅ SERVER ONLINE", description=f"**{server_name}** is back online!", color=0x00ffc6)
                await channel.send(content=role.mention, embed=alert_embed)
            servers_data[guild_id][server_name]['was_online'] = True
            save_data(servers_data)
    except Exception as e:
        print(f"Update Error: {e}")

@tasks.loop(seconds=120)
async def track_uptime():
    for guild_id, servers in servers_data.items():
        for server_name, data in servers.items():
            result = await safe_mcping(data['ip'], data['port'])
            status = result[0] if result[0] else None
            if 'uptime_data' not in servers_data[guild_id][server_name]:
                servers_data[guild_id][server_name]['uptime_data'] = {"online_time": 0, "offline_time": 0, "peak_players": 0, "down_history": []}
            uptime_data = servers_data[guild_id][server_name]['uptime_data']
            if status:
                uptime_data['online_time'] += 60
                if status.players.online > uptime_data['peak_players']:
                    uptime_data['peak_players'] = status.players.online
            else:
                uptime_data['offline_time'] += 60
                if data.get('was_online', True):
                    uptime_data['down_history'].append(datetime.now().isoformat())
                    if len(uptime_data['down_history']) > 10: uptime_data['down_history'].pop(0)
    save_data(servers_data)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await servers_data.load_all()  # ← YE NAYI LINE
    # FIXED: BUTTONS KO PERSISTENT BANAO
    for guild_id, servers in servers_data.items():
        for server_name, data in servers.items():
            bot.add_view(LiveMCView(data['ip'], data['port'], server_name))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e: print(f"Sync Error: {e}")
    update_all_servers.start()
    track_uptime.start()
    print("LiveMC Pro V4 Ready! 34 Features Loaded!")

@bot.event
async def on_guild_remove(guild):
    guild_id = str(guild.id)
    if guild_id in servers_data:
        del servers_data[guild_id]
        save_data(servers_data)

# UPDATED: AB CUSTOM NAME WALA SETUP
@bot.tree.command(name="setup", description="Add a Minecraft server to track")
@app_commands.describe(name="Server identifier - Use IP:PORT format", ip="Server IP", port="Server Port")
async def setup(interaction: discord.Interaction, name: str, ip: str, port: int):
    try:
        name = name.lower().strip()
        name = name.replace(" ", "-")

        await interaction.response.defer(ephemeral=True)

        if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send("❌ I need 'Send Messages' permission in this channel", ephemeral=True)
            return

        result = await safe_mcping(ip, port)
        if result[0] is None:
            await interaction.followup.send("❌ Invalid IP/Port or server is offline", ephemeral=True)
            return

        status, is_bedrock = result
        edition_name = "Bedrock" if is_bedrock else "Java"

        guild_id = str(interaction.guild.id)
        server_key = f"{ip}:{port}"

        if guild_id not in servers_data:
            servers_data[guild_id] = {}

        if len(servers_data[guild_id]) >= 10:
            await interaction.followup.send("❌ Maximum 10 servers per Discord for free tier", ephemeral=True)
            return

        temp_data = {"ip": ip, "port": port, "is_bedrock": is_bedrock, "color": 0x00ff6c, "footer": "LiveMC | Free Server Tracker"}
        embed = create_embed(server_key, status, temp_data)
        view = LiveMCView(ip, port, server_key)

        msg = await interaction.channel.send(embed=embed, view=view)

        servers_data[guild_id][server_key] = {
            "ip": ip,
            "port": port,
            "is_bedrock": is_bedrock,
            "channel_id": interaction.channel.id,
            "message_id": msg.id,
            "was_online": True,
            "color": 0x00ff6c,
            "footer": "LiveMC | Free Server Tracker • Auto-Update",
            "custom_name": name
        }

        # save_data(servers_data) # <- Comment rakha hai, jab function banayega tab uncomment karna

        await interaction.followup.send(f"✅ Server `{server_key}` setup complete!")

    except Exception as e: # <- YE SABSE ZARURI FIX HAI
        print(f"SETUP ERROR: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(f"❌ An error occurred: `{str(e)}`")


@bot.tree.command(name="listservers", description="List all tracked servers in this Discord")
async def listservers(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        if guild_id not in servers_data or not servers_data[guild_id]:
            await interaction.followup.send("❌ No servers are being tracked!", ephemeral=True)
            return
        embed = discord.Embed(title="📋 **Tracked Servers**", description="All active server monitors in this guild", color=0x00d4ff)
        for name, data in servers_data[guild_id].items():
            edition = "📱 Bedrock" if data.get('is_bedrock') else "☕ Java"
            display_name = data.get('custom_name', name)
            embed.add_field(name=f"**{display_name}**", value=f"{edition} • Channel: <#{data['channel_id']}>\n`{name}`", inline=False)
        embed.set_footer(text="LiveMC Pro")
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"List Error: {e}")

@bot.tree.command(name="removeserver", description="Stop tracking a server")
@app_commands.describe(server="Server name like play.example.com:25565")
async def removeserver(interaction: discord.Interaction, server: str):
    try:
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild.id)
        if not await check_server_exists(interaction, server): return
        del servers_data[guild_id][server]
        save_data(servers_data)
        await interaction.followup.send(f"✅ **{server}** removed successfully!", ephemeral=True)
    except Exception as e:
        print(f"Remove Error: {e}")

@bot.tree.command(name="players", description="Get online player list")
@app_commands.describe(server="Server name")
async def players(interaction: discord.Interaction, server: str):
    try:
        await interaction.response.defer()
        if not await check_server_exists(interaction, server): return
        data = servers_data[str(interaction.guild.id)][server]
        result = await safe_mcping(data['ip'], data['port'])
        status = result[0] if result[0] else None
        if status and status.players.online > 0:
            embed = discord.Embed(title=f"👥 **Online Players - {server}**", color=0x00ffc6)
            if hasattr(status.players, 'sample') and status.players.sample:
                player_list = "\n".join([f"• {p.name}" for p in status.players.sample[:20]])
                embed.description = f"```\n{player_list}\n```"
                embed.set_footer(text=f"Showing {len(status.players.sample)} of {status.players.online} players")
            else:
                embed.description = f"**{status.players.online}** players online\n*Enable `enable-query=true` in server.properties to see names*"
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Server is offline or no players online!", ephemeral=True)
    except Exception as e:
        print(f"Players Error: {e}")

@bot.tree.command(name="uptime", description="Check server uptime statistics")
@app_commands.describe(server="Server name")
async def uptime(interaction: discord.Interaction, server: str):
    try:
        await interaction.response.defer()
        if not await check_server_exists(interaction, server): return
        data = servers_data[str(interaction.guild.id)][server].get('uptime_data', {})
        online, offline = data.get('online_time', 0), data.get('offline_time', 0)
        total = online + offline
        percent = 100.0 if total == 0 else (online / total) * 100
        embed = discord.Embed(title=f"📊 **Statistics - {server}**", color=0x7B68EE)
        embed.add_field(name="⏰ **Uptime**", value=f"**{percent:.2f}%**\n`{int(online/3600)}h online`", inline=True)
        embed.add_field(name="🔥 **Peak Players**", value=f"**{data.get('peak_players', 0)}**", inline=True)
        embed.add_field(name="📅 **Tracked For**", value=f"**{int(total/3600)}h**\n`{int(total/86400)} days`", inline=True)
        embed.set_footer(text="LiveMC Pro Stats")
        embed.timestamp = datetime.now()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"Uptime Error: {e}")

@bot.tree.command(name="setcolor", description="Set custom embed color")
@app_commands.describe(server="Server name", hex_color="Hex color like #ff0000")
async def setcolor(interaction: discord.Interaction, server: str, hex_color: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        try:
            color = int(hex_color.replace("#", ""), 16)
        except:
            await interaction.followup.send("❌ Invalid hex color! Use format `#ff0000`", ephemeral=True)
            return
        servers_data[str(interaction.guild.id)][server]['color'] = color
        save_data(servers_data)
        await interaction.followup.send(f"✅ Embed color updated to `{hex_color}`!", ephemeral=True)
    except Exception as e:
        print(f"Color Error: {e}")

@bot.tree.command(name="setbanner", description="Set custom GIF banner")
@app_commands.describe(server="Server name", url="Direct GIF/Image URL")
async def setbanner(interaction: discord.Interaction, server: str, url: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        servers_data[str(interaction.guild.id)][server]['banner'] = url
        save_data(servers_data)
        await interaction.followup.send(f"✅ Banner updated successfully!", ephemeral=True)
    except Exception as e:
        print(f"Banner Error: {e}")

@bot.tree.command(name="setfooter", description="Set custom footer text")
@app_commands.describe(server="Server name", text="Footer text")
async def setfooter(interaction: discord.Interaction, server: str, text: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        servers_data[str(interaction.guild.id)][server]['footer'] = text
        save_data(servers_data)
        await interaction.followup.send(f"✅ Footer updated!", ephemeral=True)
    except Exception as e:
        print(f"Footer Error: {e}")

@bot.tree.command(name="setgames", description="Set game modes text")
@app_commands.describe(server="Server name", text="Game modes like Survival, Bedwars")
async def setgames(interaction: discord.Interaction, server: str, text: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        servers_data[str(interaction.guild.id)][server]['games'] = text
        save_data(servers_data)
        await interaction.followup.send(f"✅ Game modes updated!", ephemeral=True)
    except Exception as e:
        print(f"Games Error: {e}")

@bot.tree.command(name="setalertrole", description="Set role to ping on downtime")
@app_commands.describe(server="Server name", role="Role to mention")
async def setalertrole(interaction: discord.Interaction, server: str, role: discord.Role):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        servers_data[str(interaction.guild.id)][server]['alert_role'] = role.id
        save_data(servers_data)
        await interaction.followup.send(f"✅ Alert role set to {role.mention}!", ephemeral=True)
    except Exception as e:
        print(f"Role Error: {e}")

@bot.tree.command(name="setchannel", description="Change status panel channel")
@app_commands.describe(server="Server name", channel="New channel")
async def setchannel(interaction: discord.Interaction, server: str, channel: discord.TextChannel):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send("❌ I don't have permission to send messages in that channel!", ephemeral=True)
            return
        servers_data[str(interaction.guild.id)][server]['channel_id'] = channel.id
        save_data(servers_data)
        await interaction.followup.send(f"✅ Panel channel changed to {channel.mention}!", ephemeral=True)
    except Exception as e:
        print(f"Channel Error: {e}")

@bot.tree.command(name="forceupdate", description="Force update server panel")
@app_commands.describe(server="Server name")
async def forceupdate(interaction: discord.Interaction, server: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        data = servers_data[str(interaction.guild.id)][server]
        await update_server_panel(str(interaction.guild.id), server, data)
        await interaction.followup.send(f"✅ Panel updated for **{server}**!", ephemeral=True)
    except Exception as e:
        print(f"Force Error: {e}")

@bot.tree.command(name="resetstats", description="Reset server statistics")
@app_commands.describe(server="Server name")
async def resetstats(interaction: discord.Interaction, server: str):
    try:
        await interaction.response.defer(ephemeral=True)
        if not await check_server_exists(interaction, server): return
        servers_data[str(interaction.guild.id)][server]['uptime_data'] = {"online_time": 0, "offline_time": 0, "peak_players": 0, "down_history": []}
        save_data(servers_data)
        await interaction.followup.send(f"✅ Statistics reset for **{server}**!", ephemeral=True)
    except Exception as e:
        print(f"Reset Error: {e}")
@bot.tree.command(name="help", description="LiveMC ke sabhi commands")
async def help_cmd(interaction: discord.Interaction):
    
    embed = discord.Embed(
        title="🟢 LiveMC • Command Panel",
        description="**Best Minecraft Server Tracker for Discord**\n`24/7 Monitoring • Auto-Update • Java & Bedrock`",
        color=0x57F287
    )
    
    embed.add_field(
        name="🚀 **Setup Commands**",
        value="```\n/setup ip:port\n└ Server add karo tracking ke liye\n└ Example: /setup ip:play.hypixel.net\n```",
        inline=False
    )
    
    embed.add_field(
        name="📡 **Tracking Commands**",
        value="```\n/players     - Live player list\n/listservers - Tracked servers dekho\n```",
        inline=True
    )
    
    embed.add_field(
        name="⚙️ **Manage Commands**",
        value="```\n/setchannel   - Panel move karo\n/forceupdate  - Refresh karo\n/removeserver - Server hatao\n/resetstats   - Stats reset\n```",
        inline=True
    )
    
    embed.add_field(
        name="🔔 **Alert Command**",
        value="```\n/setalertrole server @role\n└ Server offline hone pe ping\n```",
        inline=False
    )
    
    embed.add_field(
        name="📊 **Bot Info**",
        value=f"```\nGuilds: {len(bot.guilds)}\nPing: {round(bot.latency * 1000)}ms\nVersion: v2.5\n```",
        inline=False
    )
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="LiveMC • Start with /setup")
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    update_all_servers.start()
    track_uptime.start()
    print("✅ Auto-update started! 2 min")
    
if __name__ == "__main__":
    keep_alive()
    bot.run(BOT_TOKEN)
