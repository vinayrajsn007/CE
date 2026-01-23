"""
Integrated NIFTY CE Auto Trader
Based on ADR-004: Combines Options Scanner (ADR-003) + Double Confirmation Strategy (ADR-001)

Features:
- Takes expiry date as user input
- Scans NIFTY CE options in premium range ₹70-₹130
- Uses Double Confirmation (5-min + 2-min) for entry signals
- **All buy/exit validation based on CE Option price data (not NIFTY index)**
- **All indicators calculated from CE Option OHLC data**
- Automatic quantity calculation based on account balance (90% risk factor)
- Continuous trading loop until market close
- Tracks daily P&L across multiple trades

Usage:
    python integrated_nifty_ce_trader.py
    
    # Or programmatically:
    trader = IntegratedNiftyCETrader()
    trader.run(expiry_date="Jan 23")
"""

import os
import time
import math
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np
import logging
import pytz

# Load environment variables
load_dotenv()

# Debug logging helper
DEBUG_LOG_PATH = "/Users/vinayraj/Desktop/vinay/kite/CE/.cursor/debug.log"

def debug_log(location, message, data=None, hypothesis_id=None, run_id="run1"):
    """Write debug log entry"""
    try:
        # Ensure directory exists
        log_dir = os.path.dirname(DEBUG_LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        log_entry = {
            "id": f"log_{int(datetime.now().timestamp() * 1000)}",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": hypothesis_id
        }
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            f.flush()  # Ensure immediate write
    except Exception as e:
        # Log to stderr so we can see if logging fails
        import sys
        print(f"DEBUG LOG ERROR: {e}", file=sys.stderr)

# Import local modules
from indicators.technical_indicators import calculate_all_indicators
from scanner.options_scanner import parse_expiry_date, NiftyOptionsScanner

# Setup logging (console + file)
from utils.logging_config import setup_logging
setup_logging(level=logging.INFO, log_prefix="trading")
logger = logging.getLogger(__name__)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TRADER_CONFIG = {
    # Options Scanner (ADR-003)
    "strike_min": 24000,
    "strike_max": 26000,
    "strike_multiple": 100,
    "premium_min": 70,
    "premium_max": 130,
    "scanner_refresh_seconds": 5,
    
    # Quantity Calculation
    "risk_factor": 0.90,  # Use 90% of balance
    "lot_size": 65,       # NIFTY lot size
    
    # Market Hours (IST)
    "market_open_hour": 9,
    "market_open_minute": 15,
    "market_close_hour": 15,
    "market_close_minute": 30,
    "stop_new_trades_minutes": 15,  # Stop new trades 15 min before close
    
    # Double Confirmation (ADR-001)
    "primary_timeframe": "5minute",
    "confirm_timeframe": "2minute",
    "primary_check_seconds": 10,
    "confirm_check_seconds": 5,
    
    # Indicator Parameters
    "supertrend_period": 7,
    "supertrend_multiplier": 3,
    "ema_low_period": 8,
    "ema_low_offset": 9,
    "ema_fast": 8,
    "ema_slow": 9,
    "rsi_period": 14,
    "rsi_max": 65,
    "stoch_rsi_threshold": 50,
    "macd_fast": 5,
    "macd_slow": 13,
    "macd_signal": 6,
    
    # Trading
    "exchange": "NFO",
    "product_type": "MIS",  # Intraday
    "order_type": "MARKET",
    
    # NIFTY Index
    "nifty_instrument_token": 256265,  # NIFTY 50 index token
}


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATED NIFTY CE TRADER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class IntegratedNiftyCETrader:
    """
    Integrated NIFTY CE Auto Trader
    
    Combines:
    - ADR-003: Options Scanner for instrument selection
    - ADR-001: Double Confirmation Strategy for trade timing
    
    Features:
    - Automatic CE option selection based on premium range
    - Double confirmation (5-min + 2-min) for entry
    - **Buy/exit validation based on CE Option price data (not NIFTY index)**
    - **All indicators calculated from selected CE Option OHLC data**
    - Exit on EMA Low falling or strong bearish signal (validated on CE Option)
    - Continuous trading loop until market close
    - Daily P&L tracking
    
    Important:
    - Historical data fetched from selected CE Option's instrument_token
    - All buy conditions validated using CE Option close price
    - All exit conditions validated using CE Option close price
    - NIFTY index only used for reference (spot price display)
    """
    
    def __init__(self, kite_client=None, config=None):
        """
        Initialize the trader
        
        Args:
            kite_client: KiteConnect instance (optional)
            config: Configuration dictionary (optional)
        """
        # Merge configuration
        self.config = {**TRADER_CONFIG, **(config or {})}
        
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
        
        # State variables
        self.expiry_date = None
        self.available_balance = 0
        self.trading_capital = 0
        self.selected_option = None
        self.calculated_quantity = 0
        
        # Position tracking
        self.position_open = False
        self.entry_price = 0
        self.entry_time = None
        self.position_quantity = 0
        self.position_symbol = None
        
        # Trade tracking
        self.trade_cycle = 0
        self.daily_trades = []
        self.total_pnl = 0
        
        # Signal tracking
        self.last_5min_check = None
        self.primary_signal = False
        self.confirm_signal = False
        
        # Scanner instance
        self.scanner = None
        
        # Running state
        self.is_running = False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MARKET HOURS METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_current_time_ist(self):
        """Get current time in IST"""
        return datetime.now(IST)
    
    def is_market_open(self):
        """Check if market is currently open (9:15 AM - 3:30 PM IST)"""
        now = self.get_current_time_ist()
        
        market_open = now.replace(
            hour=self.config['market_open_hour'],
            minute=self.config['market_open_minute'],
            second=0,
            microsecond=0
        )
        market_close = now.replace(
            hour=self.config['market_close_hour'],
            minute=self.config['market_close_minute'],
            second=0,
            microsecond=0
        )
        
        return market_open <= now <= market_close
    
    def get_time_to_market_close(self):
        """Get minutes remaining until market close"""
        now = self.get_current_time_ist()
        market_close = now.replace(
            hour=self.config['market_close_hour'],
            minute=self.config['market_close_minute'],
            second=0,
            microsecond=0
        )
        
        if now > market_close:
            return 0
        
        delta = market_close - now
        return int(delta.total_seconds() / 60)
    
    def should_stop_new_trades(self):
        """Check if we should stop initiating new trades (< 15 min to close)"""
        minutes_to_close = self.get_time_to_market_close()
        return minutes_to_close < self.config['stop_new_trades_minutes']
    
    def is_watch_only_period(self):
        """Check if within watch-only period (9:25-9:30 AM) - monitor but don't trade"""
        now = self.get_current_time_ist()
        watch_start = now.replace(hour=9, minute=25, second=0, microsecond=0)
        trading_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        return watch_start <= now < trading_start
    
    def can_trade(self):
        """Check if trading is allowed (after 9:30 AM, before 3:15 PM)"""
        if not self.is_market_open():
            return False
        if self.is_watch_only_period():
            return False
        if self.should_stop_new_trades():
            return False
        return True
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACCOUNT BALANCE METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_account_balance(self):
        """Fetch current available balance from Kite"""
        try:
            margins = self.kite.margins(segment="equity")
            self.available_balance = margins['available']['live_balance']
            self.trading_capital = self.available_balance * self.config['risk_factor']
            
            logger.info(f"Account Balance: ₹{self.available_balance:,.2f}")
            logger.info(f"Trading Capital ({self.config['risk_factor']*100:.0f}%): ₹{self.trading_capital:,.2f}")
            
            return self.available_balance
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            raise
    
    def refresh_balance_before_buy(self):
        """Refresh balance immediately before placing a buy order"""
        logger.info("Refreshing balance before buy order...")
        return self.get_account_balance()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPTIONS SCANNER METHODS (ADR-003)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def initialize_scanner(self):
        """Initialize the options scanner with current configuration"""
        scanner_config = {
            "strike_min": self.config['strike_min'],
            "strike_max": self.config['strike_max'],
            "strike_multiple": self.config['strike_multiple'],
            "premium_min": self.config['premium_min'],
            "premium_max": self.config['premium_max'],
            "refresh_interval_seconds": self.config['scanner_refresh_seconds'],
            "expiry_date": self.expiry_date,
            "option_types": ["CE"]  # Only CE options
        }
        
        self.scanner = NiftyOptionsScanner(kite_client=self.kite, config=scanner_config)
        self.scanner.load_nifty_options()
        
        logger.info(f"Scanner initialized for expiry: {self.expiry_date}")
    
    def get_nifty_spot_price(self):
        """Get current NIFTY spot price"""
        try:
            quote = self.kite.quote(["NSE:NIFTY 50"])
            return quote.get("NSE:NIFTY 50", {}).get("last_price", 0)
        except Exception as e:
            logger.error(f"Error fetching NIFTY spot: {e}")
            return 0
    
    def select_best_ce_option(self):
        """
        Select the best CE option based on ADR-003 criteria:
        1. Premium in range ₹70-₹130
        2. Closest to ATM (priority: ATM > OTM > ITM)
        3. Premium closest to ₹100 (middle of range)
        
        Returns:
            Selected option dictionary or None
        """
        try:
            # Get filtered options from scanner
            result = self.scanner.get_filtered_options()
            ce_options = result.get('ce_options', [])
            nifty_spot = result.get('nifty_spot', 0)
            
            if not ce_options:
                logger.warning("No CE options found in premium range")
                return None
            
            # Calculate ATM strike
            atm_strike = round(nifty_spot / 100) * 100
            logger.info(f"NIFTY Spot: ₹{nifty_spot:,.2f} | ATM Strike: {atm_strike}")
            
            # Priority 1: Exact ATM strike (if premium in range)
            atm_options = [opt for opt in ce_options if opt['strike'] == atm_strike]
            if atm_options:
                # If multiple ATM strikes, prefer premium closest to ₹100
                selected = min(atm_options, key=lambda x: abs(x['ltp'] - 100))
                logger.info(f"Selected ATM strike: {selected['strike']} @ ₹{selected['ltp']:.2f}")
            else:
                # Priority 2: Nearest OTM
                otm_options = [opt for opt in ce_options if opt['strike'] > atm_strike]
                if otm_options:
                    selected = min(otm_options, key=lambda x: x['strike'] - atm_strike)
                    logger.info(f"Selected nearest OTM: {selected['strike']} @ ₹{selected['ltp']:.2f}")
                else:
                    # Priority 3: Nearest ITM
                    itm_options = [opt for opt in ce_options if opt['strike'] < atm_strike]
                    if itm_options:
                        selected = max(itm_options, key=lambda x: x['strike'])
                        logger.info(f"Selected nearest ITM: {selected['strike']} @ ₹{selected['ltp']:.2f}")
                    else:
                        logger.warning("No suitable CE options found")
                        return None
            self.selected_option = {
                'tradingsymbol': selected['symbol'],
                'instrument_token': selected['instrument_token'],
                'strike': selected['strike'],
                'expiry': selected['expiry'],
                'ltp': selected['ltp'],
                'lot_size': self.config['lot_size']
            }
            
            logger.info(f"Selected CE Option: {self.selected_option['tradingsymbol']} "
                       f"@ ₹{self.selected_option['ltp']:.2f}")
            
            return self.selected_option
            
        except Exception as e:
            logger.error(f"Error selecting CE option: {e}")
            return None
    
    def refresh_option_premium(self):
        """Refresh the current premium of selected option"""
        if not self.selected_option:
            return None
        
        try:
            symbol = f"{self.config['exchange']}:{self.selected_option['tradingsymbol']}"
            quote = self.kite.quote([symbol])
            
            if symbol in quote:
                self.selected_option['ltp'] = quote[symbol]['last_price']
                return self.selected_option['ltp']
        except Exception as e:
            logger.error(f"Error refreshing premium: {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUANTITY CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_quantity(self, option_premium=None):
        """
        Calculate trading quantity based on balance and option premium
        
        Formula:
        - Cost per lot = Premium × Lot Size
        - Max lots = floor(Trading Capital / Cost per lot)
        - Quantity = Max lots × Lot Size
        
        Args:
            option_premium: Option premium (uses selected_option if not provided)
        
        Returns:
            Quantity to trade
        """
        if option_premium is None:
            if self.selected_option:
                option_premium = self.selected_option['ltp']
            else:
                return 0
        
        lot_size = self.config['lot_size']
        cost_per_lot = option_premium * lot_size
        
        if cost_per_lot <= 0:
            return 0
        
        max_lots = math.floor(self.trading_capital / cost_per_lot)
        quantity = max_lots * lot_size
        
        self.calculated_quantity = quantity
        
        logger.info(f"Quantity Calculation:")
        logger.info(f"  Cost per Lot: ₹{option_premium:.2f} × {lot_size} = ₹{cost_per_lot:,.2f}")
        logger.info(f"  Max Lots: floor(₹{self.trading_capital:,.2f} / ₹{cost_per_lot:,.2f}) = {max_lots}")
        logger.info(f"  Quantity: {max_lots} × {lot_size} = {quantity}")
        
        return quantity
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOUBLE CONFIRMATION METHODS (ADR-001)
    # ═══════════════════════════════════════════════════════════════════════════
    # NOTE: Indicators are calculated from SELECTED CE OPTION data, not NIFTY index.
    # This ensures signals are based on the actual option being traded.
    
    def get_historical_data(self, interval, days=5, use_ce_option=True):
        """
        Fetch historical data for indicator calculation
        
        Uses selected CE option's data if available, otherwise falls back to NIFTY index.
        This ensures indicators are calculated based on the actual option being traded.
        
        Args:
            interval: Candle interval ('5minute', '2minute')
            days: Number of days to fetch
            use_ce_option: If True, use selected CE option's data; if False, use NIFTY index
        
        Returns:
            DataFrame with OHLC data
        """
        try:
            # Determine which instrument token to use
            if use_ce_option and self.selected_option and self.selected_option.get('instrument_token'):
                instrument_token = self.selected_option['instrument_token']
                instrument_name = f"CE Option ({self.selected_option.get('tradingsymbol', 'Unknown')})"
            else:
                instrument_token = self.config['nifty_instrument_token']
                instrument_name = "NIFTY Index"
            
            # Use IST timezone-aware datetime objects
            to_date = datetime.now(IST)
            from_date = to_date - timedelta(days=days)
            
            logger.debug(f"Fetching {interval} data for {instrument_name} from {from_date} to {to_date} (IST)")
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            if not data:
                logger.warning(f"No data returned for {interval} interval ({instrument_name})")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                df['date'] = pd.to_datetime(df['date'])
                # Ensure timezone-aware if not already
                if df['date'].dt.tz is None:
                    df['date'] = df['date'].dt.tz_localize(IST)
                logger.debug(f"Fetched {len(df)} candles for {interval} ({instrument_name})")
            else:
                logger.warning(f"Empty DataFrame returned for {interval} ({instrument_name})")
            
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data ({interval}): {e}")
            logger.error(f"  From: {from_date}, To: {to_date}")
            logger.error(f"  Instrument: {instrument_name if 'instrument_name' in locals() else 'Unknown'}")
            return pd.DataFrame()
    
    def check_buy_conditions(self, df, timeframe="5minute"):
        """
        Check all buy conditions for a timeframe (ADR-001)
        
        IMPORTANT: This validates buy signals based on CE OPTION price data, not NIFTY index.
        The DataFrame passed should contain CE option OHLC data from get_historical_data().
        
        Conditions (all must be true):
        1. SuperTrend (7,3) Direction = 1 (Bullish) - based on CE option price
        2. CE Option Close > SuperTrend Value
        3. CE Option Close > EMA Low (8, offset 9)
        4. EMA 8 > EMA 9 (Bullish Crossover) - calculated from CE option price
        5. StochRSI < 50 OR Rising - calculated from CE option price
        6. RSI < 65 AND Rising - calculated from CE option price
        7. MACD Histogram > 0 OR Improving - calculated from CE option price
        
        Args:
            df: DataFrame with CE option OHLC data (from get_historical_data)
            timeframe: Timeframe name for logging (e.g., "5minute", "2minute")
        
        Returns:
            Tuple of (signal_active, details_dict)
        """
        if len(df) < 20:
            return False, {"error": "Insufficient data"}
        
        # Validate that we have CE option selected (for logging clarity)
        ce_symbol = self.selected_option.get('tradingsymbol', 'Unknown') if self.selected_option else 'Not Selected'
        logger.debug(f"Validating buy conditions on {timeframe} using CE Option: {ce_symbol}")
        
        # Calculate indicators from CE option price data
        df = calculate_all_indicators(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) > 2 else prev
        
        conditions = {}
        
        # All conditions use CE option's close price (current['close'])
        ce_close_price = current['close']
        
        # 1. SuperTrend Bullish (based on CE option price)
        conditions['supertrend_bullish'] = current['supertrend_direction'] == 1
        
        # 2. CE Option Close > SuperTrend
        conditions['close_above_st'] = ce_close_price > current['supertrend']
        
        # 3. CE Option Close > EMA Low
        conditions['close_above_ema_low'] = ce_close_price > current['ema_low_8']
        
        # 4. EMA 8 > EMA 9 (calculated from CE option price)
        conditions['ema_bullish'] = current['ema_8'] > current['ema_9']
        
        # 5. StochRSI < 50 OR Rising (calculated from CE option price)
        stoch_rising = current['stoch_rsi_k'] > prev['stoch_rsi_k']
        conditions['stoch_ok'] = current['stoch_rsi_k'] < self.config['stoch_rsi_threshold'] or stoch_rising
        
        # 6. RSI < 65 AND Rising (calculated from CE option price)
        rsi_rising = current['rsi_14'] > prev['rsi_14']
        conditions['rsi_ok'] = current['rsi_14'] < self.config['rsi_max'] and rsi_rising
        
        # 7. MACD Histogram > 0 OR Improving (calculated from CE option price)
        macd_improving = current['macd_hist'] > prev['macd_hist']
        conditions['macd_ok'] = current['macd_hist'] > 0 or macd_improving
        
        # All conditions must be true
        all_conditions_met = all(conditions.values())
        
        # Add indicator values for display (all based on CE option price)
        conditions['values'] = {
            'close': ce_close_price,  # CE option close price
            'supertrend': current['supertrend'],
            'supertrend_dir': 'BULLISH' if current['supertrend_direction'] == 1 else 'BEARISH',
            'ema_low': current['ema_low_8'],
            'ema_8': current['ema_8'],
            'ema_9': current['ema_9'],
            'stoch_rsi': current['stoch_rsi_k'],
            'rsi': current['rsi_14'],
            'macd_hist': current['macd_hist']
        }
        
        if all_conditions_met:
            logger.info(f"✓ BUY signal confirmed on {timeframe} - All conditions met (CE Option: {ce_symbol}, Price: ₹{ce_close_price:.2f})")
        else:
            failed_conditions = [k for k, v in conditions.items() if k != 'values' and not v]
            logger.debug(f"✗ BUY signal not ready on {timeframe} - Failed conditions: {failed_conditions} (CE Option: {ce_symbol})")
        
        return all_conditions_met, conditions
    
    def check_exit_conditions(self, df_2min):
        """
        Check exit conditions on 2-minute timeframe (ADR-001)
        
        IMPORTANT: This validates exit signals based on CE OPTION price data, not NIFTY index.
        The DataFrame passed should contain CE option OHLC data from get_historical_data().
        
        Exit Trigger 1: EMA Low Falling (based on CE option price)
        - EMA Low falling for 2+ candles AND CE option price below EMA Low
        
        Exit Trigger 2: Strong Bearish Signal (based on CE option price)
        - SuperTrend bearish AND EMA 8 < EMA 9 AND CE option Close < EMA Low
        
        Args:
            df_2min: DataFrame with CE option OHLC data (from get_historical_data)
        
        Returns:
            Tuple of (should_exit, exit_reason, details)
        """
        if len(df_2min) < 5:
            return False, None, {"error": "Insufficient data"}
        
        # Validate that we have CE option selected (for logging clarity)
        ce_symbol = self.selected_option.get('tradingsymbol', 'Unknown') if self.selected_option else 'Not Selected'
        
        # Calculate indicators from CE option price data
        df_2min = calculate_all_indicators(df_2min)
        
        current = df_2min.iloc[-1]
        prev = df_2min.iloc[-2]
        prev2 = df_2min.iloc[-3]
        
        # All exit conditions use CE option's close price (current['close'])
        ce_close_price = current['close']
        
        # Exit Trigger 1: EMA Low Falling (based on CE option price)
        ema_low_falling = (
            current['ema_low_8'] < prev['ema_low_8'] and
            prev['ema_low_8'] < prev2['ema_low_8']
        )
        price_below_ema = ce_close_price < current['ema_low_8']
        
        exit_trigger_1 = ema_low_falling and price_below_ema
        
        # Exit Trigger 2: Strong Bearish (based on CE option price)
        strong_bearish = (
            current['supertrend_direction'] == -1 and  # Bearish SuperTrend
            current['ema_8'] < current['ema_9'] and    # EMA crossed down
            ce_close_price < current['ema_low_8']      # CE option price below EMA Low
        )
        
        exit_trigger_2 = strong_bearish
        
        details = {
            'ema_low_falling': ema_low_falling,
            'price_below_ema': price_below_ema,
            'strong_bearish': strong_bearish,
            'ce_symbol': ce_symbol,
            'values': {
                'close': ce_close_price,  # CE option close price
                'ema_low': current['ema_low_8'],
                'supertrend_dir': 'BULLISH' if current['supertrend_direction'] == 1 else 'BEARISH',
                'ema_8': current['ema_8'],
                'ema_9': current['ema_9']
            }
        }
        
        if exit_trigger_1:
            logger.info(f"✓ EXIT signal triggered: EMA Low Falling (CE Option: {ce_symbol}, Price: ₹{ce_close_price:.2f})")
            return True, "ema_low_falling", details
        elif exit_trigger_2:
            logger.info(f"✓ EXIT signal triggered: Strong Bearish (CE Option: {ce_symbol}, Price: ₹{ce_close_price:.2f})")
            return True, "strong_bearish", details
        
        return False, None, details
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ORDER EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def place_buy_order(self, symbol, quantity):
        """
        Place a MARKET BUY order
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
        
        Returns:
            Order ID or None
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=self.config['exchange'],
                tradingsymbol=symbol,
                transaction_type="BUY",
                quantity=quantity,
                product=self.config['product_type'],
                order_type=self.config['order_type'],
                validity="DAY"
            )
            
            logger.info(f"BUY Order Placed - ID: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing BUY order: {e}")
            return None
    
    def place_sell_order(self, symbol, quantity, reason="manual"):
        """
        Place a MARKET SELL order
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            reason: Exit reason for logging
        
        Returns:
            Order ID or None
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=self.config['exchange'],
                tradingsymbol=symbol,
                transaction_type="SELL",
                quantity=quantity,
                product=self.config['product_type'],
                order_type=self.config['order_type'],
                validity="DAY"
            )
            
            logger.info(f"SELL Order Placed - ID: {order_id} | Reason: {reason}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing SELL order: {e}")
            return None
    
    def get_order_status(self, order_id):
        """Get order status"""
        try:
            orders = self.kite.order_history(order_id)
            if orders:
                return orders[-1]  # Latest status
            return None
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return None
    
    def get_filled_price(self, order_id):
        """Get average filled price for an order"""
        status = self.get_order_status(order_id)
        if status and status.get('status') == 'COMPLETE':
            return status.get('average_price', 0)
        return 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def record_trade(self, entry_price, exit_price, quantity, symbol, exit_reason):
        """Record a completed trade"""
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        
        trade = {
            'trade_number': len(self.daily_trades) + 1,
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'entry_time': self.entry_time,
            'exit_time': self.get_current_time_ist()
        }
        
        self.daily_trades.append(trade)
        self.total_pnl += pnl
        
        logger.info(f"Trade #{trade['trade_number']} Recorded:")
        logger.info(f"  {symbol} | Entry ₹{entry_price:.2f} → Exit ₹{exit_price:.2f}")
        logger.info(f"  P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%) | Reason: {exit_reason}")
        
        return trade
    
    def get_current_pnl(self):
        """Get current unrealized P&L if position is open"""
        if not self.position_open or not self.selected_option:
            return 0
        
        current_price = self.refresh_option_premium()
        if current_price and self.entry_price:
            return (current_price - self.entry_price) * self.position_quantity
        return 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DISPLAY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def display_status(self, signal_5min=None, signal_2min=None):
        """Display current trading status"""
        now = self.get_current_time_ist()
        nifty_spot = self.get_nifty_spot_price()
        minutes_to_close = self.get_time_to_market_close()
        
        print("\n" + "═" * 80)
        print(f"  NIFTY CE AUTO TRADER - {now.strftime('%Y-%m-%d %H:%M:%S')} IST")
        print(f"  MODE: CONTINUOUS TRADING | TRADE CYCLE #{self.trade_cycle}")
        print("═" * 80)
        
        # Market Status
        market_status = "OPEN" if self.is_market_open() else "CLOSED"
        watch_only = self.is_watch_only_period() if hasattr(self, 'is_watch_only_period') else False
        trading_allowed = self.can_trade() if hasattr(self, 'can_trade') else self.is_market_open()
        
        print(f"\n  MARKET STATUS")
        print("  " + "─" * 76)
        print(f"  Market: {market_status} | Time to Close: {minutes_to_close} minutes")
        if watch_only:
            print(f"  ⚠️  WATCH-ONLY MODE (9:25-9:30 AM) - Monitoring enabled, Trading disabled")
        elif not trading_allowed and market_status == "OPEN":
            print(f"  ⚠️  Trading disabled (outside trading hours)")
        elif trading_allowed:
            print(f"  ✓ Trading enabled")
        
        # Account Status
        print(f"\n  ACCOUNT STATUS")
        print("  " + "─" * 76)
        print(f"  Available Balance: ₹{self.available_balance:,.2f}")
        print(f"  Trading Capital ({self.config['risk_factor']*100:.0f}%): ₹{self.trading_capital:,.2f}")
        
        # Selected Option
        if self.selected_option:
            print(f"\n  SELECTED OPTION (via ADR-003 Scanner)")
            print("  " + "─" * 76)
            print(f"  Symbol: {self.selected_option['tradingsymbol']}")
            print(f"  Strike: {self.selected_option['strike']} (ATM)")
            print(f"  Expiry: {self.expiry_date.strftime('%d-%b-%Y') if self.expiry_date else 'N/A'}")
            print(f"  Current Premium: ₹{self.selected_option['ltp']:.2f}")
            print(f"  Lot Size: {self.config['lot_size']}")
            
            # Quantity Calculation
            print(f"\n  QUANTITY CALCULATION")
            print("  " + "─" * 76)
            cost_per_lot = self.selected_option['ltp'] * self.config['lot_size']
            max_lots = math.floor(self.trading_capital / cost_per_lot) if cost_per_lot > 0 else 0
            print(f"  Cost per Lot: ₹{self.selected_option['ltp']:.2f} × {self.config['lot_size']} = ₹{cost_per_lot:,.2f}")
            print(f"  Max Lots: floor(₹{self.trading_capital:,.2f} / ₹{cost_per_lot:,.2f}) = {max_lots} Lots")
            print(f"  Trading Quantity: {max_lots} × {self.config['lot_size']} = {self.calculated_quantity}")
            print(f"  Total Investment: ₹{self.calculated_quantity * self.selected_option['ltp']:,.2f}")
        
        # Double Confirmation Status
        print(f"\n  DOUBLE CONFIRMATION STATUS (ADR-001)")
        print("  " + "─" * 76)
        print(f"  NIFTY Spot: ₹{nifty_spot:,.2f} (Reference only)")
        
        # Show which instrument is being monitored and validated
        if self.selected_option:
            ce_symbol = self.selected_option.get('tradingsymbol', 'Unknown')
            ce_premium = self.selected_option.get('ltp', 0)
            print(f"  ✓ Monitoring & Validating: CE Option {ce_symbol} @ ₹{ce_premium:.2f}")
            print(f"  ⚠️  BUY validation based on CE Option price data (not NIFTY index)")
            print(f"  ⚠️  All indicators calculated from CE Option OHLC data")
        else:
            print(f"  ⚠️  Monitoring: NIFTY Index (CE option not selected yet)")
            print(f"  ⚠️  BUY validation will use CE Option data once option is selected")
        
        if signal_5min and signal_2min:
            vals_5 = signal_5min.get('values', {})
            vals_2 = signal_2min.get('values', {})
            
            print(f"\n  | {'Indicator':<14} | {'5-MIN':>7} | {'2-MIN':>7} | {'Status':>7} |")
            print("  |" + "-" * 16 + "|" + "-" * 9 + "|" + "-" * 9 + "|" + "-" * 9 + "|")
            
            # SuperTrend
            st_5 = vals_5.get('supertrend_dir', 'N/A')[:7]
            st_2 = vals_2.get('supertrend_dir', 'N/A')[:7]
            st_ok = "✓" if signal_5min.get('supertrend_bullish') and signal_2min.get('supertrend_bullish') else "✗"
            print(f"  | {'SuperTrend':<14} | {st_5:>7} | {st_2:>7} | {st_ok:>7} |")
            
            # Price > ST
            pst_5 = "YES" if signal_5min.get('close_above_st') else "NO"
            pst_2 = "YES" if signal_2min.get('close_above_st') else "NO"
            pst_ok = "✓" if signal_5min.get('close_above_st') and signal_2min.get('close_above_st') else "✗"
            print(f"  | {'Price > ST':<14} | {pst_5:>7} | {pst_2:>7} | {pst_ok:>7} |")
            
            # EMA Cross
            ema_5 = "8 > 9" if signal_5min.get('ema_bullish') else "8 < 9"
            ema_2 = "8 > 9" if signal_2min.get('ema_bullish') else "8 < 9"
            ema_ok = "✓" if signal_5min.get('ema_bullish') and signal_2min.get('ema_bullish') else "✗"
            print(f"  | {'EMA Cross':<14} | {ema_5:>7} | {ema_2:>7} | {ema_ok:>7} |")
            
            # Price > EMA Lo
            pel_5 = "YES" if signal_5min.get('close_above_ema_low') else "NO"
            pel_2 = "YES" if signal_2min.get('close_above_ema_low') else "NO"
            pel_ok = "✓" if signal_5min.get('close_above_ema_low') and signal_2min.get('close_above_ema_low') else "✗"
            print(f"  | {'Price > EMA Lo':<14} | {pel_5:>7} | {pel_2:>7} | {pel_ok:>7} |")
            
            # StochRSI
            sr_5 = f"{vals_5.get('stoch_rsi', 0):.1f}"
            sr_2 = f"{vals_2.get('stoch_rsi', 0):.1f}"
            sr_ok = "✓" if signal_5min.get('stoch_ok') and signal_2min.get('stoch_ok') else "✗"
            print(f"  | {'StochRSI':<14} | {sr_5:>7} | {sr_2:>7} | {sr_ok:>7} |")
            
            # RSI
            rsi_5 = f"{vals_5.get('rsi', 0):.1f}"
            rsi_2 = f"{vals_2.get('rsi', 0):.1f}"
            rsi_ok = "✓" if signal_5min.get('rsi_ok') and signal_2min.get('rsi_ok') else "✗"
            print(f"  | {'RSI':<14} | {rsi_5:>7} | {rsi_2:>7} | {rsi_ok:>7} |")
            
            # MACD Hist
            mh_5 = f"{vals_5.get('macd_hist', 0):+.2f}"
            mh_2 = f"{vals_2.get('macd_hist', 0):+.2f}"
            mh_ok = "✓" if signal_5min.get('macd_ok') and signal_2min.get('macd_ok') else "✗"
            print(f"  | {'MACD Hist':<14} | {mh_5:>7} | {mh_2:>7} | {mh_ok:>7} |")
            
            print(f"\n  PRIMARY SIGNAL (5-min): {'✓ BUY' if self.primary_signal else '✗ WAIT'}")
            print(f"  CONFIRM SIGNAL (2-min): {'✓ BUY' if self.confirm_signal else '✗ WAIT'}")
        
        # Position Status
        if self.position_open:
            current_pnl = self.get_current_pnl()
            current_price = self.selected_option['ltp'] if self.selected_option else 0
            pnl_pct = ((current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
            
            print("\n" + "═" * 80)
            print(f"  Status: POSITION OPEN | Entry: ₹{self.entry_price:.2f} | "
                  f"Current: ₹{current_price:.2f} | P&L: ₹{current_pnl:+,.2f} ({pnl_pct:+.2f}%)")
        
        # Daily Summary
        if self.daily_trades:
            print(f"\n  DAILY SUMMARY (so far)")
            print("  " + "─" * 76)
            print(f"  Trades Completed: {len(self.daily_trades)}")
            print(f"  Total P&L: ₹{self.total_pnl:+,.2f}")
        
        print("═" * 80)
    
    def display_daily_summary(self):
        """Display end-of-day trading summary"""
        now = self.get_current_time_ist()
        
        print("\n" + "═" * 80)
        print(f"  DAILY TRADING SUMMARY - {now.strftime('%Y-%m-%d')}")
        print("═" * 80)
        print(f"  Total Trades: {len(self.daily_trades)}")
        print(f"  Total P&L: ₹{self.total_pnl:+,.2f}")
        
        if self.daily_trades:
            print(f"\n  TRADE DETAILS:")
            print("  " + "─" * 76)
            
            for trade in self.daily_trades:
                pnl_str = f"₹{trade['pnl']:+,.2f}"
                print(f"  #{trade['trade_number']}: {trade['symbol']} | "
                      f"Entry ₹{trade['entry_price']:.2f} → Exit ₹{trade['exit_price']:.2f} | "
                      f"P&L: {pnl_str} | {trade['exit_reason']}")
        
        print("═" * 80)
        print("  Goodbye!")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def execute_buy(self):
        """Execute BUY order with balance check"""
        logger.info("=" * 60)
        logger.info("DOUBLE CONFIRMATION ACHIEVED - EXECUTING BUY ORDER")
        logger.info("=" * 60)
        
        # Step 1: Refresh balance before buying
        self.refresh_balance_before_buy()
        
        # Step 2: Recalculate quantity with fresh balance
        self.refresh_option_premium()
        quantity = self.calculate_quantity()
        
        if quantity <= 0:
            logger.warning("Insufficient balance - waiting 1 minute before retrying")
            return False
        
        # Step 3: Place BUY order
        order_id = self.place_buy_order(
            self.selected_option['tradingsymbol'],
            quantity
        )
        
        if order_id:
            # Wait for order fill
            time.sleep(2)
            filled_price = self.get_filled_price(order_id)
            
            if filled_price > 0:
                self.position_open = True
                self.entry_price = filled_price
                self.entry_time = self.get_current_time_ist()
                self.position_quantity = quantity
                self.position_symbol = self.selected_option['tradingsymbol']
                
                logger.info(f"BUY Executed: {quantity} x {self.position_symbol} @ ₹{filled_price:.2f}")
                return True
            else:
                # Use LTP as fallback
                self.position_open = True
                self.entry_price = self.selected_option['ltp']
                self.entry_time = self.get_current_time_ist()
                self.position_quantity = quantity
                self.position_symbol = self.selected_option['tradingsymbol']
                
                logger.info(f"BUY Executed (LTP): {quantity} x {self.position_symbol} @ ₹{self.entry_price:.2f}")
                return True
        
        return False
    
    def execute_sell(self, reason="manual"):
        """Execute SELL order"""
        if not self.position_open:
            return False
        
        logger.info("=" * 60)
        logger.info(f"EXECUTING SELL ORDER - Reason: {reason}")
        logger.info("=" * 60)
        
        # Get current price before selling
        current_price = self.refresh_option_premium() or self.selected_option['ltp']
        
        # Place SELL order
        order_id = self.place_sell_order(
            self.position_symbol,
            self.position_quantity,
            reason
        )
        
        if order_id:
            # Wait for order fill
            time.sleep(2)
            filled_price = self.get_filled_price(order_id)
            
            exit_price = filled_price if filled_price > 0 else current_price
            
            # Record trade
            self.record_trade(
                entry_price=self.entry_price,
                exit_price=exit_price,
                quantity=self.position_quantity,
                symbol=self.position_symbol,
                exit_reason=reason
            )
            
            # Reset position state
            self.position_open = False
            self.entry_price = 0
            self.entry_time = None
            self.position_quantity = 0
            self.position_symbol = None
            
            logger.info(f"SELL Executed: Exit @ ₹{exit_price:.2f}")
            return True
        
        return False
    
    def wait_for_buy_signal(self):
        """Wait for double confirmation buy signal"""
        last_5min_check = 0
        
        while self.is_running and not self.position_open:
            now = time.time()
            
            # Check market hours
            if not self.is_market_open():
                logger.info("Market closed - stopping signal monitoring")
                return False
            
            # Check watch-only period
            if self.is_watch_only_period():
                logger.info("Watch-only period (9:25-9:30 AM) - monitoring but not trading")
                # Continue monitoring but don't execute trades
                self.display_status(signal_5min if 'signal_5min' in locals() else {}, signal_2min if 'signal_2min' in locals() else {})
                time.sleep(self.config['confirm_check_seconds'])
                continue
            
            # Check if we should stop new trades
            if self.should_stop_new_trades():
                logger.info("Less than 15 minutes to market close - no new trades")
                return False
            
            # Refresh option premium
            self.refresh_option_premium()
            
            # Validate that CE option is selected before checking buy conditions
            if not self.selected_option:
                logger.warning("CE option not selected - cannot validate buy conditions")
                time.sleep(self.config['confirm_check_seconds'])
                continue
            
            # Check 2-minute confirmation (every 5 seconds) - using CE option data
            df_2min = self.get_historical_data("2minute", use_ce_option=True)
            if not df_2min.empty:
                # Validate buy conditions based on CE option price data
                self.confirm_signal, signal_2min = self.check_buy_conditions(df_2min, "2minute")
            else:
                self.confirm_signal = False
                signal_2min = {}
                logger.warning(f"No 2-minute data available for CE option {self.selected_option.get('tradingsymbol', 'Unknown')}")
            
            # Check 5-minute primary (every 10 seconds) - using CE option data
            if now - last_5min_check >= self.config['primary_check_seconds']:
                df_5min = self.get_historical_data("5minute", use_ce_option=True)
                if not df_5min.empty:
                    # Validate buy conditions based on CE option price data
                    self.primary_signal, signal_5min = self.check_buy_conditions(df_5min, "5minute")
                else:
                    self.primary_signal = False
                    signal_5min = {}
                    logger.warning(f"No 5-minute data available for CE option {self.selected_option.get('tradingsymbol', 'Unknown')}")
                last_5min_check = now
            else:
                signal_5min = {}
            
            # Display status
            self.display_status(signal_5min, signal_2min)
            
            # Check for double confirmation - only return True if trading is allowed
            if self.primary_signal and self.confirm_signal:
                if self.can_trade():
                    return True
                else:
                    logger.info("Double confirmation achieved but trading not allowed (watch-only period)")
                    # Continue monitoring
            
            # Wait before next check
            time.sleep(self.config['confirm_check_seconds'])
        
        return False
    
    def monitor_for_exit(self):
        """Monitor position for exit conditions"""
        while self.is_running and self.position_open:
            # Check market hours
            if not self.is_market_open():
                logger.info("Market closed - forcing position exit")
                self.execute_sell("market_close")
                return
            
            # Check for market close
            if self.get_time_to_market_close() <= 0:
                logger.info("Market closing - forcing position exit")
                self.execute_sell("market_close")
                return
            
            # Refresh option premium
            self.refresh_option_premium()
            
            # Get 2-minute data for exit check - using CE option data
            df_2min = self.get_historical_data("2minute", use_ce_option=True)
            
            if not df_2min.empty:
                # Validate exit conditions based on CE option price data
                should_exit, exit_reason, exit_details = self.check_exit_conditions(df_2min)
                
                # Display current P&L
                current_pnl = self.get_current_pnl()
                current_price = self.selected_option['ltp'] if self.selected_option else 0
                pnl_pct = ((current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
                
                print(f"\r  Position: {self.position_symbol} | Entry: ₹{self.entry_price:.2f} | "
                      f"Current: ₹{current_price:.2f} | P&L: ₹{current_pnl:+,.2f} ({pnl_pct:+.2f}%)", end="")
                
                if should_exit:
                    print()  # New line
                    self.execute_sell(exit_reason)
                    return
            
            # Wait before next check
            time.sleep(self.config['confirm_check_seconds'])
    
    def run(self, expiry_date=None):
        """
        Main execution loop - continuous trading until market close
        
        Args:
            expiry_date: Expiry date string (e.g., "Jan 23", "2026-01-23")
        """
        # #region agent log
        debug_log("trader.py:1086", "run() method entry", {"expiry_date": expiry_date}, "B")
        # #endregion
        
        self.is_running = True
        
        # #region agent log
        debug_log("trader.py:1093", "is_running set to True", {"is_running": self.is_running}, "B")
        # #endregion
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PHASE 1: INITIALIZATION
            # ═══════════════════════════════════════════════════════════════════
            
            print("\n" + "═" * 80)
            print("  NIFTY CE AUTO TRADER - INITIALIZATION")
            print("═" * 80)
            
            # Get expiry date from user if not provided
            if expiry_date is None:
                # #region agent log
                debug_log("trader.py:1105", "Prompting for expiry date", {}, "B")
                # #endregion
                expiry_date = self.prompt_for_expiry()
            
            # Parse expiry date
            # #region agent log
            debug_log("trader.py:1110", "Parsing expiry date", {"expiry_date_input": expiry_date}, "B")
            # #endregion
            
            self.expiry_date = parse_expiry_date(expiry_date)
            logger.info(f"Expiry Date: {self.expiry_date.strftime('%d-%b-%Y')}")
            
            # #region agent log
            debug_log("trader.py:1113", "Expiry date parsed", {"parsed_expiry": self.expiry_date.strftime('%d-%b-%Y') if self.expiry_date else None}, "B")
            # #endregion
            
            # Get account balance
            # #region agent log
            debug_log("trader.py:1116", "Getting account balance", {}, "B")
            # #endregion
            
            self.get_account_balance()
            
            # #region agent log
            debug_log("trader.py:1119", "Account balance retrieved", {
                "available_balance": self.available_balance,
                "trading_capital": self.trading_capital
            }, "B")
            # #endregion
            
            # Check market hours
            market_open = self.is_market_open()
            # #region agent log
            debug_log("trader.py:1126", "Checking market hours", {"market_open": market_open}, "B")
            # #endregion
            
            if not market_open:
                logger.warning("Market is currently closed (9:15 AM - 3:30 PM IST)")
                print("\nMarket is closed. Auto Trader will wait for market to open...")
                
                # Wait for market to open
                while not self.is_market_open() and self.is_running:
                    time.sleep(60)  # Check every minute
            
            # ═══════════════════════════════════════════════════════════════════
            # CONTINUOUS TRADING LOOP
            # ═══════════════════════════════════════════════════════════════════
            
            # #region agent log
            debug_log("trader.py:1135", "Entering continuous trading loop", {}, "B")
            # #endregion
            
            while self.is_running and self.is_market_open():
                self.trade_cycle += 1
                
                # #region agent log
                debug_log("trader.py:1140", "Trade cycle started", {"trade_cycle": self.trade_cycle}, "B")
                # #endregion
                
                logger.info(f"\n{'='*60}")
                logger.info(f"TRADE CYCLE #{self.trade_cycle} STARTING")
                logger.info(f"{'='*60}")
                
                # Check if we should stop new trades
                should_stop = self.should_stop_new_trades()
                # #region agent log
                debug_log("trader.py:1148", "Checking if should stop new trades", {"should_stop": should_stop}, "B")
                # #endregion
                
                if should_stop:
                    logger.info("Less than 15 minutes to market close - stopping new trade cycles")
                    break
                
                # Check watch-only period - allow monitoring but not trading
                watch_only = self.is_watch_only_period()
                # #region agent log
                debug_log("trader.py:1157", "Checking watch-only period", {"watch_only": watch_only}, "B")
                # #endregion
                
                if watch_only:
                    logger.info("Watch-only period (9:25-9:30 AM) - monitoring market, scanning options...")
                    # Initialize scanner and display status but don't execute trades
                    self.initialize_scanner()
                    selected = self.select_best_ce_option()
                    if selected:
                        self.get_account_balance()
                        quantity = self.calculate_quantity()
                        self.display_status()
                    time.sleep(10)  # Wait 10 seconds before next check
                    continue
                
                # Check if trading is allowed
                can_trade_now = self.can_trade()
                # #region agent log
                debug_log("trader.py:1173", "Checking if trading allowed", {"can_trade": can_trade_now}, "B")
                # #endregion
                
                if not can_trade_now:
                    logger.info("Trading not allowed at this time - waiting...")
                    time.sleep(10)
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 2: OPTIONS SCANNER (ADR-003)
                # ═══════════════════════════════════════════════════════════════
                
                # Initialize/refresh scanner
                # #region agent log
                debug_log("trader.py:1183", "Initializing scanner", {}, "B")
                # #endregion
                
                self.initialize_scanner()
                
                # Select best CE option
                # #region agent log
                debug_log("trader.py:1189", "Selecting best CE option", {}, "B")
                # #endregion
                
                selected = self.select_best_ce_option()
                
                # #region agent log
                debug_log("trader.py:1193", "CE option selection result", {
                    "selected": selected is not None,
                    "symbol": selected.get('tradingsymbol') if selected else None,
                    "strike": selected.get('strike') if selected else None,
                    "premium": selected.get('ltp') if selected else None
                }, "B")
                # #endregion
                
                if not selected:
                    logger.warning("No suitable CE option found - waiting 30 seconds")
                    time.sleep(30)
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 3: QUANTITY CALCULATION
                # ═══════════════════════════════════════════════════════════════
                
                # Refresh balance and calculate quantity
                # #region agent log
                debug_log("trader.py:1209", "Refreshing balance for quantity calculation", {}, "B")
                # #endregion
                
                self.get_account_balance()
                quantity = self.calculate_quantity()
                
                # #region agent log
                debug_log("trader.py:1215", "Quantity calculated", {
                    "quantity": quantity,
                    "calculated_quantity": self.calculated_quantity
                }, "B")
                # #endregion
                
                if quantity <= 0:
                    logger.warning("Insufficient balance - waiting 1 minute")
                    time.sleep(60)
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 4: WAIT FOR DOUBLE CONFIRMATION (ADR-001)
                # ═══════════════════════════════════════════════════════════════
                
                logger.info("Waiting for Double Confirmation BUY signal...")
                
                # #region agent log
                debug_log("trader.py:1227", "Waiting for buy signal", {}, "B")
                # #endregion
                
                buy_signal_received = self.wait_for_buy_signal()
                
                # #region agent log
                debug_log("trader.py:1232", "Buy signal check result", {"buy_signal_received": buy_signal_received}, "B")
                # #endregion
                
                if buy_signal_received:
                    # ═══════════════════════════════════════════════════════════
                    # PHASE 5: EXECUTE BUY
                    # ═══════════════════════════════════════════════════════════
                    
                    # Double-check trading is allowed before executing
                    can_trade_before_buy = self.can_trade()
                    # #region agent log
                    debug_log("trader.py:1241", "Final trading check before buy", {"can_trade": can_trade_before_buy}, "B")
                    # #endregion
                    
                    if not can_trade_before_buy:
                        logger.info("Trading not allowed - skipping order execution")
                        continue
                    
                    # #region agent log
                    debug_log("trader.py:1248", "Executing buy order", {
                        "symbol": self.selected_option.get('tradingsymbol') if self.selected_option else None,
                        "quantity": self.calculated_quantity
                    }, "B")
                    # #endregion
                    
                    buy_executed = self.execute_buy()
                    
                    # #region agent log
                    debug_log("trader.py:1255", "Buy execution result", {
                        "buy_executed": buy_executed,
                        "position_open": self.position_open
                    }, "B")
                    # #endregion
                    
                    if buy_executed:
                        # ═══════════════════════════════════════════════════════
                        # PHASE 6: MONITOR FOR EXIT
                        # ═══════════════════════════════════════════════════════
                        
                        logger.info("Position opened - monitoring for exit conditions...")
                        # #region agent log
                        debug_log("trader.py:1265", "Starting exit monitoring", {
                            "entry_price": self.entry_price,
                            "position_quantity": self.position_quantity
                        }, "B")
                        # #endregion
                        
                        self.monitor_for_exit()
                    else:
                        # Buy failed (insufficient balance)
                        logger.warning("Buy failed - waiting 1 minute before restart")
                        time.sleep(60)
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 7: REPEAT CYCLE
                # ═══════════════════════════════════════════════════════════════
                
                if self.is_market_open() and not self.should_stop_new_trades():
                    logger.info("Trade cycle complete - starting new cycle...")
                    time.sleep(5)  # Brief pause before next cycle
            
            # ═══════════════════════════════════════════════════════════════════
            # END OF DAY
            # ═══════════════════════════════════════════════════════════════════
            
            # Force exit any open position
            if self.position_open:
                logger.info("End of trading day - closing open position")
                self.execute_sell("market_close")
            
            # Display daily summary
            self.display_daily_summary()
            
        except KeyboardInterrupt:
            # #region agent log
            debug_log("trader.py:1278", "KeyboardInterrupt caught", {}, "B")
            # #endregion
            
            logger.info("\nTrading stopped by user")
            
            # Close any open position
            if self.position_open:
                logger.info("Closing open position...")
                self.execute_sell("user_stop")
            
            self.display_daily_summary()
            
        except Exception as e:
            # #region agent log
            debug_log("trader.py:1291", "Exception in trading loop", {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }, "B")
            # #endregion
            
            logger.error(f"Error in trading loop: {e}")
            raise
        
        finally:
            # #region agent log
            debug_log("trader.py:1300", "run() method finally block", {
                "final_trade_cycle": self.trade_cycle,
                "total_trades": len(self.daily_trades),
                "total_pnl": self.total_pnl
            }, "B")
            # #endregion
            
            self.is_running = False
    
    def prompt_for_expiry(self):
        """Prompt user for expiry date input"""
        print("\n" + "═" * 80)
        print("  NIFTY CE AUTO TRADER - Configuration")
        print("═" * 80)
        print("\nEnter expiry date in any of these formats:")
        print("  - 'Jan 23' or '23 Jan'")
        print("  - 'Jan 23 2026' or '23 Jan 2026'")
        print("  - '2026-01-23' (ISO format)")
        print("─" * 80)
        
        expiry_input = input("\nEnter Expiry Date (e.g., Jan 23): ").strip()
        
        if not expiry_input:
            raise ValueError("Expiry date is required")
        
        return expiry_input
    
    def stop(self):
        """Stop the trader"""
        self.is_running = False
        logger.info("Trader stopping...")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    print("\n" + "═" * 80)
    print("  INTEGRATED NIFTY CE AUTO TRADER")
    print("  Based on ADR-004: Options Scanner (ADR-003) + Double Confirmation (ADR-001)")
    print("═" * 80)
    
    try:
        trader = IntegratedNiftyCETrader()
        trader.run()
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
