"""
NIFTY Options Scanner
Based on ADR-003: Scans NIFTY options in a strike range and filters by premium range
Runs every 5 seconds to fetch live market data from Kite Connect

Features:
- Configurable strike price range (25000-26000)
- Configurable premium range (80-120)
- User input for expiry date (e.g., "Jan 20", "23 Jan", "2026-01-23")
- Real-time LTP updates every 5 seconds
"""

import os
import time
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd
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
setup_logging(level=logging.INFO, log_prefix="scanner")
logger = logging.getLogger(__name__)


def parse_expiry_date(expiry_input, year=None):
    """
    Parse expiry date from various input formats
    
    Supported formats:
    - "Jan 20" or "20 Jan" (assumes current year)
    - "Jan 20 2026" or "20 Jan 2026"
    - "2026-01-20" (ISO format)
    - "20-01-2026" or "20/01/2026"
    - datetime.date object
    
    Args:
        expiry_input: Expiry date string or date object
        year: Year to use if not specified (defaults to current year)
    
    Returns:
        datetime.date object
    """
    if expiry_input is None:
        return None
    
    # If already a date object, return as-is
    if isinstance(expiry_input, datetime):
        return expiry_input.date()
    if hasattr(expiry_input, 'year'):  # datetime.date
        return expiry_input
    
    if year is None:
        year = datetime.now().year
    
    expiry_str = str(expiry_input).strip()
    
    # Try various date formats
    formats = [
        # Month Day formats
        "%b %d",        # "Jan 20"
        "%B %d",        # "January 20"
        "%d %b",        # "20 Jan"
        "%d %B",        # "20 January"
        # Month Day Year formats
        "%b %d %Y",     # "Jan 20 2026"
        "%B %d %Y",     # "January 20 2026"
        "%d %b %Y",     # "20 Jan 2026"
        "%d %B %Y",     # "20 January 2026"
        # ISO and other formats
        "%Y-%m-%d",     # "2026-01-20"
        "%d-%m-%Y",     # "20-01-2026"
        "%d/%m/%Y",     # "20/01/2026"
        "%m/%d/%Y",     # "01/20/2026"
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(expiry_str, fmt)
            # If year not in format, use provided year
            if "%Y" not in fmt:
                parsed = parsed.replace(year=year)
            return parsed.date()
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse expiry date: '{expiry_input}'. "
                    f"Try formats like 'Jan 20', '20 Jan', '2026-01-20'")


def get_available_expiries(kite, underlying="NIFTY"):
    """
    Get list of available expiry dates for an underlying
    
    Args:
        kite: KiteConnect instance
        underlying: Underlying name (default: NIFTY)
    
    Returns:
        List of expiry dates sorted ascending
    """
    try:
        instruments = kite.instruments("NFO")
        df = pd.DataFrame(instruments)
        
        # Filter for underlying options
        nifty_df = df[
            (df['name'] == underlying) &
            (df['instrument_type'].isin(['CE', 'PE']))
        ]
        
        # Get unique expiries and sort
        expiries = sorted(nifty_df['expiry'].unique())
        
        # Filter for future expiries only
        today = datetime.now().date()
        future_expiries = [exp for exp in expiries if exp >= today]
        
        return future_expiries
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")
        return []


class NiftyOptionsScanner:
    """
    NIFTY Options Scanner
    
    Scans NIFTY options within a strike price range (24000-26000)
    and filters options with premium between 70-130 INR.
    Refreshes every 5 seconds with live market data.
    """
    
    def __init__(self, kite_client=None, config=None):
        """
        Initialize the scanner
        
        Args:
            kite_client: KiteConnect client instance (optional, will create if not provided)
            config: Configuration dictionary (optional, uses defaults)
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
        
        # Default configuration
        default_config = {
            "strike_min": 24000,
            "strike_max": 26000,
            "strike_multiple": 100,  # Only strikes in multiples of 100 (24000, 24100, etc.)
            "premium_min": 70,
            "premium_max": 130,
            "refresh_interval_seconds": 5,
            "underlying": "NIFTY",
            "exchange": "NFO",
            "option_types": ["CE", "PE"],
            "expiry_date": None  # Specific expiry date (e.g., "Jan 20", "2026-01-20")
        }
        
        # Merge with provided config
        self.config = {**default_config, **(config or {})}
        
        # Parse expiry date if provided
        if self.config.get('expiry_date'):
            self.expiry_date = parse_expiry_date(self.config['expiry_date'])
            logger.info(f"Expiry date set to: {self.expiry_date.strftime('%d-%b-%Y')}")
        else:
            self.expiry_date = None
        
        # Cache for instruments
        self.instruments_cache = None
        self.nifty_options = []
        self.last_instrument_load = None
        
        # State tracking
        self.is_running = False
        self.scan_count = 0
    
    def load_nifty_options(self, force_reload=False):
        """
        Load and cache all NIFTY options from NFO exchange
        
        Args:
            force_reload: Force reload instruments even if cached
        
        Returns:
            List of NIFTY options in the strike range
        """
        # Check if we need to reload (reload once per day or if forced)
        if not force_reload and self.instruments_cache is not None:
            if self.last_instrument_load and \
               datetime.now() - self.last_instrument_load < timedelta(hours=12):
                return self.nifty_options
        
        logger.info("Loading NIFTY options from NFO exchange...")
        
        try:
            # Fetch all NFO instruments
            instruments = self.kite.instruments("NFO")
            self.instruments_cache = instruments
            self.last_instrument_load = datetime.now()
            
            # Convert to DataFrame for easier filtering
            df = pd.DataFrame(instruments)
            
            # Filter for NIFTY options only
            nifty_df = df[
                (df['name'] == self.config['underlying']) &
                (df['instrument_type'].isin(self.config['option_types']))
            ].copy()
            
            # Filter by strike range
            nifty_df = nifty_df[
                (nifty_df['strike'] >= self.config['strike_min']) &
                (nifty_df['strike'] <= self.config['strike_max'])
            ]
            
            # Filter by strike multiple (only strikes in multiples of 100)
            strike_multiple = self.config.get('strike_multiple', 100)
            if strike_multiple > 0:
                nifty_df = nifty_df[nifty_df['strike'] % strike_multiple == 0]
                logger.info(f"Filtered to strikes in multiples of {strike_multiple}")
            
            # Apply expiry filter if specified
            if self.expiry_date:
                nifty_df = self._filter_by_expiry(nifty_df)
            
            # Sort by strike and type
            nifty_df = nifty_df.sort_values(['strike', 'instrument_type'])
            
            self.nifty_options = nifty_df.to_dict('records')
            
            logger.info(f"Loaded {len(self.nifty_options)} NIFTY options in strike range "
                       f"{self.config['strike_min']}-{self.config['strike_max']}")
            
            return self.nifty_options
            
        except Exception as e:
            logger.error(f"Error loading instruments: {e}")
            raise
    
    def _filter_by_expiry(self, df):
        """
        Filter options by specific expiry date
        
        Args:
            df: DataFrame of options
        
        Returns:
            Filtered DataFrame matching the expiry date
        """
        if df.empty or self.expiry_date is None:
            return df
        
        # Get unique expiries
        available_expiries = sorted(df['expiry'].unique())
        
        # Check if exact expiry exists
        if self.expiry_date in available_expiries:
            return df[df['expiry'] == self.expiry_date]
        
        # Try to find closest matching expiry (within 1 day tolerance for edge cases)
        for exp in available_expiries:
            if abs((exp - self.expiry_date).days) <= 1:
                logger.warning(f"Exact expiry {self.expiry_date} not found, using {exp}")
                self.expiry_date = exp
                return df[df['expiry'] == exp]
        
        # Expiry not found - show available expiries
        logger.error(f"Expiry date {self.expiry_date} not found!")
        logger.info("Available expiries:")
        for exp in available_expiries[:10]:
            logger.info(f"  - {exp.strftime('%d-%b-%Y')}")
        
        return df[df['expiry'] == self.expiry_date]  # Will return empty
    
    def get_live_prices(self, options_list):
        """
        Fetch live LTP for a list of options
        
        Args:
            options_list: List of option dictionaries with tradingsymbol
        
        Returns:
            Dictionary mapping tradingsymbol to price data
        """
        if not options_list:
            return {}
        
        # Build instrument list for API call
        # Format: "NFO:NIFTY2612025500CE"
        instruments = [
            f"{self.config['exchange']}:{opt['tradingsymbol']}" 
            for opt in options_list
        ]
        
        # Kite has a limit of 1000 instruments per call
        # Split into batches if needed
        batch_size = 500
        all_prices = {}
        
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i + batch_size]
            
            try:
                # Use quote() for more detailed data
                quotes = self.kite.quote(batch)
                all_prices.update(quotes)
            except Exception as e:
                logger.error(f"Error fetching quotes for batch {i//batch_size + 1}: {e}")
        
        return all_prices
    
    def filter_by_premium_range(self, options_list, prices):
        """
        Filter options by premium (LTP) range
        
        Args:
            options_list: List of option dictionaries
            prices: Dictionary of prices from get_live_prices()
        
        Returns:
            Tuple of (ce_options, pe_options) filtered by premium
        """
        ce_options = []
        pe_options = []
        
        for opt in options_list:
            symbol = opt['tradingsymbol']
            exchange_symbol = f"{self.config['exchange']}:{symbol}"
            
            if exchange_symbol not in prices:
                continue
            
            price_data = prices[exchange_symbol]
            ltp = price_data.get('last_price', 0)
            
            # Check if LTP is in range
            if self.config['premium_min'] < ltp < self.config['premium_max']:
                # Enrich option data with live price info
                option_with_price = {
                    'symbol': symbol,
                    'strike': opt['strike'],
                    'type': opt['instrument_type'],
                    'expiry': opt['expiry'],
                    'instrument_token': opt['instrument_token'],
                    'ltp': ltp,
                    'ohlc': price_data.get('ohlc', {}),
                    'volume': price_data.get('volume', 0),
                    'oi': price_data.get('oi', 0),
                    'change': self._calculate_change(price_data)
                }
                
                if opt['instrument_type'] == 'CE':
                    ce_options.append(option_with_price)
                else:
                    pe_options.append(option_with_price)
        
        # Sort by LTP
        ce_options.sort(key=lambda x: x['ltp'])
        pe_options.sort(key=lambda x: x['ltp'])
        
        return ce_options, pe_options
    
    def _calculate_change(self, price_data):
        """Calculate price change percentage"""
        ltp = price_data.get('last_price', 0)
        ohlc = price_data.get('ohlc', {})
        prev_close = ohlc.get('close', 0)
        
        if prev_close and prev_close > 0:
            change_pct = ((ltp - prev_close) / prev_close) * 100
            return round(change_pct, 2)
        return 0
    
    def get_nifty_spot_price(self):
        """Get current NIFTY spot price"""
        try:
            quote = self.kite.quote(["NSE:NIFTY 50"])
            return quote.get("NSE:NIFTY 50", {}).get("last_price", 0)
        except Exception as e:
            logger.error(f"Error fetching NIFTY spot: {e}")
            return 0
    
    def display_results(self, ce_options, pe_options, nifty_spot):
        """
        Display formatted scan results
        
        Args:
            ce_options: List of filtered CE options
            pe_options: List of filtered PE options
            nifty_spot: Current NIFTY spot price
        """
        current_time = datetime.now()
        next_update = current_time + timedelta(seconds=self.config['refresh_interval_seconds'])
        
        # Clear screen (optional - comment out if running in IDE)
        # os.system('clear' if os.name != 'nt' else 'cls')
        
        print("\n" + "═" * 80)
        print(f"  NIFTY OPTIONS SCANNER - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 80)
        
        # Show expiry date and configuration
        expiry_display = self.expiry_date.strftime('%d-%b-%Y') if self.expiry_date else "All"
        strike_multiple = self.config.get('strike_multiple', 100)
        
        print(f"  Expiry: {expiry_display} | Strikes: {self.config['strike_min']}-{self.config['strike_max']} (x{strike_multiple})")
        print(f"  Premium Range: ₹{self.config['premium_min']} - ₹{self.config['premium_max']} | NIFTY Spot: ₹{nifty_spot:,.2f}")
        
        # Display CE Options
        print("\n  " + "─" * 76)
        print("  📈 CALL OPTIONS (CE) - Premium ₹{}-₹{}".format(
            self.config['premium_min'], self.config['premium_max']))
        print("  " + "─" * 76)
        
        if ce_options:
            print("  | {:<22} | {:>7} | {:>8} | {:>8} | {:>12} |".format(
                "Symbol", "Strike", "LTP", "Change", "Expiry"))
            print("  |" + "-" * 24 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + 
                  "-" * 10 + "|" + "-" * 14 + "|")
            
            for opt in ce_options:
                expiry_str = opt['expiry'].strftime('%d-%b-%Y') if opt['expiry'] else 'N/A'
                change_str = f"{opt['change']:+.2f}%" if opt['change'] else "0.00%"
                print("  | {:<22} | {:>7} | ₹{:>6.2f} | {:>8} | {:>12} |".format(
                    opt['symbol'],
                    int(opt['strike']),
                    opt['ltp'],
                    change_str,
                    expiry_str
                ))
            print(f"\n  Total CE Options Found: {len(ce_options)}")
        else:
            print("  No CE options found in premium range")
        
        # Display PE Options
        print("\n  " + "─" * 76)
        print("  📉 PUT OPTIONS (PE) - Premium ₹{}-₹{}".format(
            self.config['premium_min'], self.config['premium_max']))
        print("  " + "─" * 76)
        
        if pe_options:
            print("  | {:<22} | {:>7} | {:>8} | {:>8} | {:>12} |".format(
                "Symbol", "Strike", "LTP", "Change", "Expiry"))
            print("  |" + "-" * 24 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + 
                  "-" * 10 + "|" + "-" * 14 + "|")
            
            for opt in pe_options:
                expiry_str = opt['expiry'].strftime('%d-%b-%Y') if opt['expiry'] else 'N/A'
                change_str = f"{opt['change']:+.2f}%" if opt['change'] else "0.00%"
                print("  | {:<22} | {:>7} | ₹{:>6.2f} | {:>8} | {:>12} |".format(
                    opt['symbol'],
                    int(opt['strike']),
                    opt['ltp'],
                    change_str,
                    expiry_str
                ))
            print(f"\n  Total PE Options Found: {len(pe_options)}")
        else:
            print("  No PE options found in premium range")
        
        print("\n" + "═" * 80)
        print(f"  Scan #{self.scan_count} | Last Updated: {current_time.strftime('%H:%M:%S')} | "
              f"Next Update: {next_update.strftime('%H:%M:%S')} ({self.config['refresh_interval_seconds']}s)")
        print("═" * 80)
    
    def scan_once(self):
        """
        Perform a single scan
        
        Returns:
            Tuple of (ce_options, pe_options, nifty_spot)
        """
        self.scan_count += 1
        
        # Load/refresh instruments if needed
        self.load_nifty_options()
        
        # Get live prices
        prices = self.get_live_prices(self.nifty_options)
        
        # Filter by premium range
        ce_options, pe_options = self.filter_by_premium_range(self.nifty_options, prices)
        
        # Get NIFTY spot
        nifty_spot = self.get_nifty_spot_price()
        
        return ce_options, pe_options, nifty_spot
    
    def run(self, max_scans=None, display=True):
        """
        Run the scanner continuously
        
        Args:
            max_scans: Maximum number of scans (None for infinite)
            display: Whether to display results to console
        """
        self.is_running = True
        self.scan_count = 0
        
        logger.info("Starting NIFTY Options Scanner...")
        logger.info(f"Configuration: Strike {self.config['strike_min']}-{self.config['strike_max']}, "
                   f"Premium ₹{self.config['premium_min']}-₹{self.config['premium_max']}")
        
        try:
            while self.is_running:
                try:
                    # Perform scan
                    ce_options, pe_options, nifty_spot = self.scan_once()
                    
                    # Display results
                    if display:
                        self.display_results(ce_options, pe_options, nifty_spot)
                    
                    # Check max scans
                    if max_scans and self.scan_count >= max_scans:
                        logger.info(f"Completed {max_scans} scans. Stopping...")
                        break
                    
                    # Wait for next scan
                    time.sleep(self.config['refresh_interval_seconds'])
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error during scan: {e}")
                    time.sleep(self.config['refresh_interval_seconds'])
                    
        except KeyboardInterrupt:
            logger.info("\nScanner stopped by user")
        finally:
            self.is_running = False
    
    def stop(self):
        """Stop the scanner"""
        self.is_running = False
        logger.info("Scanner stopping...")
    
    def get_filtered_options(self):
        """
        Get filtered options without display (for programmatic use)
        
        Returns:
            Dictionary with ce_options, pe_options, nifty_spot, and metadata
        """
        ce_options, pe_options, nifty_spot = self.scan_once()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'nifty_spot': nifty_spot,
            'config': self.config,
            'ce_options': ce_options,
            'pe_options': pe_options,
            'ce_count': len(ce_options),
            'pe_count': len(pe_options)
        }


def prompt_for_expiry():
    """
    Prompt user for expiry date input
    
    Returns:
        Expiry date string entered by user
    """
    print("\n" + "=" * 80)
    print("NIFTY OPTIONS SCANNER - Configuration")
    print("=" * 80)
    print("\nEnter expiry date in any of these formats:")
    print("  - 'Jan 20' or '20 Jan'")
    print("  - 'Jan 20 2026' or '20 Jan 2026'")
    print("  - '2026-01-20' (ISO format)")
    print("  - Press Enter for nearest weekly expiry")
    print("-" * 80)
    
    expiry_input = input("\nEnter Expiry Date (e.g., Jan 20): ").strip()
    
    return expiry_input if expiry_input else None


def show_available_expiries():
    """
    Show available expiry dates from Kite
    """
    try:
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not api_key or not access_token:
            print("Cannot fetch expiries - API credentials not set")
            return
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        expiries = get_available_expiries(kite, "NIFTY")
        
        print("\nAvailable NIFTY Expiry Dates:")
        print("-" * 40)
        for i, exp in enumerate(expiries[:8], 1):
            print(f"  {i}. {exp.strftime('%d-%b-%Y')} ({exp.strftime('%A')})")
        
        if len(expiries) > 8:
            print(f"  ... and {len(expiries) - 8} more")
        print()
        
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")


def get_nearest_weekly_expiry(kite):
    """
    Get nearest weekly expiry date
    
    Args:
        kite: KiteConnect instance
    
    Returns:
        Nearest expiry date or None
    """
    expiries = get_available_expiries(kite, "NIFTY")
    if expiries:
        return expiries[0]
    return None


def main():
    """Main entry point with user input for expiry date"""
    
    # Show header
    print("\n" + "=" * 80)
    print("  NIFTY OPTIONS SCANNER")
    print("  Scan for CE/PE options with premium between ₹80-₹120")
    print("=" * 80)
    
    # Try to show available expiries
    show_available_expiries()
    
    # Get expiry date from user
    expiry_input = prompt_for_expiry()
    
    # Parse expiry date
    if expiry_input:
        try:
            expiry_date = parse_expiry_date(expiry_input)
            print(f"\n✓ Using expiry: {expiry_date.strftime('%d-%b-%Y')}")
        except ValueError as e:
            print(f"\n✗ Error: {e}")
            print("Using nearest weekly expiry instead...")
            expiry_date = None
    else:
        expiry_date = None
        print("\n✓ Using nearest weekly expiry")
    
    # Configuration
    config = {
        "strike_min": 24000,
        "strike_max": 26000,
        "strike_multiple": 100,  # Only strikes in multiples of 100 (25000, 25100, 25200, etc.)
        "premium_min": 80,
        "premium_max": 120,
        "refresh_interval_seconds": 5,
        "expiry_date": expiry_date  # User-specified expiry date
    }
    
    # Create scanner
    scanner = NiftyOptionsScanner(config=config)
    
    # If no expiry specified, get nearest weekly
    if scanner.expiry_date is None:
        nearest = get_nearest_weekly_expiry(scanner.kite)
        if nearest:
            scanner.expiry_date = nearest
            print(f"✓ Auto-selected nearest expiry: {nearest.strftime('%d-%b-%Y')}")
    
    # Run continuously
    print("\n" + "=" * 80)
    print("Scanner Configuration:")
    print(f"  Expiry: {scanner.expiry_date.strftime('%d-%b-%Y') if scanner.expiry_date else 'All'}")
    print(f"  Strike Range: {config['strike_min']} - {config['strike_max']} (multiples of {config['strike_multiple']})")
    print(f"  Premium Range: ₹{config['premium_min']} - ₹{config['premium_max']}")
    print(f"  Refresh Interval: {config['refresh_interval_seconds']} seconds")
    print("=" * 80)
    print("\nPress Ctrl+C to stop\n")
    
    scanner.run()


def run_with_expiry(expiry_date_str, strike_min=25000, strike_max=26000, 
                    strike_multiple=100, premium_min=80, premium_max=120, 
                    refresh_seconds=5):
    """
    Convenience function to run scanner with specific expiry
    
    Args:
        expiry_date_str: Expiry date string (e.g., "Jan 20", "20 Jan 2026")
        strike_min: Minimum strike price (default: 25000)
        strike_max: Maximum strike price (default: 26000)
        strike_multiple: Only include strikes in multiples of this value (default: 100)
        premium_min: Minimum premium (default: 80)
        premium_max: Maximum premium (default: 120)
        refresh_seconds: Refresh interval in seconds (default: 5)
    
    Example:
        run_with_expiry("Jan 20")
        run_with_expiry("23 Jan 2026", strike_min=24000, strike_max=25000)
        run_with_expiry("Jan 20", strike_multiple=50)  # Include all strikes (50 multiples)
    """
    config = {
        "strike_min": strike_min,
        "strike_max": strike_max,
        "strike_multiple": strike_multiple,
        "premium_min": premium_min,
        "premium_max": premium_max,
        "refresh_interval_seconds": refresh_seconds,
        "expiry_date": expiry_date_str
    }
    
    scanner = NiftyOptionsScanner(config=config)
    scanner.run()


if __name__ == "__main__":
    main()
