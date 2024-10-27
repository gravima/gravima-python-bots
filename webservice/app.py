import imaplib
import time
from flask import Flask, request, jsonify
from openai import OpenAI
from bs4 import BeautifulSoup
import email
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
import os
from dotenv import load_dotenv
import logging

load_dotenv()

IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = int(os.getenv('IMAP_PORT', 993))  # Standard IMAP SSL Port
IMAP_USER = os.getenv('IMAP_USER')
IMAP_PASS = os.getenv('IMAP_PASS')
PORT = int(os.getenv('PORT', 5000))  # Standard Flask Port
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Function for IMAP connection
def connect_to_imap():
    try:
        mail = imaplib.IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        return mail, None  # successful, no error
    except imaplib.IMAP4.error as e:
        return None, f"IMAP connection failed: {str(e)}"

# Function to search UID by message_id
def getemailuidbymessage_id(message_id):
    mail, error = connect_to_imap()
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

def getmailtextbyuid(uid):
    try:
        # Connect to IMAP server
        mail, error = connect_to_imap()
        if error:
            return None

        try:
            # Select inbox and fetch email content
            mail.select('INBOX')
            result, data = mail.uid('FETCH', uid, '(RFC822)')
            
            if result != 'OK':
                return None
                
            # Parse the email content
            import email
            email_body = email.message_from_bytes(data[0][1])
            
            text_content = None
            html_content = None
            
            # Extract text content from email parts
            if email_body.is_multipart():
                for part in email_body.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition'))
                    
                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue
                        
                    try:
                        # Get the email part payload
                        payload = part.get_payload(decode=True).decode()
                    except:
                        continue
                        
                    if content_type == 'text/plain':
                        text_content = payload
                    elif content_type == 'text/html':
                        html_content = payload
            else:
                # Handle non-multipart emails
                content_type = email_body.get_content_type()
                try:
                    payload = email_body.get_payload(decode=True).decode()
                    if content_type == 'text/plain':
                        text_content = payload
                    elif content_type == 'text/html':
                        html_content = payload
                except:
                    return None
            # If plain text is available, use it
            if text_content:
                return text_content.strip()
            
            # Otherwise, convert HTML to plain text if available
            elif html_content:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                return soup.get_text(separator='\n', strip=True)
             
            return None

        finally:
            # Always logout from mail server
            mail.logout()
            
    except Exception as e:
        logging.error(f'Error retrieving email content: {str(e)}')
        return None

def create_reply_draft(uid, suggested_reply):
    """
    Creates a draft reply to an email using the suggested text.
    
    Parameters:
    uid (str): The UID of the original email to reply to
    suggested_reply (str): The suggested reply text from ChatGPT
    
    Returns:
    tuple: (success: bool, message: str)
    """
    try:
        # Connect to IMAP server
        mail, error = connect_to_imap()
        if error:
            return False, f"IMAP connection failed: {error}"

        try:
            # Select inbox and fetch original email
            mail.select('INBOX')
            result, data = mail.uid('FETCH', uid, '(RFC822)')
            
            if result != 'OK':
                return False, "Failed to fetch original email"
                
            # Parse the original email
            import email
            from email.message import EmailMessage
            from email.utils import make_msgid, formatdate
            
            original_email = email.message_from_bytes(data[0][1])
            
            # Create new message
            reply = EmailMessage()
            
            # Set basic headers
            reply['Message-ID'] = make_msgid()
            reply['Date'] = formatdate(localtime=True)
            reply['From'] = original_email.get('To')  # We are replying, so our From is their To
            
            # Set To field (original sender)
            original_from = original_email.get('From')
            reply['To'] = original_from
            
            # Set Subject
            original_subject = original_email.get('Subject', '')
            if not original_subject.lower().startswith('re:'):
                reply['Subject'] = f"Re: {original_subject}"
            else:
                reply['Subject'] = original_subject
                
            # Set In-Reply-To and References headers for proper threading
            reply['In-Reply-To'] = original_email.get('Message-ID', '')
            references = original_email.get('References', '')
            if references:
                reply['References'] = f"{references} {original_email['Message-ID']}"
            else:
                reply['References'] = original_email['Message-ID']

            # Prepare the reply text
            # First, get the original email text for quoting
            original_text = getmailtextbyuid(uid)
            if original_text:
                quoted_text = '\n'.join(f'> {line}' for line in original_text.split('\n'))
                reply_body = f"{suggested_reply}\n\n---\n\nAm {original_email['Date']} schrieb {original_from}:\n\n{quoted_text}"
            else:
                reply_body = suggested_reply

            # Set the content
            reply.set_content(reply_body)

            # Convert to string and encode
            reply_string = reply.as_string().encode('utf-8')
            
            # Append to Drafts folder
            try:
                # First, try to select 'Drafts' folder
                result = mail.select('Drafts')
                if result[0] != 'OK':
                    # If 'Drafts' doesn't exist, try 'Entwürfe' (German)
                    result = mail.select('Entwürfe')
                    if result[0] != 'OK':
                        return False, "Could not find Drafts folder"

                # Append the draft
                result = mail.append('Drafts' if result[0] == 'OK' else 'Entwürfe', 
                                   '', 
                                   imaplib.Time2Internaldate(time.time()), 
                                   reply_string)
                
                if result[0] != 'OK':
                    return False, "Failed to save draft"
                    
                return True, "Draft created successfully"
                
            except imaplib.IMAP4.error as e:
                return False, f"IMAP error while saving draft: {str(e)}"

        finally:
            # Always logout from mail server
            mail.logout()
            
    except Exception as e:
        logging.error(f'Error creating reply draft: {str(e)}')
        return False, f"Error creating reply draft: {str(e)}"

# Route IMAP - get UID by message_id
@app.route('/get-uid', methods=['POST'])
def get_uid():
    data = request.get_json()
    message_id = data.get('message_id')

    # Validate message_id
    if not message_id:
        return jsonify({'status': 'error', 'message': 'Message-ID not provided'})

    # Attempt to retrieve the UID
    uid, error = getemailuidbymessage_id(message_id)

    if error:
        # Handle error during UID retrieval
        return jsonify({'status': 'error', 'message': f'Error retrieving UID: {error}'})

    if uid:
        # Success: UID found
        return jsonify({'status': 'success', 'uid': uid, 'message': f'UID found for Message-ID'})
    else:
        # UID not found
        return jsonify({'status': 'error', 'message': f'UID not found for Message-ID {message_id}'})

# Route IMAP - move email to Trash
@app.route('/move-email', methods=['POST'])
def move_email():
    data = request.get_json()
    uid = data.get('uid')

    # Validate UID
    if not uid:
        return jsonify({'status': 'error', 'message': 'UID not provided'})

    # Connect to IMAP
    mail, error = connect_to_imap()
    if error:
        return jsonify({'status': 'error', 'message': f'IMAP connection error: {error}'})

    try:
        # Select INBOX and attempt to move the email to Trash
        mail.select('INBOX')
        result = mail.uid('MOVE', uid, 'Trash')

        if result[0] == 'OK':
            # Successful move
            return jsonify({'status': 'success', 'message': f'Email moved to Trash successfully'})
        else:
            # Failed to move email
            return jsonify({'status': 'error', 'message': f'Failed to move email with UID {uid}'})

    except imaplib.IMAP4.error as e:
        # Handle IMAP errors
        return jsonify({'status': 'error', 'message': f'MOVE command failed: {str(e)} for UID {uid}'})

    finally:
        # Always logout from the mail server
        mail.logout()

# Route IMAP - mark email as read
@app.route('/mark-as-read', methods=['POST'])
def mark_as_read():
    data = request.get_json()
    uid = data.get('uid')

    # Validate UID
    if not uid:
        return jsonify({'status': 'error', 'message': 'UID not provided'})

    # Connect to IMAP
    mail, error = connect_to_imap()
    if error:
        return jsonify({'status': 'error', 'message': f'IMAP connection error: {error}'})

    try:
        # Select INBOX
        mail.select('INBOX')

        # Set the \Seen flag to mark the email as read
        result = mail.uid('STORE', uid, '+FLAGS', '(\\Seen)')
        
        if result[0] == 'OK':
            # Success response
            return jsonify({'status': 'success', 'message': 'Email marked as read successfully'})
        else:
            # Failed to mark email as read
            return jsonify({'status': 'error', 'message': f'Failed to mark email {uid} as read'})

    except imaplib.IMAP4.error as e:
        # Handle IMAP errors
        return jsonify({'status': 'error', 'message': f'Error marking email as read: {str(e)}'})

    finally:
        # Always logout from the mail server
        mail.logout()

# Route OpenAI suggest answer
@app.route('/suggest-answer', methods=['POST'])
def suggest_answer():
    try:
        data = request.json
        uid = data.get('uid')
        user_context = data.get('context', '')

        # Get email content using helper function
        email_content = getmailtextbyuid(uid)
        
        if not email_content:
            return jsonify({
                'status': 'error',
                'message': 'Failed to retrieve email content'
            })

        # Construct prompt for ChatGPT
        prompt = f"""
        Basierend auf der folgenden E-Mail und dem Kontext, erstelle bitte eine professionelle Antwort:
        
        Original E-Mail:
        {email_content}
        
        Hinweis vom Benutzer für die Antwort:
        {user_context}
        """
        
        # Call ChatGPT API with new client
        response = client.chat.completions.create(
            model="gpt-4", 
            messages=[
                {"role": "system", "content": "Erstelle Mail-Antworten für eine Internetagentur. Ansprache Sie oder du je nach E-Mail. Halte den Ton professionell, präzise sowie strukturiert und freundlich. Bitte erstelle NUR die E-Mail-Antwort ohne Betreff, einleitende Worte oder Erläuterungen nach dem E-Mail-Text. Verzichte generell auf 'und mit Kommas' (und,)"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=500
        )
        
        suggested_reply = response.choices[0].message.content

        # success, message = create_reply_draft(uid, suggested_reply)
        
        return jsonify({
            'status': 'success',
            'message': suggested_reply
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)