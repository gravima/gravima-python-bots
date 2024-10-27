import imaplib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def connect_to_imap():
    """Establish connection to IMAP server using environment variables."""
    try:
        # Get credentials from environment variables
        IMAP_HOST = os.getenv('IMAP_HOST')
        IMAP_PORT = int(os.getenv('IMAP_PORT', 993))
        IMAP_USER = os.getenv('IMAP_USER')
        IMAP_PASS = os.getenv('IMAP_PASS')

        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        return mail, None
    except imaplib.IMAP4.error as e:
        return None, f"IMAP connection failed: {str(e)}"

def get_uid_by_message_id(message_id):
    """
    Retrieve the UID of an email using its Message-ID.
    
    Args:
        message_id (str): The Message-ID to look up
        
    Returns:
        tuple: (uid, error_message) - If successful, uid contains the UID and error_message is None.
               If unsuccessful, uid is None and error_message contains the error description.
    """
    # Clean the message ID if it contains brackets
    message_id = message_id.strip('<>') if message_id else message_id
    
    # Connect to IMAP server
    mail, error = connect_to_imap()
    if error:
        return None, error

    try:
        # Select inbox
        mail.select('inbox')
        
        # Search for the email with the given Message-ID
        result, data = mail.search(None, f'HEADER Message-ID "{message_id}"')

        if result == 'OK':
            email_ids = data[0].split()
            if email_ids:
                # Get the UID for the found message
                result, data = mail.fetch(email_ids[0], '(UID)')
                if result == 'OK':
                    # Extract UID from the response
                    uid = data[0].decode().split()[2].strip(')')
                    return uid, None
                else:
                    return None, 'Failed to fetch UID'
            else:
                return None, 'No emails found with that Message-ID'
        else:
            return None, 'Search for Message-ID failed'
    except imaplib.IMAP4.error as e:
        return None, f"IMAP error: {str(e)}"
    finally:
        mail.logout()

def main():
    """Main function to demonstrate usage."""
    # Example message ID
    message_id = "017701db1e4c$0ae291d0$20a7b570$@gravima.de"
    
    # Get the UID
    uid, error = get_uid_by_message_id(message_id)
    
    if error:
        print(f"Error: {error}")
    else:
        print(f"UID found: {uid}")

if __name__ == "__main__":
    main()