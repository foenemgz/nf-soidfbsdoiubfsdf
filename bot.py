import discord
from discord.ext import commands
from keep_alive import keep_alive
keep_alive()
import youtube_dl
import asyncio
import random

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True

# Bot Prefix
bot = commands.Bot(command_prefix=",", intents=intents)

# Sniped Messages Storage (now with more than 600 messages per channel)
sniped_messages = {}  # {channel_id: [list of (content, author, created_at)]}

# Music Queue
music_queue = []

# YTDL + FFMPEG Settings
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extractaudio': True,
    'audioformat': "mp3",
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

@bot.event
async def on_ready():
    print(f'✅ Bot is online as {bot.user}')

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    
    # Check if the channel already has sniped messages
    if message.channel.id not in sniped_messages:
        sniped_messages[message.channel.id] = []
    
    # Insert the deleted message at the front of the list
    sniped_messages[message.channel.id].insert(0, (message.content, message.author, message.created_at))
    
    # Keep only the last 600 deleted messages per channel (Adjustable limit)
    if len(sniped_messages[message.channel.id]) > 600:
        sniped_messages[message.channel.id].pop()

async def play_music(ctx):
    if len(music_queue) > 0:
        voice_channel = ctx.author.voice.channel
        vc = ctx.voice_client
        if not vc:
            vc = await voice_channel.connect()

        url = music_queue[0]['url']
        title = music_queue[0]['title']

        vc.play(discord.FFmpegPCMAudio(url, **ffmpeg_options), after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f"🎶 Now playing: `{title}`")
    else:
        await ctx.voice_client.disconnect()

async def play_next(ctx):
    if len(music_queue) > 0:
        music_queue.pop(0)
        if len(music_queue) > 0:
            await play_music(ctx)

# Music Commands
@bot.command()
async def play(ctx, *, search):
    if ctx.author.voice is None:
        return await ctx.send("❌ You must be in a voice channel to play music!")
    
    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await voice_channel.connect()

    async with ctx.typing():
        info = ytdl.extract_info(search, download=False)
        url = info['url']
        title = info.get('title', 'Unknown Title')
        music_queue.append({'url': url, 'title': title})

        if not ctx.voice_client.is_playing():
            await play_music(ctx)
        else:
            await ctx.send(f"✅ Added to queue: `{title}`")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped the song.")
    else:
        await ctx.send("❌ Nothing is playing right now.")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        await ctx.voice_client.pause()
        await ctx.send("⏸️ Paused the music.")
    else:
        await ctx.send("❌ Nothing is playing.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        await ctx.voice_client.resume()
        await ctx.send("▶️ Resumed the music.")
    else:
        await ctx.send("❌ Music is not paused.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        music_queue.clear()
        await ctx.voice_client.disconnect()
        await ctx.send("🛑 Stopped music and disconnected.")
    else:
        await ctx.send("❌ I'm not in a voice channel.")

@bot.command()
async def queue(ctx):
    if len(music_queue) == 0:
        await ctx.send("🎵 Queue is empty!")
    else:
        queue_list = ""
        for idx, song in enumerate(music_queue):
            queue_list += f"{idx+1}. {song['title']}\n"
        await ctx.send(f"📜 **Current Queue:**\n{queue_list}")

# Moderation Commands
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f'🔨 Banned {member.mention} for {reason}')

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'👢 Kicked {member.mention} for {reason}')

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, time=None, *, reason=None):
    guild = ctx.guild
    muted_role = discord.utils.get(guild.roles, name="Muted")
    if not muted_role:
        muted_role = await guild.create_role(name="Muted")
        for channel in guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False)
    
    await member.add_roles(muted_role)
    await ctx.send(f'🔇 Muted {member.mention} for {reason}')

    if time:
        # Parse the time (e.g., 1m, 1h, 1d)
        try:
            if time.endswith('m'):
                duration = int(time[:-1]) * 60
            elif time.endswith('h'):
                duration = int(time[:-1]) * 3600
            elif time.endswith('d'):
                duration = int(time[:-1]) * 86400
            else:
                raise ValueError("Invalid time format")
            
            await asyncio.sleep(duration)
            await member.remove_roles(muted_role)
            await ctx.send(f'🔊 {member.mention} has been unmuted after {time}.')
        except ValueError:
            await ctx.send("❌ Invalid time format. Please use 'm' for minutes, 'h' for hours, or 'd' for days.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    guild = ctx.guild
    muted_role = discord.utils.get(guild.roles, name="Muted")
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f'🔊 {member.mention} has been unmuted.')
    else:
        await ctx.send("❌ This user is not muted.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, member: discord.User):
    await ctx.guild.unban(member)
    await ctx.send(f'🔓 Unbanned {member.mention}.')

@bot.command()
@commands.has_permissions(kick_members=True)
async def unkick(ctx, member: discord.User):
    # To unkick, we'd need to re-invite the user, so we'll just send an info message
    await ctx.send(f"👢 {member.mention} has been un-kicked (re-invited).")

# Utility Commands
@bot.command()
async def ping(ctx):
    await ctx.send(f'🏓 Pong! `{round(bot.latency * 1000)}ms`')

@bot.command()
async def say(ctx, *, message):
    await ctx.send(message)

@bot.command()
async def eightball(ctx, *, question):
    responses = ['It is certain.', 'Outlook not so good.', 'Yes.', 'No.', 'Maybe.']
    await ctx.send(f'🎱 {random.choice(responses)}')

@bot.command()
async def shutdown(ctx):
    if ctx.author.id != 1078021613641011290:
        await ctx.send("❌ You are not authorized to shut me down.")
        return
    await ctx.send("👋 Shutting down...")
    await bot.close()

@bot.command()
async def helpme(ctx):
    help_text = """
**📜 Commands List:**
Moderation:
,ban @user reason - Ban a user
,kick @user reason - Kick a user
,mute @user reason - Mute a user
,unmute @user - Unmute a user
,unban @user - Unban a user
,unkick @user - Unkick a user

Utilities:
,ping - Check bot latency
,say [message] - Bot repeats your message
,eightball [question] - Ask the magic 8-ball
,s - Snipe the last deleted message

Music:
,play [song name/link] - Play music
,skip - Skip current song
,pause - Pause the music
,resume - Resume music
,queue - Show current music queue
,stop - Stop music and leave VC
"""
    await ctx.send(help_text)

# Snipe Command (now using ,s)
@bot.command(name='s')
async def snipe(ctx, number: int = 1):
    number = number - 1  # Because list is 0-indexed
    try:
        snipe_list = sniped_messages.get(ctx.channel.id, [])
        if len(snipe_list) == 0:
            return await ctx.send("❌ No messages to snipe in this channel!")
        
        content, author, time = snipe_list[number]
        await ctx.send(f"🕵️ **Sniped Message #{number+1}:**\n> {content}\n- Sent by **{author}** at `{time.strftime('%Y-%m-%d %H:%M:%S')}`")
    except IndexError:
        await ctx.send("❌ I couldn't find that many sniped messages!")

# New delete sniped messages command
@bot.command(name='delete')
async def delete_snipes(ctx):
    if ctx.channel.id in sniped_messages:
        sniped_messages[ctx.channel.id].clear()
        await ctx.send("🗑️ Successfully cleared all sniped messages in this channel!")
    else:
        await ctx.send("❌ No sniped messages to delete in this channel.")

# RUN THE BOT
bot.run('your bot token')  # <-- Replace with your new bot token safely
