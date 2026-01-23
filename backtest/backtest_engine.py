"""
Backtesting Module for NIFTY CE Auto Trader
Tests trading logic using historical data

Usage:
    python backtest_nifty_ce_trader.py
    
    # Or programmatically:
    from backtest_nifty_ce_trader import BacktestNiftyCETrader
    
    backtester = BacktestNiftyCETrader(
        test_date="2026-01-16",
        expiry_date="2026-01-23",
        strike=25100,
        initial_balance=100000
    )
    
    results = backtester.run()
    backtester.display_results()
"""

import os
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np
import logging
import pytz
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

# Import local modules (now these will work)
from indicators.technical_indicators import calculate_all_indicators

# Parse expiry date function (copied here to keep all logic in this file)
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

# Setup logging (console + file)
from utils.logging_config import setup_logging
setup_logging(level=logging.INFO, log_prefix="backtest")
logger = logging.getLogger(__name__)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


class BacktestNiftyCETrader:
    """
    Backtesting engine for NIFTY CE Auto Trader
    
    Simulates trading using historical data for a specific date
    Tests the same logic as IntegratedNiftyCETrader but with historical prices
    """
    
    def __init__(self, kite_client=None, test_date=None, expiry_date=None, 
                 strike=25100, initial_balance=100000):
        """
        Initialize backtester
        
        Args:
            kite_client: KiteConnect instance (optional)
            test_date: Test date string (e.g., "2026-01-16")
            expiry_date: Expiry date string (e.g., "2026-01-23")
            strike: Strike price to test (default: 25100)
            initial_balance: Starting balance for simulation (default: 100000)
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
        
        # Parse dates
        if test_date:
            if isinstance(test_date, str):
                self.test_date = datetime.strptime(test_date, "%Y-%m-%d").date()
            else:
                self.test_date = test_date
        else:
            raise ValueError("test_date is required")
        
        if expiry_date:
            self.expiry_date = parse_expiry_date(expiry_date)
        else:
            raise ValueError("expiry_date is required")
        
        self.strike = strike
        self.initial_balance = initial_balance
        
        # Configuration (same as IntegratedNiftyCETrader)
        self.config = {
            "risk_factor": 0.90,
            "lot_size": 65,
            "primary_timeframe": "5minute",
            "confirm_timeframe": "2minute",
            "nifty_instrument_token": 256265,
        }
        
        # State variables
        self.current_balance = initial_balance
        self.trading_capital = initial_balance * self.config['risk_factor']
        
        # Historical data storage (CE option price data for signals)
        self.ce_option_data_5min = None  # CE option 5-min data for signals
        self.ce_option_data_2min = None  # CE option 2-min data for signals
        
        # Trading simulation
        self.trades = []
        self.current_position = None
        self.current_time_index = 0
        
        # Instrument tokens (will be fetched)
        self.ce_instrument_token = None
        self.pe_instrument_token = None
    
    def validate_test_date(self):
        """Validate that test date is valid for backtesting"""
        today = datetime.now(IST).date()
        
        # Check if date is in future
        if self.test_date > today:
            raise ValueError(f"Test date {self.test_date} is in the future")
        
        # Check if date is weekend (Saturday=5, Sunday=6)
        weekday = self.test_date.weekday()
        if weekday >= 5:
            raise ValueError(f"Test date {self.test_date} is a weekend (no market data)")
        
        # Check if expiry date is valid
        expiry_date_only = self.expiry_date.date() if isinstance(self.expiry_date, datetime) else self.expiry_date
        if expiry_date_only < self.test_date:
            raise ValueError(f"Expiry date {expiry_date_only} is before test date {self.test_date}")
        
        logger.info(f"✓ Date validation passed: Test date {self.test_date} is valid")
    
    def get_instrument_tokens(self):
        """Get instrument tokens for CE option"""
        try:
            logger.info(f"Searching for instrument: Strike {self.strike}, Expiry {self.expiry_date}")
            
            instruments = self.kite.instruments("NFO")
            df = pd.DataFrame(instruments)
            
            # Find CE option - filter by name, type, and strike first
            ce_match = df[
                (df['name'] == 'NIFTY') &
                (df['instrument_type'] == 'CE') &
                (df['strike'] == self.strike)
            ]
            
            if ce_match.empty:
                # Log available strikes for debugging
                available_strikes = df[
                    (df['name'] == 'NIFTY') & 
                    (df['instrument_type'] == 'CE')
                ]['strike'].unique()
                logger.error(f"No CE options found for strike {self.strike}")
                logger.error(f"Available strikes: {sorted(available_strikes)[:20]}")
                raise ValueError(f"CE option not found for strike {self.strike}")
            
            # Match expiry date - handle different date formats
            expiry_date_only = self.expiry_date.date() if isinstance(self.expiry_date, datetime) else self.expiry_date
            
            # Try exact match first
            if 'expiry' in ce_match.columns:
                # Convert expiry column to date if it's datetime
                if pd.api.types.is_datetime64_any_dtype(ce_match['expiry']):
                    ce_match_filtered = ce_match[ce_match['expiry'].dt.date == expiry_date_only]
                else:
                    ce_match_filtered = ce_match[ce_match['expiry'] == expiry_date_only]
                
                if not ce_match_filtered.empty:
                    ce_match = ce_match_filtered
                else:
                    # Try to find closest expiry
                    logger.warning(f"Exact expiry match not found for {expiry_date_only}, trying closest match...")
                    if pd.api.types.is_datetime64_any_dtype(ce_match['expiry']):
                        # Find closest expiry date
                        expiry_diffs = abs((ce_match['expiry'].dt.date - expiry_date_only).apply(lambda x: x.days))
                        closest_idx = expiry_diffs.idxmin()
                        ce_match = ce_match.loc[[closest_idx]]
                        logger.info(f"Using closest expiry: {ce_match.iloc[0]['expiry']}")
            
            if not ce_match.empty:
                self.ce_instrument_token = ce_match.iloc[0]['instrument_token']
                symbol = ce_match.iloc[0]['tradingsymbol']
                expiry_found = ce_match.iloc[0]['expiry']
                logger.info(f"✓ Found CE option: {symbol} (Token: {self.ce_instrument_token}, Expiry: {expiry_found})")
            else:
                raise ValueError(f"CE option not found: NIFTY {self.strike}CE expiring {expiry_date_only}")
                
        except Exception as e:
            logger.error(f"Error fetching instrument tokens: {e}")
            # Debug: show available options
            try:
                instruments = self.kite.instruments("NFO")
                df = pd.DataFrame(instruments)
                nifty_ce = df[(df['name'] == 'NIFTY') & (df['instrument_type'] == 'CE')]
                if not nifty_ce.empty:
                    logger.error(f"Available NIFTY CE expiries: {sorted(nifty_ce['expiry'].unique())[:10]}")
            except:
                pass
            raise
    
    def load_historical_data(self):
        """Load historical data for test date"""
        logger.info(f"Loading historical data for {self.test_date}")
        
        # Validate dates first
        self.validate_test_date()
        
        # Date range for test day - WITH IST TIMEZONE
        from_date = IST.localize(
            datetime.combine(self.test_date, datetime.min.time()).replace(hour=9, minute=15)
        )
        to_date = IST.localize(
            datetime.combine(self.test_date, datetime.min.time()).replace(hour=15, minute=30)
        )
        
        logger.info(f"Fetching data from {from_date} to {to_date} (IST)")
        
        try:
            # Get instrument tokens first
            self.get_instrument_tokens()
            
            if not self.ce_instrument_token:
                raise ValueError("CE instrument token not found")
            
            # Load CE option data for signal calculation (5-min and 2-min)
            # Using CE option price data for indicators instead of NIFTY index
            logger.info("Loading CE option price data for signal calculation...")
            self.ce_option_data_5min = self._fetch_historical(
                self.ce_instrument_token,
                from_date, to_date, "5minute"
            )
            self.ce_option_data_2min = self._fetch_historical(
                self.ce_instrument_token,
                from_date, to_date, "2minute"
            )
            
            logger.info("Using CE option price data for indicator calculation (not NIFTY index)")
            
            # Validate data loaded
            if self.ce_option_data_2min.empty:
                raise ValueError("No CE option 2-min data loaded - check if instrument token is correct")
            if self.ce_option_data_5min.empty:
                raise ValueError("No CE option 5-min data loaded - check if instrument token is correct")
            
            logger.info(f"✓ Loaded {len(self.ce_option_data_2min)} CE option 2-min candles")
            logger.info(f"✓ Loaded {len(self.ce_option_data_5min)} CE option 5-min candles")
            
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            logger.error(f"  Test Date: {self.test_date}")
            logger.error(f"  Expiry Date: {self.expiry_date}")
            logger.error(f"  Strike: {self.strike}")
            raise
    
    def _fetch_historical(self, instrument_token, from_date, to_date, interval):
        """Fetch historical data for an instrument"""
        try:
            logger.debug(f"Fetching {interval} data for token {instrument_token}")
            logger.debug(f"  From: {from_date} (IST)")
            logger.debug(f"  To: {to_date} (IST)")
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            if not data:
                logger.warning(f"No data returned for token {instrument_token}, interval {interval}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                df['date'] = pd.to_datetime(df['date'])
                # Ensure timezone-aware if not already
                if df['date'].dt.tz is None:
                    df['date'] = df['date'].dt.tz_localize(IST)
                logger.info(f"✓ Fetched {len(df)} candles for {interval}")
            else:
                logger.warning(f"Empty DataFrame returned for token {instrument_token}")
            
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data for token {instrument_token}: {e}")
            logger.error(f"  Interval: {interval}")
            logger.error(f"  From: {from_date}")
            logger.error(f"  To: {to_date}")
            # Re-raise to see the actual error
            raise
    
    def check_buy_conditions(self, df, timeframe="5minute"):
        """Check buy conditions (same logic as IntegratedNiftyCETrader)"""
        if len(df) < 20:
            return False, {}
        
        # Calculate indicators
        df = calculate_all_indicators(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        conditions = {}
        
        # SuperTrend Bullish
        conditions['supertrend_bullish'] = current['supertrend_direction'] == 1
        conditions['close_above_st'] = current['close'] > current['supertrend']
        conditions['close_above_ema_low'] = current['close'] > current['ema_low_8']
        conditions['ema_bullish'] = current['ema_8'] > current['ema_9']
        
        # StochRSI
        stoch_rising = current['stoch_rsi_k'] > prev['stoch_rsi_k']
        conditions['stoch_ok'] = current['stoch_rsi_k'] < 50 or stoch_rising
        
        # RSI
        rsi_rising = current['rsi_14'] > prev['rsi_14']
        conditions['rsi_ok'] = current['rsi_14'] < 65 and rsi_rising
        
        # MACD
        macd_improving = current['macd_hist'] > prev['macd_hist']
        conditions['macd_ok'] = current['macd_hist'] > 0 or macd_improving
        
        # Add indicator values for detailed logging
        conditions['values'] = {
            'close': current['close'],
            'supertrend': current['supertrend'],
            'supertrend_dir': 'BULLISH' if current['supertrend_direction'] == 1 else 'BEARISH',
            'ema_low': current['ema_low_8'],
            'ema_8': current['ema_8'],
            'ema_9': current['ema_9'],
            'stoch_rsi': current['stoch_rsi_k'],
            'stoch_rsi_prev': prev['stoch_rsi_k'],
            'stoch_rsi_rising': stoch_rising,
            'rsi': current['rsi_14'],
            'rsi_prev': prev['rsi_14'],
            'rsi_rising': rsi_rising,
            'macd_hist': current['macd_hist'],
            'macd_hist_prev': prev['macd_hist'],
            'macd_improving': macd_improving
        }
        
        all_conditions_met = all(conditions.values())
        
        return all_conditions_met, conditions
    
    def format_condition_status(self, conditions, timeframe=""):
        """Format condition status for logging"""
        if not conditions or 'values' not in conditions:
            return ""
        
        vals = conditions.get('values', {})
        status_lines = []
        
        # SuperTrend
        st_status = "✓" if conditions.get('supertrend_bullish') else "✗"
        status_lines.append(f"  SuperTrend: {st_status} ({vals.get('supertrend_dir', 'N/A')}) | "
                          f"Close: ₹{vals.get('close', 0):.2f} vs ST: ₹{vals.get('supertrend', 0):.2f}")
        
        # Close > ST
        st_above = "✓" if conditions.get('close_above_st') else "✗"
        status_lines.append(f"  Close > ST: {st_above}")
        
        # Close > EMA Low
        ema_low_status = "✓" if conditions.get('close_above_ema_low') else "✗"
        status_lines.append(f"  Close > EMA Low: {ema_low_status} | "
                          f"Close: ₹{vals.get('close', 0):.2f} vs EMA Low: ₹{vals.get('ema_low', 0):.2f}")
        
        # EMA Cross
        ema_status = "✓" if conditions.get('ema_bullish') else "✗"
        status_lines.append(f"  EMA Cross: {ema_status} | EMA8: ₹{vals.get('ema_8', 0):.2f} vs EMA9: ₹{vals.get('ema_9', 0):.2f}")
        
        # StochRSI
        stoch_status = "✓" if conditions.get('stoch_ok') else "✗"
        stoch_rising_str = "↑" if vals.get('stoch_rsi_rising') else "↓"
        status_lines.append(f"  StochRSI: {stoch_status} | Value: {vals.get('stoch_rsi', 0):.1f} {stoch_rising_str} "
                          f"(<50 or rising)")
        
        # RSI
        rsi_status = "✓" if conditions.get('rsi_ok') else "✗"
        rsi_rising_str = "↑" if vals.get('rsi_rising') else "↓"
        status_lines.append(f"  RSI: {rsi_status} | Value: {vals.get('rsi', 0):.1f} {rsi_rising_str} "
                          f"(<65 and rising)")
        
        # MACD
        macd_status = "✓" if conditions.get('macd_ok') else "✗"
        macd_improving_str = "↑" if vals.get('macd_improving') else "↓"
        status_lines.append(f"  MACD Hist: {macd_status} | Value: {vals.get('macd_hist', 0):+.2f} {macd_improving_str} "
                          f"(>0 or improving)")
        
        return "\n".join(status_lines)
    
    def check_exit_conditions(self, df_2min):
        """Check exit conditions (same logic as IntegratedNiftyCETrader)"""
        if len(df_2min) < 5:
            return False, None, {}
        
        df_2min = calculate_all_indicators(df_2min)
        
        current = df_2min.iloc[-1]
        prev = df_2min.iloc[-2]
        prev2 = df_2min.iloc[-3]
        
        # Exit Trigger 1: EMA Low Falling
        ema_low_falling = (
            current['ema_low_8'] < prev['ema_low_8'] and
            prev['ema_low_8'] < prev2['ema_low_8']
        )
        price_below_ema = current['close'] < current['ema_low_8']
        
        exit_trigger_1 = ema_low_falling and price_below_ema
        
        # Exit Trigger 2: Strong Bearish
        strong_bearish = (
            current['supertrend_direction'] == -1 and
            current['ema_8'] < current['ema_9'] and
            current['close'] < current['ema_low_8']
        )
        
        if exit_trigger_1:
            return True, "ema_low_falling", {}
        elif strong_bearish:
            return True, "strong_bearish", {}
        
        return False, None, {}
    
    def simulate_buy(self, timestamp, ce_price):
        """Simulate BUY order execution - Uses fixed 1 lot for backtesting"""
        if self.current_position:
            return False  # Already in position
        
        # Use fixed 1 lot for backtesting (consistent position sizing)
        quantity = 1 * self.config['lot_size']  # 1 lot = 65 units
        
        if quantity <= 0:
            return False
        
        # Calculate cost
        cost = ce_price * quantity
        
        # Check balance (for backtesting, we allow negative balance but log warning)
        if self.current_balance < cost:
            logger.warning(f"Insufficient balance: ₹{self.current_balance:,.2f} < Required: ₹{cost:,.2f}")
            logger.warning("Continuing with negative balance for backtesting purposes")
        
        # Execute buy
        self.current_balance -= cost
        
        self.current_position = {
            'entry_time': timestamp,
            'entry_price': ce_price,
            'quantity': quantity,
            'symbol': f"NIFTY{self.expiry_date.strftime('%y%b%d').upper()}{self.strike}CE"
        }
        
        logger.info(f"BUY @ {timestamp}: 1 Lot ({quantity} units) @ ₹{ce_price:.2f} | Cost: ₹{cost:,.2f} | Balance: ₹{self.current_balance:,.2f}")
        return True
    
    def simulate_sell(self, timestamp, ce_price, reason):
        """Simulate SELL order execution"""
        if not self.current_position:
            return False
        
        # Execute sell
        proceeds = ce_price * self.current_position['quantity']
        self.current_balance += proceeds
        
        # Calculate P&L
        pnl = (ce_price - self.current_position['entry_price']) * self.current_position['quantity']
        pnl_pct = ((ce_price - self.current_position['entry_price']) / self.current_position['entry_price']) * 100
        
        # Record trade
        trade = {
            'trade_number': len(self.trades) + 1,
            'entry_time': self.current_position['entry_time'],
            'exit_time': timestamp,
            'entry_price': self.current_position['entry_price'],
            'exit_price': ce_price,
            'quantity': self.current_position['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason
        }
        
        self.trades.append(trade)
        
        logger.info(f"SELL @ {timestamp}: {self.current_position['quantity']} @ ₹{ce_price:.2f} | "
                   f"P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%) | Reason: {reason}")
        
        self.current_position = None
        return True
    
    def run(self):
        """Run backtest simulation"""
        logger.info("=" * 80)
        logger.info("STARTING BACKTEST")
        logger.info("=" * 80)
        logger.info(f"Test Date: {self.test_date}")
        logger.info(f"Expiry Date: {self.expiry_date}")
        logger.info(f"Strike: {self.strike}")
        logger.info(f"Position Size: 1 Lot ({self.config['lot_size']} units) - FIXED")
        logger.info(f"Initial Balance: ₹{self.initial_balance:,.2f} (for P&L calculation only)")
        
        # Load historical data
        self.load_historical_data()
        
        if self.ce_option_data_2min.empty or self.ce_option_data_5min.empty:
            logger.error("Insufficient CE option historical data")
            return None
        
        # Align data by timestamp
        ce_df = self.ce_option_data_2min.copy()
        
        # Simulate minute-by-minute
        logger.info("\nSimulating trading...")
        logger.info(f"Total candles to process: {len(ce_df)}")
        logger.info(f"Starting from index 20 (need enough data for indicators)")
        logger.info(f"Trading hours: 9:30 AM - 3:15 PM IST")
        
        last_5min_check_idx = -1
        processed_count = 0
        skipped_before_930 = 0
        skipped_after_315 = 0
        skipped_no_data = 0
        signal_checks = 0
        primary_signals = 0
        confirm_signals = 0
        
        # Track condition failures for analysis
        condition_failures = {
            'supertrend_bullish': 0,
            'close_above_st': 0,
            'close_above_ema_low': 0,
            'ema_bullish': 0,
            'stoch_ok': 0,
            'rsi_ok': 0,
            'macd_ok': 0
        }
        condition_checks_count = 0
        last_periodic_log_idx = -1
        
        for idx in range(20, len(ce_df)):  # Start from index 20 to have enough data for indicators
            current_time = ce_df.iloc[idx]['date']
            ce_price = ce_df.iloc[idx]['close']
            
            # Skip before 9:30 AM (watch-only period)
            # Handle timezone-aware datetime
            if isinstance(current_time, pd.Timestamp):
                hour = current_time.hour
                minute = current_time.minute
            else:
                hour = current_time.hour
                minute = current_time.minute
                
            if hour == 9 and minute < 30:
                skipped_before_930 += 1
                continue
            
            # Skip after 3:15 PM (stop new trades)
            if hour == 15 and minute >= 15:
                if self.current_position:
                    # Force exit
                    logger.info(f"Market close time reached - closing position")
                    self.simulate_sell(current_time, ce_price, "market_close")
                skipped_after_315 = len(ce_df) - idx
                logger.info(f"Stopped at 3:15 PM - Processed {processed_count} candles, {idx} total iterations")
                break
            
            # Get CE option data for current time (for signal calculation)
            ce_data_2min = self.ce_option_data_2min[self.ce_option_data_2min['date'] <= current_time].tail(20)
            ce_data_5min = self.ce_option_data_5min[self.ce_option_data_5min['date'] <= current_time].tail(20)
            
            if ce_data_2min.empty or ce_data_5min.empty:
                skipped_no_data += 1
                continue
            
            processed_count += 1
            
            if self.current_position:
                # Check exit conditions using CE option data
                should_exit, exit_reason, _ = self.check_exit_conditions(ce_data_2min)
                if should_exit:
                    self.simulate_sell(current_time, ce_price, exit_reason)
            else:
                # Check entry conditions using CE option price data
                signal_checks += 1
                
                # Check 2-min confirmation using CE option data
                confirm_signal, confirm_details = self.check_buy_conditions(ce_data_2min, "2minute")
                if confirm_signal:
                    confirm_signals += 1
                
                # Check 5-min primary (every 5 minutes) using CE option data
                if idx - last_5min_check_idx >= 2:  # Approx 5 minutes (2-min candles)
                    primary_signal, primary_details = self.check_buy_conditions(ce_data_5min, "5minute")
                    last_5min_check_idx = idx
                    if primary_signal:
                        primary_signals += 1
                        logger.info(f"✓ PRIMARY SIGNAL TRUE @ {current_time.strftime('%H:%M:%S')} (5-min)")
                        logger.info(f"5-MIN Conditions:\n{self.format_condition_status(primary_details, '5min')}")
                    else:
                        # Track which conditions failed (only track 5-min for analysis)
                        if primary_details:
                            condition_checks_count += 1
                            for cond_name in condition_failures.keys():
                                if not primary_details.get(cond_name, True):
                                    condition_failures[cond_name] += 1
                else:
                    primary_signal = False
                    primary_details = {}
                
                # Periodic condition summary (every 20 candles ~40 minutes)
                if idx - last_periodic_log_idx >= 20:
                    time_str = current_time.strftime('%H:%M:%S')
                    logger.info(f"\n--- Condition Status @ {time_str} ---")
                    logger.info(f"5-MIN ({'SIGNAL' if primary_signal else 'NO SIGNAL'}):")
                    if primary_details:
                        logger.info(self.format_condition_status(primary_details, '5min'))
                    logger.info(f"2-MIN ({'SIGNAL' if confirm_signal else 'NO SIGNAL'}):")
                    if confirm_details:
                        logger.info(self.format_condition_status(confirm_details, '2min'))
                    logger.info("---")
                    last_periodic_log_idx = idx
                
                # Double confirmation
                if primary_signal and confirm_signal:
                    logger.info(f"✓ DOUBLE CONFIRMATION @ {current_time.strftime('%H:%M:%S')} - Executing BUY")
                    self.simulate_buy(current_time, ce_price)
                elif primary_signal and not confirm_signal:
                    logger.info(f"⚠ Primary signal TRUE but confirmation FALSE @ {current_time.strftime('%H:%M:%S')}")
                    logger.info(f"2-MIN Failed Conditions:\n{self.format_condition_status(confirm_details, '2min')}")
                elif not primary_signal and confirm_signal:
                    logger.info(f"⚠ Confirmation TRUE but primary signal FALSE @ {current_time.strftime('%H:%M:%S')}")
                    logger.info(f"5-MIN Failed Conditions:\n{self.format_condition_status(primary_details, '5min')}")
        
        # Log summary
        logger.info(f"\nSimulation Summary:")
        logger.info(f"  Total candles processed: {processed_count}")
        logger.info(f"  Skipped before 9:30 AM: {skipped_before_930}")
        logger.info(f"  Skipped after 3:15 PM: {skipped_after_315}")
        logger.info(f"  Skipped (no data): {skipped_no_data}")
        logger.info(f"  Signal checks performed: {signal_checks}")
        logger.info(f"  Primary signals (5-min): {primary_signals}")
        logger.info(f"  Confirmation signals (2-min): {confirm_signals}")
        logger.info(f"  Total trades executed: {len(self.trades)}")
        
        # Final condition analysis
        if condition_checks_count > 0 and len(self.trades) == 0:
            logger.info(f"\n{'='*80}")
            logger.info("CONDITION FAILURE ANALYSIS")
            logger.info(f"{'='*80}")
            logger.info(f"Total condition checks: {condition_checks_count}")
            logger.info(f"\nMost Common Failing Conditions:")
            
            # Sort by failure count
            sorted_failures = sorted(condition_failures.items(), key=lambda x: x[1], reverse=True)
            
            for cond_name, fail_count in sorted_failures:
                fail_percentage = (fail_count / condition_checks_count * 100) if condition_checks_count > 0 else 0
                cond_display = {
                    'supertrend_bullish': 'SuperTrend Bullish',
                    'close_above_st': 'Close > SuperTrend',
                    'close_above_ema_low': 'Close > EMA Low',
                    'ema_bullish': 'EMA 8 > EMA 9',
                    'stoch_ok': 'StochRSI OK',
                    'rsi_ok': 'RSI OK',
                    'macd_ok': 'MACD OK'
                }.get(cond_name, cond_name)
                
                logger.info(f"  {cond_display}: Failed {fail_count}/{condition_checks_count} times ({fail_percentage:.1f}%)")
            
            logger.info(f"\n{'='*80}")
            logger.info("REASON FOR NO TRADES:")
            logger.info(f"{'='*80}")
            
            if sorted_failures[0][1] == condition_checks_count:
                logger.info(f"  All checks failed on: {sorted_failures[0][0]}")
                logger.info(f"  This condition needs to pass for any trade to execute.")
            else:
                top_failures = [f for f in sorted_failures if f[1] > condition_checks_count * 0.5]
                if top_failures:
                    logger.info(f"  Primary blockers:")
                    for cond_name, fail_count in top_failures[:3]:
                        cond_display = {
                            'supertrend_bullish': 'SuperTrend Bullish',
                            'close_above_st': 'Close > SuperTrend',
                            'close_above_ema_low': 'Close > EMA Low',
                            'ema_bullish': 'EMA 8 > EMA 9',
                            'stoch_ok': 'StochRSI OK',
                            'rsi_ok': 'RSI OK',
                            'macd_ok': 'MACD OK'
                        }.get(cond_name, cond_name)
                        logger.info(f"    - {cond_display} (failed {fail_count}/{condition_checks_count} times)")
            
            logger.info(f"\n  All 7 conditions must pass simultaneously for a BUY signal.")
            logger.info(f"  Strategy is working as designed - selective entry prevents bad trades.")
            logger.info(f"{'='*80}")
        
        # Force exit if position still open
        if self.current_position:
            last_price = ce_df.iloc[-1]['close']
            last_time = ce_df.iloc[-1]['date']
            self.simulate_sell(last_time, last_price, "market_close")
        
        logger.info("\n" + "=" * 80)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 80)
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Calculate comprehensive backtest metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_trade_duration_minutes': 0,
                'final_balance': self.current_balance,
                'initial_balance': self.initial_balance,
                'trades': []
            }
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]
        
        win_rate = (len(winning_trades) / len(self.trades) * 100) if self.trades else 0
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Calculate drawdown
        balance_curve = [self.initial_balance]
        for trade in self.trades:
            balance_curve.append(balance_curve[-1] + trade['pnl'])
        
        peak = balance_curve[0]
        max_drawdown = 0
        for balance in balance_curve:
            if balance > peak:
                peak = balance
            drawdown = ((peak - balance) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Sharpe ratio (simplified)
        returns = [t['pnl_pct'] for t in self.trades]
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Average trade duration
        durations = [(t['exit_time'] - t['entry_time']).total_seconds() / 60 for t in self.trades]
        avg_duration = np.mean(durations) if durations else 0
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / self.initial_balance) * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_trade_duration_minutes': avg_duration,
            'final_balance': self.current_balance,
            'initial_balance': self.initial_balance,
            'trades': self.trades
        }
    
    def display_results(self):
        """Display comprehensive backtest results"""
        metrics = self._calculate_metrics()
        
        print("\n" + "═" * 100)
        print(f"  BACKTEST RESULTS - {self.test_date} | Strike: {self.strike} CE")
        print("═" * 100)
        
        print(f"\n  PERFORMANCE METRICS")
        print("  " + "─" * 98)
        print(f"  Initial Balance: ₹{metrics['initial_balance']:,.2f}")
        print(f"  Final Balance: ₹{metrics['final_balance']:,.2f}")
        print(f"  Total P&L: ₹{metrics['total_pnl']:+,.2f} ({metrics['total_pnl_pct']:+.2f}%)")
        
        print(f"\n  TRADE STATISTICS")
        print("  " + "─" * 98)
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Winning Trades: {metrics['winning_trades']}")
        print(f"  Losing Trades: {metrics['losing_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.2f}%")
        print(f"  Average Win: ₹{metrics['avg_win']:+,.2f}")
        print(f"  Average Loss: ₹{metrics['avg_loss']:+,.2f}")
        
        print(f"\n  RISK METRICS")
        print("  " + "─" * 98)
        print(f"  Maximum Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Average Trade Duration: {metrics['avg_trade_duration_minutes']:.1f} minutes")
        
        if metrics['trades']:
            print(f"\n  TRADE-BY-TRADE ANALYSIS")
            print("  " + "─" * 98)
            print(f"{'#':<4} {'Entry Time':<20} {'Exit Time':<20} {'Entry':<10} {'Exit':<10} {'P&L':<12} {'P&L%':<8} {'Reason':<15}")
            print("  " + "-" * 98)
            
            for trade in metrics['trades']:
                entry_str = trade['entry_time'].strftime('%H:%M:%S')
                exit_str = trade['exit_time'].strftime('%H:%M:%S')
                pnl_str = f"₹{trade['pnl']:+,.2f}"
                pnl_pct_str = f"{trade['pnl_pct']:+.2f}%"
                
                print(f"  {trade['trade_number']:<4} {entry_str:<20} {exit_str:<20} "
                     f"₹{trade['entry_price']:<9.2f} ₹{trade['exit_price']:<9.2f} "
                     f"{pnl_str:<12} {pnl_pct_str:<8} {trade['exit_reason']:<15}")
        
        print("═" * 100)


def main():
    """Main entry point - Configured for 25300 CE Jan 27 Expiry, Today's Date, 1 Lot"""
    print("\n" + "═" * 100)
    print("  NIFTY CE AUTO TRADER - BACKTESTING MODULE")
    print("═" * 100)
    print("\n  NOTE: Backtesting uses FIXED 1 LOT (65 units) per trade")
    print("  Initial balance is only used for P&L calculation, not position sizing")
    print("═" * 100)
    
    try:
        # Fixed configuration: 25300 CE, Jan 27 Expiry, Today's Date, 1 Lot
        today = datetime.now(IST).date()
        test_date = today.strftime("%Y-%m-%d")
        expiry_date = "Jan 27"
        strike = 25300
        initial_balance = 100000
        
        print(f"\n✓ Backtest Configuration (AUTO):")
        print(f"  Test Date: {test_date} (Today)")
        print(f"  Expiry Date: {expiry_date}")
        print(f"  Strike: {strike} CE (ATM)")
        print(f"  Position Size: 1 Lot (65 units) - FIXED")
        print(f"  Initial Balance: ₹{initial_balance:,.2f} (for P&L calculation only)")
        
        # Create backtester
        backtester = BacktestNiftyCETrader(
            test_date=test_date,
            expiry_date=expiry_date,
            strike=strike,
            initial_balance=initial_balance
        )
        
        # Run backtest
        results = backtester.run()
        
        # Display results
        if results:
            backtester.display_results()
        
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
