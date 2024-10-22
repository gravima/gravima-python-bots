import imaplib
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = int(os.getenv('IMAP_PORT', 993))  # Standard IMAP SSL Port
IMAP_USER = os.getenv('IMAP_USER')
IMAP_PASS = os.getenv('IMAP_PASS')
PORT = int(os.getenv('PORT', 5000))  # Standard Flask Port

app = Flask(__name__)

# Hilfsfunktion zum Aufbau der IMAP-Verbindung
def connect_to_imap():
    try:
        mail = imaplib.IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        return mail, None  # Erfolgreich, also kein Fehler
    except imaplib.IMAP4.error as e:
        return None, f"IMAP connection failed: {str(e)}"

# Funktion zur Suche der UID per Message-ID
def getemailuidbymessage_id(message_id):
    mail, error = connect_to_imap()  # Korrektes Entpacken
    if error:
        return None, error

    try:
        mail.select('inbox')
        result, data = mail.search(None, f'HEADER Message-ID "{message_id}"')

        if result == 'OK':
            email_ids = data[0].split()
            if email_ids:
                result, data = mail.fetch(email_ids[0], '(UID)')
                if result == 'OK':
                    uid = data[0].decode().split()[2].strip(')')
                    return uid, None
                else:
                    return None, 'Failed to fetch UID'
            else:
                return None, 'No emails found with that Message-ID'
        else:
            return None, 'Search for Message-ID failed'
    finally:
        mail.logout()

import requests

DISCORD_BOT_UPDATE_URL = os.getenv('DISCORD_BOT_UPDATE_URL')

# Sendet eine Benachrichtigung an den Discord-Bot, um die Nachricht zu aktualisieren
def notify_discord(message_id, status):
    payload = {
        'messageId': message_id,
        'status': status
    }

    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post("https://pythonbot.gravima.de/update-message-status", json=payload, headers=headers)
        if response.status_code == 200:
            return True
        else:
            print(f"Fehler beim Senden der Aktualisierung an Discord: {response.status_code}")
            return False
    except Exception as e:
        print(f"Exception beim Senden der Aktualisierung an Discord: {str(e)}")
        return False

# Route zum Abrufen der UID
@app.route('/get-uid', methods=['POST'])
def get_uid():
    data = request.get_json()
    message_id = data.get('message_id')

    if not message_id:
        return jsonify({'error': 'Message-ID not provided'}), 400

    uid, error = getemailuidbymessage_id(message_id)

    if error:
        return jsonify({'error': error}), 500
    if uid:
        return jsonify({'uid': uid}), 200
    else:
        return jsonify({'error': 'UID not found'}), 404

# Route zum Verschieben der E-Mail
@app.route('/move-email', methods=['POST'])
def move_email():
    data = request.get_json()
    uid = data.get('uid')

    if not uid:
        return jsonify({'error': 'UID not provided'}), 400

    mail, error = connect_to_imap()  # Korrektes Entpacken
    if error:
        return jsonify({'error': error}), 500

    try:
        mail.select('INBOX')
        result = mail.uid('MOVE', uid, 'Trash')
        if result[0] == 'OK':
            notify_discord(message_id, 'trash')
            return jsonify({'message': 'Email moved to Trash successfully', 'uid': uid}), 200
        else:
            return jsonify({'error': 'Failed to move email', 'uid': uid}), 500
    except imaplib.IMAP4.error as e:
        return jsonify({'error': f'MOVE command failed: {str(e)}', 'uid': uid}), 500
    finally:
        mail.logout()

# Route zum Markieren einer E-Mail als gelesen
@app.route('/mark-as-read', methods=['POST'])
def mark_as_read():
    data = request.get_json()
    uid = data.get('uid')
    message_id = data.get('message_id')  # Hier wird die messageId von Discord übergeben

    if not uid:
        logging.error('UID not provided')
        return jsonify({'error': 'UID not provided'}), 400

    logging.info(f'Received request to mark as read for UID: {uid}, message_id: {message_id}')
    
    mail, error = connect_to_imap()
    if error:
        logging.error(f'IMAP connection error: {error}')
        return jsonify({'error': error}), 500

    try:
        mail.select('INBOX')
        result = mail.uid('STORE', uid, '+FLAGS', '(\\Seen)')
        if result[0] == 'OK':
            logging.info(f'Successfully marked email {uid} as read')

            # Nach dem erfolgreichen Markieren als gelesen, Discord benachrichtigen
            notify_discord(message_id, 'read')
            return jsonify({'message': f'Email {uid} marked as read'}), 200
        else:
            logging.error(f'Failed to mark email {uid} as read')
            return jsonify({'error': f'Failed to mark email {uid} as read'}), 500
    except imaplib.IMAP4.error as e:
        logging.error(f'IMAP error while marking as read: {e}')
        return jsonify({'error': f'Error marking email as read: {str(e)}'}), 500
    finally:
        mail.logout()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)