import imaplib
from flask import Flask, request, jsonify
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

    if not uid:
        return jsonify({'error': 'UID not provided'}), 400

    mail, error = connect_to_imap()
    if error:
        return jsonify({'error': error}), 500

    try:
        # Postfach auswählen
        mail.select('INBOX')

        # Das \Seen-Flag setzen, um die E-Mail als gelesen zu markieren
        result = mail.uid('STORE', uid, '+FLAGS', '(\\Seen)')
        if result[0] == 'OK':
            return jsonify({'message': f'Email {uid} marked as read'}), 200
        else:
            return jsonify({'error': f'Failed to mark email {uid} as read'}), 500
    except imaplib.IMAP4.error as e:
        return jsonify({'error': f'Error marking email as read: {str(e)}'}), 500
    finally:
        mail.logout()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)