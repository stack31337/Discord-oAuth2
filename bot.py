import discord
from discord.ext import commands
import sqlite3
import requests
import time
import asyncio
import aiohttp
from discord.ui import Button, View

token = ''

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)

def save_allowed_user_ids():
    with open('allowed_users.txt', 'w') as file:
        for user_id in allowed_user_ids:
            file.write(str(user_id) + '\n')

def load_allowed_user_ids():
    try:
        with open('allowed_users.txt', 'r') as file:
            lines = file.readlines()
            return [int(line.strip()) for line in lines]
    except FileNotFoundError:
        return []

allowed_user_ids = load_allowed_user_ids()

guilds_members_rate_limits = {}

def add_user_to_guild(user_id, access_token, guild_id):
    url = f"https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}"
    headers = {
        'Authorization': f'{token}',  # Add your bot token to here
        'Content-Type': 'application/json'
    }
    data = {'access_token': access_token}
    
    endpoint = f'guilds/{guild_id}/members'

    while True:
        current_time = time.time()
        if endpoint in guilds_members_rate_limits and guilds_members_rate_limits[endpoint] > current_time:
            wait_time = guilds_members_rate_limits[endpoint] - current_time
            print(f"Rate limit aşıldı. {wait_time:.2f} saniye bekleniyor...")
            time.sleep(wait_time)
        
        response = requests.put(url, json=data, headers=headers)

        if response.status_code == 429:
            retry_after = response.json().get('retry_after', 1) / 1000

            guilds_members_rate_limits[endpoint] = current_time + retry_after

            print(f"Rate limit aşıldı. {retry_after:.2f} saniye bekleniyor...")
            time.sleep(retry_after)
        else:
            print(f"İşlem başarıyla tamamlandı. Yanıt kodu: {response.status_code}")
            break

    return response.status_code



@bot.command()
async def join(ctx, amount: int, guild_id: int):
    if ctx.author.id not in allowed_user_ids:
        embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
        embed.set_footer(text="Sorry, you can't use this command.")
        await ctx.send(embed=embed)
        return

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT user_id, access_token FROM users')
    users = c.fetchall()

    added_count = 0
    failed_count = 0
    http_error_count = 0

    embed = discord.Embed(title="**Status**", color=0x00ff00)
    embed.set_footer(text=f'✅ Joining to server...')

    message = await ctx.send(embed=embed)

    for user_id, access_token in users:
        if added_count >= amount:
            break

        status = add_user_to_guild(user_id, access_token, guild_id)
        if status == 201:
            added_count += 1
        elif status == 204:
            failed_count += 1
        else:
            http_error_count += 1
            
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
        
        embed = discord.Embed(title="**Status**", color=0x00ff00)
        embed.set_footer(text=f'👁️ Total {user_count}\n📌 Desired {amount}\n✅ Success {added_count}\n❌ Already in server {failed_count}\n🚫 Limited {http_error_count}')
        await message.edit(embed=embed)
        time.sleep(0.1)

    conn.close()

@bot.command()
async def users(ctx):
    if ctx.author.id not in allowed_user_ids:
        embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
        embed.set_footer(text="Sorry, you can't use this command.")
        await ctx.send(embed=embed)
        return

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    user_count = c.fetchone()[0]
    conn.close()
    
    embed = discord.Embed(title="**Users**", color=0x00ff00)
    embed.set_footer(text=f'✅ OAuth 2.0 Verified Users: {user_count}')
    await ctx.send(embed=embed)

@bot.command()
async def owner(ctx):
    await ctx.send(f'**This bot authors: - ID: {allowed_user_ids}**')


rate_limits = {}

@bot.command()
@commands.has_permissions(manage_messages=True)
async def nuke(ctx):
               if ctx.author.id not in allowed_user_ids:
                              embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
                              embed.set_footer(text="Sorry, you can't use this command.")
                              await ctx.send(embed=embed)
                              return

               await ctx.channel.purge(limit=None, check=lambda m: not m.pinned)
               embed = discord.Embed(title="**Nuke**", color=0x00ff00)
               embed.set_footer(text=f'Channel has been nuked.')
               await ctx.send(embed=embed, delete_after=99)

@bot.command()
async def add_user(ctx, user_id: int):
    if ctx.author.id not in allowed_user_ids:
        embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
        embed.set_footer(text="Sorry, you can't use this command.")
        return

    allowed_user_ids.append(user_id)
    save_allowed_user_ids()
    embed = discord.Embed(title="**Whitelist**", color=0x00ff00)
    embed.set_footer(text=f'ID: {user_id} has been succesfully added whitelist.')
    await ctx.send(embed=embed)
    
@bot.command()
async def ping(ctx):
    await ctx.send(f'**Pong!** {round(bot.latency * 1000)}ms')

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

async def check_tokens():
    cursor.execute("SELECT user_id, access_token FROM users")
    users = cursor.fetchall()

    valid_count = 0
    removed_count = 0

    for user_id, access_token in users:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {access_token}"
                }
                async with session.get(f"https://discord.com/api/v9/users/@me", headers=headers) as response:
                    if response.status != 200:
                        cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                        conn.commit()
                        removed_count += 1
                        print(f"Token for user {user_id} has been removed from the database.")
                    else:
                        valid_count += 1
                        print(f"Token for user {user_id} is valid.")
        except aiohttp.ClientError as e:
            cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            removed_count += 1
            print(f"Token for user {user_id} has been removed from the database due to an error: {e}")

    await update_discord_channel(valid_count, removed_count)
    await asyncio.sleep(14400)
    await check_tokens()

async def update_discord_channel(valid_count, removed_count):
    channel_id =  1111111111 # add channel id here
    channel = bot.get_channel(channel_id)
    embed = discord.Embed(title="**Routine**")
    embed.set_footer(text=f"✅ Valid: {valid_count}\n❌ Removed: {removed_count}")
    await channel.send(embed=embed)

@bot.command()
async def invite(ctx):
    if ctx.author.id not in allowed_user_ids:
        embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
        embed.set_footer(text="Sorry, you can't use this command.")
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="You can see channels after verification.",
        description="Click the 'Access' button to confirm that you are 18 years or older and that you consent to viewing sexually content. 🔞",
        color=discord.Color.blue()
    )
    
    embed.set_image(url="https://media.discordapp.net/attachments/1074328261703782450/1084585395494338661/523x.gif?ex=65ad895c&is=659b145c&hm=caad6f1c1aa6274185309955ca03d8e7e7201626ceba1dab85ef7799e283b9ca&=&width=440&height=247")

    button = Button(style=discord.ButtonStyle.url, label="Acces", url="") # url = your auth link

    view = View()
    view.add_item(button)

    await ctx.send(embed=embed, view=view)

@bot.command()
async def link(ctx):
    if ctx.author.id not in allowed_user_ids:
        embed = discord.Embed(title="**Permission not found!**", color=0xff0000)
        embed.set_footer(text="Sorry, you can't use this command.")
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed()
    embed.set_footer(text="") # add your bot invite link here
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    await check_tokens()



bot.run(f'{token}')
