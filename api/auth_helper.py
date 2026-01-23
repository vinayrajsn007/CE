"""
Authentication Helper for Zerodha Kite API
Helps with initial setup and token generation
"""

import os
import webbrowser
from .kite_client import KiteTradingClient
import logging
import sys
from pathlib import Path
# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from utils.logging_config import setup_logging

setup_logging(level=logging.INFO, log_prefix="auth")
logger = logging.getLogger(__name__)


def authenticate_kite():
    """
    Interactive authentication flow for Kite Connect
    
    Returns:
        KiteTradingClient instance with valid access token
    """
    print("=" * 60)
    print("Zerodha Kite Connect Authentication")
    print("=" * 60)
    
    # Get API credentials
    api_key = input("Enter your Kite API Key: ").strip()
    api_secret = input("Enter your Kite API Secret: ").strip()
    
    if not api_key or not api_secret:
        print("Error: API Key and Secret are required!")
        return None
    
    # Initialize client
    kite_client = KiteTradingClient(api_key=api_key, api_secret=api_secret)
    
    # Generate login URL
    login_url = kite_client.generate_login_url()
    print(f"\nOpening browser for login...")
    print(f"If browser doesn't open, visit: {login_url}")
    
    # Open browser
    webbrowser.open(login_url)
    
    # Get request token
    print("\nAfter logging in, you'll be redirected to a URL.")
    print("Copy the 'request_token' parameter from that URL.")
    request_token = input("\nEnter the request token: ").strip()
    
    if not request_token:
        print("Error: Request token is required!")
        return None
    
    try:
        # Generate session
        data = kite_client.generate_session(request_token)
        access_token = data['access_token']
        user_data = data
        
        print("\n" + "=" * 60)
        print("Authentication Successful!")
        print("=" * 60)
        print(f"User ID: {user_data.get('user_id', 'N/A')}")
        print(f"User Name: {user_data.get('user_name', 'N/A')}")
        print(f"Email: {user_data.get('email', 'N/A')}")
        print(f"\nAccess Token: {access_token}")
        print("\nSave this access token in your .env file:")
        print(f"KITE_ACCESS_TOKEN={access_token}")
        print("=" * 60)
        
        return kite_client
        
    except Exception as e:
        print(f"\nError during authentication: {e}")
        return None


def save_token_to_env(access_token, api_key=None, api_secret=None):
    """
    Save access token to .env file
    
    Args:
        access_token: Access token to save
        api_key: API key (optional)
        api_secret: API secret (optional)
    """
    env_file = ".env"
    
    try:
        # Read existing .env if it exists
        lines = []
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                lines = f.readlines()
        
        # Update or add tokens
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith('KITE_ACCESS_TOKEN='):
                new_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
                updated = True
            elif api_key and line.startswith('KITE_API_KEY='):
                new_lines.append(f'KITE_API_KEY={api_key}\n')
            elif api_secret and line.startswith('KITE_API_SECRET='):
                new_lines.append(f'KITE_API_SECRET={api_secret}\n')
            else:
                new_lines.append(line)
        
        if not updated:
            if api_key:
                new_lines.append(f'KITE_API_KEY={api_key}\n')
            if api_secret:
                new_lines.append(f'KITE_API_SECRET={api_secret}\n')
            new_lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')
        
        # Write back
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
        
        print(f"Token saved to {env_file}")
        
    except Exception as e:
        print(f"Error saving token: {e}")


if __name__ == "__main__":
    import os
    
    kite = authenticate_kite()
    
    if kite:
        # Optionally save to .env
        save_option = input("\nSave token to .env file? (y/n): ").strip().lower()
        if save_option == 'y':
            access_token = kite.access_token
            api_key = kite.api_key
            api_secret = kite.api_secret
            save_token_to_env(access_token, api_key, api_secret)
