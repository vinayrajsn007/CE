#!/usr/bin/env python3
"""
Entry point for Integrated NIFTY CE Auto Trader
"""
import json
import os
from datetime import datetime
from trading.trader import IntegratedNiftyCETrader

# Debug logging helper
DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "debug.log")

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

if __name__ == "__main__":
    # ═══════════════════════════════════════════════════════════════════════════
    # DEBUG BREAKPOINT 1: Entry Point
    # Set breakpoint here to start debugging from the beginning
    # ═══════════════════════════════════════════════════════════════════════════
    # #region agent log
    debug_log("integrated_nifty_ce_trader.py:8", "Entry point execution started", {"script": __file__}, "A")
    # #endregion
    
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # DEBUG BREAKPOINT 2: Before Trader Initialization
        # Check: Environment variables loaded, .env file exists
        # ═══════════════════════════════════════════════════════════════════════
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:11", "Creating IntegratedNiftyCETrader instance", {}, "A")
        # #endregion
        
        # DEBUG: Step into this to see initialization
        trader = IntegratedNiftyCETrader()
        
        # ═══════════════════════════════════════════════════════════════════════
        # DEBUG BREAKPOINT 3: After Trader Initialization
        # Check: trader.kite is not None, config loaded, state initialized
        # Watch: trader.kite, trader.config, trader.is_running
        # ═══════════════════════════════════════════════════════════════════════
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:15", "Trader instance created", {
            "has_kite": trader.kite is not None,
            "is_running": trader.is_running,
            "trade_cycle": trader.trade_cycle
        }, "A")
        # #endregion
        
        # ═══════════════════════════════════════════════════════════════════════
        # DEBUG BREAKPOINT 4: Before Run Method
        # Check: All initialization complete, ready to start trading
        # ═══════════════════════════════════════════════════════════════════════
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:23", "Calling trader.run()", {}, "A")
        # #endregion
        
        # DEBUG: Step into this to enter main trading loop
        trader.run()
        
        # ═══════════════════════════════════════════════════════════════════════
        # DEBUG BREAKPOINT 5: After Run Completes
        # Check: Final state, total trades, P&L summary
        # ═══════════════════════════════════════════════════════════════════════
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:27", "trader.run() completed", {
            "final_trade_cycle": trader.trade_cycle,
            "total_trades": len(trader.daily_trades),
            "total_pnl": trader.total_pnl
        }, "A")
        # #endregion
        
    except KeyboardInterrupt as e:
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:35", "KeyboardInterrupt caught", {"error": str(e)}, "A")
        # #endregion
        raise
    except Exception as e:
        # #region agent log
        debug_log("integrated_nifty_ce_trader.py:39", "Exception caught in main", {
            "error_type": type(e).__name__,
            "error_message": str(e)
        }, "A")
        # #endregion
        raise
