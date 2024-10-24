import os
import discord
import requests
import re
from discord.ext import commands
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

# Laden der Umgebungsvariablen aus der .env Datei
load_dotenv()

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))  # Sicherstellen, dass dies eine Ganzzahl ist
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))  # Standard Flask Port

app = Flask(__name__)

# Set up the bot with the appropriate intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Event when the bot is ready and connected to Discord
@bot.event
async def on_ready():
    logging.info(f'Bot is online as {bot.user}')
    logging.info(f'Messages will be send to {WEBHOOK_URL}')

# Event to handle button interactions (custom buttons in Discord)
@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        try:
            custom_id = interaction.data['custom_id']
            command, message_id = custom_id.split(':')

            # Erstelle die Daten, die an den Webhook gesendet werden sollen
            payload = {
                'action': command,
                'messageId': message_id,
                'author': interaction.user.name
            }

            # Sende die Daten per POST an den Webhook
            headers = {'Content-Type': 'application/json'}
            response = requests.post(WEBHOOK_URL, json=payload, headers=headers)

            if response.status_code == 200:
                await interaction.response.send_message(f'Dein Befehl "{command}" wurde weitergeleitet!')
            else:
                await interaction.response.send_message(f'Fehler beim Senden der Nachricht an n8n: {response.status_code} / {WEBHOOK_URL} ')

        except Exception as e:
            logging.error(f'Fehler beim Senden der Nachricht an den Webhook: {e}')
            await interaction.response.send_message('Fehler beim Senden der Nachricht an n8n.')

# Starte den Bot
bot.run(DISCORD_API_KEY)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)