import os
from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class GoogleAuthService:
    """Service for Google OAuth authentication"""
    
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
    
    async def verify_google_token(self, token: str) -> Optional[Dict]:
        """Verify Google OAuth token and return user info"""
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.client_id
            )
            
            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                return None
            
            # Extract user information
            user_info = {
                "google_id": idinfo['sub'],
                "email": idinfo['email'],
                "email_verified": idinfo.get('email_verified', False),
                "full_name": idinfo.get('name'),
                "picture": idinfo.get('picture')
            }
            
            return user_info
            
        except ValueError as e:
            # Invalid token
            print(f"Google token verification failed: {e}")
            return None
        except Exception as e:
            print(f"Error verifying Google token: {e}")
            return None


google_auth_service = GoogleAuthService()
