import os
import discord
import requests
from flask import Flask, request, jsonify
from discord.ext import commands
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

# Laden der Umgebungsvariablen aus der .env Datei
load_dotenv()

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))  # Sicherstellen, dass dies eine Ganzzahl ist
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Set up the bot with the appropriate intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Flask application for receiving updates
app = Flask(__name__)

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
                await interaction.response.send_message(f'Dein Befehl "{command}" für E-Mail-ID "{message_id}" wurde an n8n gesendet.')
            else:
                await interaction.response.send_message(f'Fehler beim Senden der Nachricht an n8n: {response.status_code} / {WEBHOOK_URL} ')

        except Exception as e:
            logging.error(f'Fehler beim Senden der Nachricht an den Webhook: {e}')
            await interaction.response.send_message('Fehler beim Senden der Nachricht an n8n.')

# Flask Route to update message status
@app.route('/update-message-status', methods=['POST'])
async def update_message_status():
    data = request.json
    message_id = data.get('messageId')
    status = data.get('status')

    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    message = await channel.fetch_message(message_id)

    if status == 'read':
        await message.edit(content=message.content + "\n✅ Nachricht wurde als gelesen markiert.")
    elif status == 'trash':
        await message.edit(content=message.content + "\n🗑️ Nachricht wurde in den Papierkorb verschoben.")

    return jsonify({'success': True}), 200

if __name__ == "__main__":
    # Running both the Discord bot and the Flask app
    from threading import Thread

    # Start Flask in a separate thread
    def run_flask():
        app.run(host='0.0.0.0', port=5000)

    # Start the Flask server
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Start the Discord bot
    bot.run(DISCORD_API_KEY)