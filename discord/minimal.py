# This example requires the 'message_content' intent.

import discord
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Set up the bot with the appropriate intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run(DISCORD_API_KEY)
