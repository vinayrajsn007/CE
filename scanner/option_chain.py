"""
NIFTY CE Option Chain Viewer
Fetches and displays all CE strikes for a given expiry date

Usage:
    python nifty_option_chain.py
    
    # Or programmatically:
    from nifty_option_chain import NiftyOptionChain
    
    chain = NiftyOptionChain(expiry_date="Jan 23")
    chain.display_chain()
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd
import logging

# Load environment variables
load_dotenv()

# Import local modules
from scanner.options_scanner import parse_expiry_date, NiftyOptionsScanner

# Setup logging (console + file)
import sys
from pathlib import Path
# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from utils.logging_config import setup_logging
setup_logging(level=logging.INFO, log_prefix="option_chain")
logger = logging.getLogger(__name__)


class NiftyOptionChain:
    """
    NIFTY CE Option Chain Viewer
    
    Fetches all CE strikes for a given expiry date (no premium filtering)
    Displays options in a simple list format
    """
    
    def __init__(self, kite_client=None, expiry_date=None):
        """
        Initialize the option chain viewer
        
        Args:
            kite_client: KiteConnect instance (optional)
            expiry_date: Expiry date string (e.g., "Jan 23", "2026-01-23")
        """
        # Initialize Kite client
        if kite_client:
            self.kite = kite_client
        else:
            api_key = os.getenv('KITE_API_KEY')
            access_token = os.getenv('KITE_ACCESS_TOKEN')
            
            if not api_key or not access_token:
                raise ValueError("KITE_API_KEY and KITE_ACCESS_TOKEN are required")
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
        
        # Parse expiry date
        if expiry_date:
            self.expiry_date = parse_expiry_date(expiry_date)
        else:
            self.expiry_date = None
        
        # Scanner configuration - no premium filtering, all strikes
        scanner_config = {
            "strike_min": 24000,
            "strike_max": 26000,
            "strike_multiple": 100,
            "premium_min": 0,  # No premium filter
            "premium_max": 10000,  # Very high limit to include all
            "refresh_interval_seconds": 5,
            "expiry_date": self.expiry_date,
            "option_types": ["CE"]  # Only CE options
        }
        
        self.scanner = NiftyOptionsScanner(kite_client=self.kite, config=scanner_config)
    
    def get_full_option_chain(self):
        """
        Get full option chain for CE options (all strikes, no premium filtering)
        
        Returns:
            Dictionary with ce_options, nifty_spot, and metadata
        """
        # Load all NIFTY options
        self.scanner.load_nifty_options()
        
        # Get all CE options (no premium filtering)
        all_ce_options = []
        
        for opt in self.scanner.nifty_options:
            if opt['instrument_type'] == 'CE':
                # Get live price
                symbol = opt['tradingsymbol']
                exchange_symbol = f"{self.scanner.config['exchange']}:{symbol}"
                
                try:
                    quote = self.kite.quote([exchange_symbol])
                    if exchange_symbol in quote:
                        price_data = quote[exchange_symbol]
                        opt_with_price = {
                            'symbol': symbol,
                            'strike': opt['strike'],
                            'expiry': opt['expiry'],
                            'instrument_token': opt['instrument_token'],
                            'ltp': price_data.get('last_price', 0),
                            'volume': price_data.get('volume', 0),
                            'oi': price_data.get('oi', 0)
                        }
                        all_ce_options.append(opt_with_price)
                except Exception as e:
                    logger.warning(f"Error fetching price for {symbol}: {e}")
        
        # Sort by strike
        all_ce_options.sort(key=lambda x: x['strike'])
        
        # Get NIFTY spot
        nifty_spot = self.scanner.get_nifty_spot_price()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'nifty_spot': nifty_spot,
            'expiry_date': self.expiry_date,
            'ce_options': all_ce_options,
            'ce_count': len(all_ce_options)
        }
    
    def display_chain(self):
        """Display the option chain in a simple format"""
        chain_data = self.get_full_option_chain()
        
        ce_options = chain_data['ce_options']
        nifty_spot = chain_data['nifty_spot']
        expiry_str = self.expiry_date.strftime('%d-%b-%Y') if self.expiry_date else 'All'
        
        print("\n" + "═" * 100)
        print(f"  NIFTY CE OPTION CHAIN - Expiry: {expiry_str}")
        print(f"  NIFTY Spot: ₹{nifty_spot:,.2f} | Total CE Options: {len(ce_options)}")
        print("═" * 100)
        
        if ce_options:
            print(f"{'Strike':<8} {'Symbol':<25} {'LTP':<12} {'Volume':<12} {'OI':<15}")
            print("-" * 100)
            
            for opt in ce_options:
                strike = opt['strike']
                symbol = opt['symbol']
                ltp = f"₹{opt['ltp']:.2f}" if opt['ltp'] > 0 else "-"
                volume = f"{opt['volume']:,}" if opt['volume'] else "0"
                oi = f"{opt['oi']:,}" if opt['oi'] else "0"
                
                print(f"{strike:<8} {symbol:<25} {ltp:<12} {volume:<12} {oi:<15}")
            
            print("═" * 100)
        else:
            print("  No CE options found for the specified expiry date")
        
        print()


def main():
    """Main entry point"""
    print("\n" + "═" * 100)
    print("  NIFTY CE OPTION CHAIN VIEWER")
    print("═" * 100)
    
    try:
        # Get expiry date from user
        print("\nEnter expiry date in any of these formats:")
        print("  - 'Jan 23' or '23 Jan'")
        print("  - 'Jan 23 2026' or '23 Jan 2026'")
        print("  - '2026-01-23' (ISO format)")
        print("─" * 100)
        
        expiry_input = input("\nEnter Expiry Date (e.g., Jan 23): ").strip()
        
        if not expiry_input:
            print("Expiry date is required")
            return
        
        # Create chain viewer
        chain = NiftyOptionChain(expiry_date=expiry_input)
        
        # Display chain
        chain.display_chain()
        
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
