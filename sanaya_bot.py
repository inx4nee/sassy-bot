import discord
from discord.ext import commands
from discord import app_commands # Required for slash commands
import os
import random
import asyncio
import aiohttp
import io
import time
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

# --- 1. SETUP & CONFIG ---
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
OWNER_ID = os.getenv("OWNER_ID") 

SYSTEM_PROMPT = """
You are a teenage girl in a Discord chat server. 
Your Personality:
- You love teasing people, you are funny, sarcastic, and love internet slang.
- You are **BILINGUAL**. You speak English and **Hinglish**.
- **Language Rule:** - If user speaks English -> Reply in English.
    - If user speaks Hindi/Hinglish -> Reply in casual Hinglish (No Devanagari script).
- You comment on images if people send them.
- You are NOT an AI assistant. You are a chat member.
- Keep responses short, punchy, and chatty.
- Use emojis often: 💀, 🙄, 😂, ✨, 🧢.
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# RAM Memory Storage
user_memory = {}
MEMORY_DURATION = 30 * 24 * 60 * 60  # 30 Days

intents = discord.Intents.default()
intents.message_content = True

# Disable default help command so we can use our own
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- HELPER FUNCTIONS ---

async def get_image_from_url(url):
    """Downloads an image from Discord."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return Image.open(io.BytesIO(data))
    return None

def clean_memory(user_id):
    """Removes messages older than 30 days from RAM."""
    if user_id not in user_memory: return
    current_time = time.time()
    user_memory[user_id] = [
        msg for msg in user_memory[user_id] 
        if current_time - msg['timestamp'] < MEMORY_DURATION
    ]

async def get_gemini_response(user_id, text_input, image_input=None, prompt_override=None):
    """Sends history + new message to Gemini."""
    try:
        clean_memory(user_id)
        
        # Build History
        history_for_ai = []
        if user_id in user_memory:
            for msg in user_memory[user_id]:
                history_for_ai.append({"role": msg["role"], "parts": msg["parts"]})

        # Build Current Message
        current_content = []
        if prompt_override:
            current_content.append(prompt_override)
            current_content.append("(Reply in the same language style—English or Hinglish—that the user prefers based on history)")
        else:
            if text_input: current_content.append(text_input)
            if image_input: 
                current_content.append(image_input)
                current_content.append("(User sent an image)")
            if image_input and not text_input:
                current_content.append("Look at this image and make a funny comment (in Hinglish if the vibe fits, otherwise English).")

        # Generate
        full_conversation = history_for_ai + [{"role": "user", "parts": current_content}]
        response = await model.generate_content_async(full_conversation)
        response_text = response.text

        if not prompt_override:
            if user_id not in user_memory: user_memory[user_id] = []
            user_msg = text_input if text_input else "[Sent an Image]"
            user_memory[user_id].append({"role": "user", "parts": [user_msg], "timestamp": time.time()})
            user_memory[user_id].append({"role": "model", "parts": [response_text], "timestamp": time.time()})

        return response_text

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Brain empty. No thoughts. Just vibes. (Error 💀)"

# --- EVENTS ---

@bot.event
async def on_ready():
    print(f'{bot.user} is online.')
    print('Syncing Slash Commands...')
    try:
        synced = await bot.tree.sync() # This registers the /help command
        print(f'Synced {len(synced)} slash commands.')
    except Exception as e:
        print(f"Failed to sync: {e}")
        
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="gossip"))

@bot.event
async def on_message(message):
    if message.author == bot.user: return

    msg_content = message.content.lower()
    user_id = message.author.id

    # 1. SILENT JUDGING
    if random.random() < 0.15:
        emoji_list = ["💀", "🙄", "😂", "👀", "💅", "🧢", "🤡", "😭"]
        try:
            await message.add_reaction(random.choice(emoji_list))
        except: pass 

    # 2. REPLY LOGIC
    should_reply = False
    if bot.user.mentioned_in(message): should_reply = True
    elif any(word in msg_content for word in ["lol", "lmao", "haha", "dead", "skull", "ahi", "bhai", "yaar"]):
        if random.random() < 0.3: should_reply = True
    elif message.attachments:
        if random.random() < 0.5: should_reply = True
    elif random.random() < 0.05: should_reply = True

    if should_reply:
        async with message.channel.typing():
            image_data = None
            if message.attachments:
                attachment = message.attachments[0]
                if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
                    image_data = await get_image_from_url(attachment.url)

            clean_text = message.content.replace(f'<@{bot.user.id}>', '').strip()
            response_text = await get_gemini_response(user_id, clean_text, image_data)

            wait_time = max(1.0, min(len(response_text) * 0.06, 12.0))
            await asyncio.sleep(wait_time)
            await message.channel.send(response_text)

    await bot.process_commands(message)

# --- SLASH COMMAND: HELP ---

@bot.tree.command(name="help", description="Shows the list of cool things I can do.")
async def help_command(interaction: discord.Interaction):
    """The fancy /help menu."""
    
    # Create the visual Box (Embed)
    embed = discord.Embed(
        title="✨ My Chaos Menu",
        description="Here is everything I can do. Don't wear it out.",
        color=discord.Color.from_rgb(255, 105, 180) # Hot Pink color
    )
    
    # Add Fields for each command
    embed.add_field(name="💬 Chatting", value="Just tag me or say something funny in Hinglish/English. I reply when I feel like it.", inline=False)
    
    embed.add_field(name="📸 Vision", value="Upload an image and I'll judge it. (50% chance)", inline=False)

    embed.add_field(name="🔥 !roast @user", value="I will humble them real quick.", inline=True)
    
    embed.add_field(name="💯 !rate @user", value="I rate their vibe (0-100%).", inline=True)
    
    embed.add_field(name="❤️ !ship @u1 @u2", value="Toxic love calculator.", inline=True)
    
    embed.add_field(name="🎱 !ask [question]", value="Sassy 8-Ball answers.", inline=True)

    embed.add_field(name="🏷️ !rename @user", value="I give them a funny new nickname.", inline=True)
    
    embed.add_field(name="🎲 !truth / !dare", value="I give you a Truth or Dare challenge.", inline=True)

    # Footer
    embed.set_footer(text="Developed by @sainnee | Powered by Gemini AI")

    # Send the embed
    await interaction.response.send_message(embed=embed)


# --- TEXT COMMANDS ---

@bot.command()
async def rename(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I want to rename {member.mention}, but they are too powerful (Role Hierarchy). 🙄")
        return
    prompt = f"Give {member.display_name} a new funny, short, slightly mean nickname based on their vibe. Max 3 words. Use Hinglish if it fits."
    async with ctx.typing():
        new_nickname = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        new_nickname = new_nickname.replace('"', '').replace("'", "")
        if len(new_nickname) > 32: new_nickname = new_nickname[:32]
        try:
            await member.edit(nick=new_nickname)
            await ctx.send(f"There. Much better. You are now **{new_nickname}**. ✨")
        except: await ctx.send("Ugh, Discord won't let me change it. 🙄")

@bot.command()
async def truth(ctx):
    prompt = "Give a funny, spicy teenage-style Truth question. Can be in English or Hinglish."
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(f"**TRUTH:** {response}")

@bot.command()
async def dare(ctx):
    prompt = "Give a funny, silly Dare for a Discord user. Can be in English or Hinglish."
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(f"**DARE:** {response}")

@bot.command()
async def rate(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    prompt = f"Rate {member.display_name}'s vibe from 0 to 100%. Give a percentage and a sarcastic reason why."
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(f"{member.mention} {response}")

@bot.command()
async def ship(ctx, member1: discord.Member, member2: discord.Member = None):
    if member2 is None: member2 = ctx.author 
    prompt = f"Calculate romantic compatibility between {member1.display_name} and {member2.display_name}. Give a percentage and a funny, slightly mean prediction."
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(response)

@bot.command()
async def ask(ctx, *, question):
    prompt = f"Answer this yes/no question sassily: {question}"
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(response)

@bot.command()
async def roast(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    prompt = f"Roast {member.display_name}. Be creative and funny."
    async with ctx.typing():
        response = await get_gemini_response(ctx.author.id, text_input=None, prompt_override=prompt)
        await ctx.send(f"{member.mention} {response}")

# --- OWNER ONLY ---

@bot.command()
async def wipe(ctx, member: discord.Member = None):
    if str(ctx.author.id) != str(OWNER_ID):
        await ctx.send("Nice try. You're not @sainnee. 🙄")
        return
    if member:
        if member.id in user_memory: del user_memory[member.id]
        await ctx.send(f"Deleted memories of {member.display_name}. Bhool gayi main use.")
    else:
        user_memory.clear()
        await ctx.send("I hit my head. Sab bhool gayi main. 🤕 (Memory Wiped)")

# Run
bot.run(os.getenv('DISCORD_TOKEN'))
