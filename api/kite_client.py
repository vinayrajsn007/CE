"""
Zerodha Kite Connect API Client
Handles authentication and provides trading functions
"""

import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import logging

# Load environment variables
load_dotenv()

# Setup logging (console + file)
import sys
from pathlib import Path
# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from utils.logging_config import setup_logging
setup_logging(level=logging.DEBUG, log_prefix="kite_client")

class KiteTradingClient:
    """Wrapper class for Zerodha Kite Connect API"""
    
    def __init__(self, api_key=None, api_secret=None, access_token=None):
        """
        Initialize Kite Connect client
        
        Args:
            api_key: Kite Connect API key (or from env)
            api_secret: Kite Connect API secret (or from env)
            access_token: Access token (or from env)
        """
        self.api_key = api_key or os.getenv('KITE_API_KEY')
        self.api_secret = api_secret or os.getenv('KITE_API_SECRET')
        self.access_token = access_token or os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API Key and API Secret are required")
        
        self.kite = KiteConnect(api_key=self.api_key)
        
        if self.access_token:
            self.kite.set_access_token(self.access_token)
    
    def generate_login_url(self):
        """Generate login URL for manual authentication"""
        return self.kite.login_url()
    
    def generate_session(self, request_token):
        """
        Generate access token from request token
        
        Args:
            request_token: Request token obtained after login
        
        Returns:
            Access token and user data
        """
        data = self.kite.generate_session(request_token, api_secret=self.api_secret)
        self.access_token = data['access_token']
        self.kite.set_access_token(self.access_token)
        return data
    
    def get_profile(self):
        """Get user profile"""
        return self.kite.profile()
    
    def get_margins(self):
        """Get account margins"""
        return self.kite.margins()
    
    # Order Management
    def place_order(self, variety, exchange, tradingsymbol, transaction_type, 
                   quantity, price=None, product="MIS", order_type="MARKET", 
                   validity="DAY", disclosed_quantity=None, trigger_price=None,
                   squareoff=None, stoploss=None, trailing_stoploss=None):
        """
        Place an order
        
        Args:
            variety: Order variety (regular, bo, co, amo)
            exchange: Exchange (NSE, BSE, NFO, etc.)
            tradingsymbol: Trading symbol
            transaction_type: BUY or SELL
            quantity: Order quantity
            price: Order price (for LIMIT orders)
            product: Product type (MIS, CNC, NRML)
            order_type: Order type (MARKET, LIMIT, SL, SL-M)
            validity: Validity (DAY, IOC)
            disclosed_quantity: Disclosed quantity
            trigger_price: Trigger price for SL orders
            squareoff: Square off value for bracket orders
            stoploss: Stop loss value for bracket orders
            trailing_stoploss: Trailing stop loss for bracket orders
        
        Returns:
            Order ID
        """
        order_params = {
            "variety": variety,
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "product": product,
            "order_type": order_type,
            "validity": validity
        }
        
        if price:
            order_params["price"] = price
        
        if disclosed_quantity:
            order_params["disclosed_quantity"] = disclosed_quantity
        
        if trigger_price:
            order_params["trigger_price"] = trigger_price
        
        if squareoff:
            order_params["squareoff"] = squareoff
        
        if stoploss:
            order_params["stoploss"] = stoploss
        
        if trailing_stoploss:
            order_params["trailing_stoploss"] = trailing_stoploss
        
        return self.kite.place_order(**order_params)
    
    def modify_order(self, order_id, variety="regular", price=None, quantity=None,
                    order_type=None, validity=None, disclosed_quantity=None,
                    trigger_price=None):
        """Modify an existing order"""
        params = {
            "order_id": order_id,
            "variety": variety
        }
        
        if price:
            params["price"] = price
        if quantity:
            params["quantity"] = quantity
        if order_type:
            params["order_type"] = order_type
        if validity:
            params["validity"] = validity
        if disclosed_quantity:
            params["disclosed_quantity"] = disclosed_quantity
        if trigger_price:
            params["trigger_price"] = trigger_price
        
        return self.kite.modify_order(**params)
    
    def cancel_order(self, order_id, variety="regular"):
        """Cancel an order"""
        return self.kite.cancel_order(variety=variety, order_id=order_id)
    
    def get_orders(self):
        """Get all orders"""
        return self.kite.orders()
    
    def get_order_history(self, order_id):
        """Get order history"""
        return self.kite.order_history(order_id)
    
    def get_positions(self):
        """Get current positions"""
        return self.kite.positions()
    
    def get_holdings(self):
        """Get holdings"""
        return self.kite.holdings()
    
    # Market Data
    def get_quote(self, instruments):
        """
        Get quote for instruments
        
        Args:
            instruments: List of instruments in format ["EXCHANGE:TRADINGSYMBOL"]
        
        Returns:
            Quote data
        """
        return self.kite.quote(instruments)
    
    def get_ltp(self, instruments):
        """Get Last Traded Price"""
        return self.kite.ltp(instruments)
    
    def get_ohlc(self, instruments):
        """Get OHLC data"""
        return self.kite.ohlc(instruments)
    
    def get_historical_data(self, instrument_token, from_date, to_date, interval, continuous=False):
        """
        Get historical data
        
        Args:
            instrument_token: Instrument token
            from_date: Start date (datetime object)
            to_date: End date (datetime object)
            interval: Interval (minute, day, 3minute, 5minute, etc.)
            continuous: For futures, whether to get continuous data
        
        Returns:
            Historical data
        """
        return self.kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
            continuous=continuous
        )
    
    def get_instruments(self, exchange=None):
        """Get instruments list"""
        if exchange:
            return self.kite.instruments(exchange)
        return self.kite.instruments()
    
    def search_instruments(self, exchange, symbol):
        """Search for instruments"""
        instruments = self.get_instruments(exchange)
        return [inst for inst in instruments if symbol.upper() in inst['tradingsymbol'].upper()]
