"""
Configuration file for Zerodha Kite API
Copy this file and fill in your credentials
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Zerodha Kite API Credentials
# Get these from https://kite.trade/apps/

KITE_API_KEY = os.getenv('KITE_API_KEY', 'your_api_key_here')
KITE_API_SECRET = os.getenv('KITE_API_SECRET', 'your_api_secret_here')
KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN', '')
KITE_USER_ID = os.getenv('KITE_USER_ID', '')

# Trading Configuration
DEFAULT_PRODUCT = "MIS"  # MIS (Intraday), CNC (Delivery), NRML (Carry Forward)
DEFAULT_VALIDITY = "DAY"  # DAY, IOC
DEFAULT_VARIETY = "regular"  # regular, bo (bracket), co (cover), amo (after market)
