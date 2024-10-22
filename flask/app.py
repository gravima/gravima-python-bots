import imaplib
from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = os.getenv('IMAP_PORT')
IMAP_USER = os.getenv('IMAP_USER')
IMAP_PASS = os.getenv('IMAP_PASS')
PORT = os.getenv('PORT')

app = Flask(__name__)

def getemailuidbymessage_id(message_id):
    # Verbindung zum IMAP-Server herstellen
    mail = imaplib.IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASS)

    # Postfach auswählen
    mail.select('inbox')

    # E-Mails nach Message-ID durchsuchen
    result, data = mail.search(None, f'HEADER Message-ID "{message_id}"')

    if result == 'OK':
        email_ids = data[0].split()
        if email_ids:
            return email_ids[0].decode()
        else:
            return None
    else:
        return None

@app.route('/')
def index():
    return 'Index Page'

@app.route('/get-uid', methods=['POST'])
def get_uid():
    data = request.get_json()
    message_id = data.get('message_id')

    if not message_id:
        return jsonify({'error': 'Message-ID not provided'}), 400

    uid = getemailuidbymessage_id(message_id)

    if uid:
        return jsonify({'uid': uid}), 200
    else:
        return jsonify({'error': 'UID not found'}), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
