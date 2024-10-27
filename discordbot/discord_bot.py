import os
import discord
from discord.ext import commands
from discord import ui
import requests
# from flask import Flask, request, jsonify
from quart import Quart, request, jsonify
from dotenv import load_dotenv
import logging
import multiprocessing
import sys
import signal
from functools import partial
import asyncio

def handle_exception(loop, context):
    logging.error(f"Caught exception: {context['message']}")
    exception = context.get('exception')
    if exception:
        logging.error(f"Exception details: {exception}")

asyncio.get_event_loop().set_exception_handler(handle_exception)

logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT2 = int(os.getenv('PORT2', 4210))

# Initialize Flask app
app = Quart(__name__)

# Set up the bot with the appropriate intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'Bot is online as {bot.user}')
    logging.info(f'Messages will be sent to {WEBHOOK_URL}')

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        try:
            # Add debug logging
            logging.info(f"=== Interaction Debug Info ===")
            logging.info(f"Message ID from interaction: {interaction.message.id}")
            logging.info(f"Message reference: {interaction.message.reference if hasattr(interaction.message, 'reference') else 'No reference'}")
            logging.info(f"Channel ID: {interaction.channel_id}")
            logging.info(f"Raw interaction data: {interaction.data}")

            # Extract the action and message ID from the custom_id
            custom_id = interaction.data['custom_id']
            command, message_id = custom_id.split(':')
            discord_message_id = interaction.message.id  # ID of the original message
            logging.info(f"Discord message ID: {discord_message_id}")

            user_name = interaction.user.name

            if command == 'suggest':
                # For 'suggest' action, collect context from the user via a modal
                await collect_context_and_send_webhook(interaction, command, message_id, discord_message_id, user_name)
            else:
                # For other actions, send the webhook immediately
                await interaction.response.defer(ephemeral=False)
                await build_and_send_webhook(command, message_id, discord_message_id, user_name, context="")
        except Exception as e:
            logging.error(f'Error in on_interaction: {e}')
            await interaction.response.send_message('Error handling interaction.', ephemeral=True)

async def collect_context_and_send_webhook(interaction, command, message_id, discord_message_id, user_name):
    try:
        logging.info(f"Collecting context for command: {command}, message_id: {message_id}, discord_message_id: {discord_message_id}, user_name: {user_name}")

        class ContextModal(discord.ui.Modal):
            def __init__(self, command, message_id, discord_message_id, user_name):
                super().__init__(title="Provide Context")
                self.command = command
                self.message_id = message_id
                self.discord_message_id = discord_message_id
                self.user_name = user_name
                self.context_input = discord.ui.TextInput(
                    label="Additional Context",
                    placeholder="Enter any additional context or instructions...",
                    style=discord.TextStyle.paragraph,
                    required=False,
                    max_length=1000
                )
                self.add_item(self.context_input)

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    context = self.context_input.value or ""
                    logging.info(f"Modal submitted with context: {context}")
                    # Verwende die Instanzvariablen
                    await build_and_send_webhook(
                        self.command,
                        self.message_id,
                        self.discord_message_id,
                        self.user_name,
                        context
                    )
                    await modal_interaction.response.defer(ephemeral=False)
                except Exception as e:
                    logging.error(f'Error in modal on_submit: {e}')
                    await modal_interaction.response.send_message("An error occurred.", ephemeral=True)

        # Zeige das Modal an und übergebe die Variablen
        modal = ContextModal(command, message_id, discord_message_id, user_name)
        logging.info("Sending modal to the user")
        await interaction.response.send_modal(modal)
    except Exception as e:
        logging.error(f"Error in collect_context_and_send_webhook: {e}")
        await interaction.response.send_message('Error collecting context.', ephemeral=True)

async def build_and_send_webhook(command, message_id, discord_message_id, user_name, context):
    # Prepare the payload for the webhook
    payload = {
        'action': command,
        'messageId': message_id,
        'discordMessageId': str(discord_message_id),
        'context': context,
        'author': user_name
    }

    # Send the data via POST to the webhook
    headers = {'Content-Type': 'application/json'}
    response = requests.post(WEBHOOK_URL, json=payload, headers=headers)
    if response.status_code != 200:
        logging.error(f'Error sending webhook: {response.status_code}')
    else:
        logging.info(f'Webhook called successfully with payload {payload}')

# Route - Update Discord message
@app.route('/update-message', methods=['POST'])
async def update_message():
    try:
        logging.info("Request received at /update-message")

        # JSON-Daten vom Request abrufen
        data = await request.get_json()
        logging.info(f"Request JSON data: {data}")

        action = data.get('action')
        status = data.get('status')
        message = data.get('message')
        discord_message_id = str(data.get('discordMessageId'))
        logging.info(f"Parsed parameters - action: {action}, status: {status}, message: {message}, discord_message_id: {discord_message_id}")

        suggested_reply = ""
        if action == "suggest":
            suggested_reply = message
            message = "Created suggested answer"
            logging.info(f"Suggested reply prepared")

        # Definiere die Statusnachricht basierend auf dem status
        if status == 'success':
            status_message = f':white_check_mark: {message}'
        else:
            status_message = f':x: {message}'
        
        logging.info(f"Status message set to: {status_message}")

        # Discord API-URL für das Bearbeiten der Nachricht
        url = f'https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages/{discord_message_id}'
        logging.info(f"Discord API URL: {url}")

        # Authorization Header für die Discord API
        headers = {
            'Authorization': f'Bot {DISCORD_API_KEY}',
            'Content-Type': 'application/json'
        }

        # Step 1: Fetch the original message content
        logging.info("Fetching the original Discord message content")
        get_response = requests.get(url, headers=headers)
        logging.info(f"GET response status code: {get_response.status_code}")

        if get_response.status_code != 200:
            logging.error("Failed to retrieve the original Discord message")
            return jsonify({'status': 'error', 'message': 'Failed to retrieve the original Discord message'})

        # Get the original message with all content including components
        original_data = get_response.json()
        original_message = original_data.get("content")
        original_components = original_data.get("components", [])

        logging.info(f"Original message content: {original_message}")
        logging.info(f"Original components: {original_components}")

        # Append the new status message with a line break
        updated_message = f"{original_message}\n\n{status_message}"
        logging.info(f"Updated message content: {updated_message}")

        # Prepare the new components based on the action
        new_components = []
        if action == "trash":
            # Remove all buttons
            new_components = []
        elif action == "read":
            # Keep all buttons except "Mark as Read"
            for row in original_components:
                new_row = {
                    "type": row["type"],
                    "components": [
                        comp for comp in row["components"]
                        if not (comp["type"] == 2 and "Mark as Read" in comp.get("label", ""))
                    ]
                }
                if new_row["components"]:  # Only add row if it has components
                    new_components.append(new_row)
        elif action == "suggest":
            # Keep all buttons
            new_components = original_components

        # Prepare the payload for updating the message
        payload = {
            'content': updated_message,
            'components': new_components
        }
        
        logging.info(f"PATCH payload prepared: {payload}")

        # Sende PATCH-Request, um die Nachricht zu aktualisieren
        patch_response = requests.patch(url, json=payload, headers=headers)
        logging.info(f"PATCH response status code: {patch_response.status_code}")

        # Additional step: If action is suggest, reply with the suggested reply
        if action == "suggest" and suggested_reply:
            logging.info("Sending suggested reply")
            reply_payload = {
                'content': suggested_reply,
                'message_reference': {
                    'message_id': discord_message_id,
                    'channel_id': DISCORD_CHANNEL_ID
                }
            }
            reply_url = f'https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages'
            logging.info(f"POST reply payload: {reply_payload}")

            reply_response = requests.post(reply_url, json=reply_payload, headers=headers)
            logging.info(f"Reply POST response status code: {reply_response.status_code}")

            if reply_response.status_code == 200:
                logging.info("Suggested reply sent successfully")
                return jsonify({'status': 'success', 'message': 'Replied with suggested message'})
            else:
                logging.error("Failed to send suggested reply")
                return jsonify({'status': 'error', 'message': 'Failed to send suggested reply'})

        if patch_response.status_code == 200:
            logging.info("Discord message updated successfully")
            return jsonify({'status': 'success', 'message': 'Updated Discord message'})
        else:
            logging.error("Failed to update Discord message")
            return jsonify({'status': 'error', 'message': 'Failed to update Discord message'})

    except Exception as e:
        # Log with exception details for complete traceback
        logging.exception('Error while updating Discord message')
        return jsonify({'status': 'error', 'message': 'Exception occurred'})

async def run_bot():
    await bot.start(DISCORD_API_KEY)

async def run_app():
    await app.run_task(host='0.0.0.0', port=PORT2)

async def main():
    try:
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        
        # Gemeinsamer Signal-Handler für beide Plattformen
        def shutdown_handler(signum, frame):
            logging.info(f"Received signal {signum}, initiating shutdown...")
            # Alle Tasks abbrechen
            for task in asyncio.all_tasks(loop):
                task.cancel()
        
        # Signal-Handler registrieren (sowohl für Windows als auch Unix)
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        
        # Tasks erstellen und ausführen
        bot_task = asyncio.create_task(run_bot())
        app_task = asyncio.create_task(run_app())
        
        await asyncio.gather(bot_task, app_task)
        
    except asyncio.CancelledError:
        logging.info("Main task was cancelled, shutting down...")
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")
    finally:
        logging.info("Cleaning up...")
        # Alle verbleibenden Tasks beenden
        for task in asyncio.all_tasks(loop):
            if not task.done() and task is not asyncio.current_task():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logging.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received at top level")
    finally:
        logging.info("Program terminated")