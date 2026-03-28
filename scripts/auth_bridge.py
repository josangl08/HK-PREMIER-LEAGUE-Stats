# ABOUTME: Utility script to perform OAuth 2.0 flow for Google AI (AI Studio track).
# ABOUTME: Generates a persistent 'token.json' for the Gemini Subscriber Bridge. Re-run after any scope change.

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Uses Generative Language API scope (AI Studio track — cuota por cuenta/suscripción).
# NOTE: Do NOT use 'cloud-platform' here — that routes to Vertex AI (pay-per-token).
# After changing this scope, delete token.json and re-run this script to re-authenticate.
SCOPES = ['https://www.googleapis.com/auth/generative-language']

def get_subscriber_credentials():
    """
    Returns Google OAuth credentials for the subscriber.
    If 'token.json' doesn't exist, it opens a browser for onboarding.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You need a client_secret.json from Google Cloud Console.
            # Create an "OAuth Desktop Client" in APIs & Services -> Credentials.
            if not os.path.exists('client_secret.json'):
                print("ERROR: 'client_secret.json' not found.")
                print("1. Go to Google Cloud Console (https://console.cloud.google.com/)")
                print("2. Create a project and enable 'Generative Language API'")
                print("3. Create OAuth 2.0 Client ID (Desktop App) and download JSON as 'client_secret.json'")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("SUCCESS: 'token.json' created/updated.")
    
    return creds

if __name__ == '__main__':
    result = get_subscriber_credentials()
    if result:
        print("BRIDGE ACTIVE: Using Gemini Subscriber Account (OAuth)")
    else:
        print("ERROR: Could not obtain credentials. Check client_secret.json and try again.")
