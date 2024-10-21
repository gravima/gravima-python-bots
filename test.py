import os
import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv
import re

load_dotenv()

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Set up the bot with the appropriate intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == DISCORD_CHANNEL_ID:  # ID des Channels
        args = message.content.strip().split()
        command = args[0][1:].lower()

        if command in ['antwort', 'spam', 'gelesen', 'delete']:
            if message.reference:
                try:
                    original_message = await message.channel.fetch_message(message.reference.message_id)
                    message_id_match = re.search(r'ID:\s*<([^>]+)>', original_message.content)

                    if not message_id_match:
                        await message.channel.send('E-Mail-ID konnte nicht gefunden werden.')
                        return

                    message_id = message_id_match.group(1)

                    payload = {
                        'action': command,
                        'messageId': message_id,
                        'author': message.author.name,
                        'content': ' '.join(args[1:])
                    }
                    response = requests.post(WEBHOOK_URL, json=payload)

                    if response.status_code == 200:
                        await message.channel.send(f'Dein Befehl "{command}" für E-Mail-ID "{message_id}" wurde an n8n gesendet.')
                    else:
                        await message.channel.send('Fehler beim Senden der Nachricht an n8n.')

                except Exception as e:
                    print(f'Fehler beim Abrufen oder Senden der Nachricht: {e}')
                    await message.channel.send('Fehler beim Abrufen oder Senden der Nachricht.')
            else:
                await message.channel.send('Antwort muss auf eine Originalnachricht verweisen.')

@bot.event
async def on_interaction(interaction):
    if not isinstance(interaction, discord.Interaction):
        return

    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        command, message_id = custom_id.split(':')

        try:
            payload = {
                'action': command,
                'messageId': message_id,
                'author': interaction.user.name
            }
            response = requests.post(WEBHOOK_URL, json=payload)

            if response.status_code == 200:
                await interaction.response.send_message(f'Dein Befehl "{command}" für E-Mail-ID "{message_id}" wurde an n8n gesendet.')
            else:
                await interaction.response.send_message('Fehler beim Senden der Nachricht an n8n.')

        except Exception as e:
            print(f'Fehler beim Senden der Nachricht an den Webhook: {e}')
            await interaction.response.send_message('Fehler beim Senden der Nachricht an n8n.')

bot.run(DISCORD_API_KEY)
