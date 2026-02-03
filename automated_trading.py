#!/usr/bin/env python3
"""
Automated Trading Entry Point
Wrapper around IntegratedNiftyCETrader with enhanced error handling

This is a user-friendly entry point for the automated NIFTY CE trading system.
It provides better error handling and user experience compared to the direct trader.

Usage:
    python automated_trading.py
"""

import sys
import logging
from datetime import datetime
import pytz

from trading.trader import IntegratedNiftyCETrader

# Setup logging (console + file)
from utils.logging_config import setup_logging
setup_logging(level=logging.INFO, log_prefix="automated_trading")
logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


def main():
    """Main entry point for automated trading"""
    print("\n" + "═" * 80)
    print("  AUTOMATED NIFTY CE TRADING SYSTEM")
    print("  Based on ADR-004: Options Scanner + Double Confirmation Strategy")
    print("═" * 80)
    
    trader = None
    
    try:
        # Create trader instance
        logger.info("Initializing Automated Trading System...")
        trader = IntegratedNiftyCETrader()
        
        # Display current time
        current_time = datetime.now(IST)
        logger.info(f"Current Time (IST): {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Run the trading system
        logger.info("Starting trading system...")
        trader.run()
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.info("Trading stopped by user (Ctrl+C)")
        logger.info("=" * 80)
        
        if trader and trader.position_open:
            logger.info("Closing open position...")
            try:
                trader.execute_sell("user_stop")
            except Exception as e:
                logger.error(f"Error closing position: {e}")
        
        if trader:
            trader.display_daily_summary()
        
        sys.exit(0)
        
    except ValueError as e:
        logger.error("\n" + "=" * 80)
        logger.error("CONFIGURATION ERROR")
        logger.error("=" * 80)
        logger.error(f"{e}")
        logger.error("\nPlease check:")
        logger.error("  1. .env file exists and contains KITE_API_KEY and KITE_ACCESS_TOKEN")
        logger.error("  2. API credentials are valid")
        logger.error("  3. Expiry date format is correct")
        sys.exit(1)
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("UNEXPECTED ERROR")
        logger.error("=" * 80)
        logger.error(f"{e}", exc_info=True)
        
        if trader and trader.position_open:
            logger.warning("Position is still open - please check manually")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
