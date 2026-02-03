# ADR-004: Integrated NIFTY CE Auto Trader

**Status:** Accepted  
**Date:** January 2026  
**Author:** Trading System Team  
**Deciders:** Strategy Development Team  
**Integrates:** ADR-001 (Double Confirmation Strategy), ADR-003 (Options Scanner)

---

## Context

We need an automated trading system that:
- Gets the current account balance to determine position sizing
- Takes NIFTY Options Expiry Date as user input
- Uses **ADR-003 Options Scanner** to select optimal CALL options (premium ₹70-₹130)
- Uses **ADR-001 Double Confirmation Strategy** to time entries and exits
- **Monitors Selected CE Option data (not NIFTY Index) for buy/exit validation**
- **All indicators and buy/exit conditions validated using CE Option price data**
- Automatically calculates quantity based on available balance (90% risk factor)
- Executes CE BUY when double confirmation signals are validated on CE Option
- Executes CE SELL when exit conditions are detected on CE Option
- **Repeats the entire trading cycle after each exit until market closes**
- **Operates within market hours (9:15 AM - 3:30 PM IST)**
- **Watch-only mode (9:25-9:30 AM) - monitors market but doesn't trade**
- **Trading starts at 9:30 AM**
- **Tracks daily performance across multiple trades**

---

## Decision

We will implement an **Integrated NIFTY CE Auto Trader** that combines the Options Scanner for instrument selection with the **Double Confirmation Strategy (ADR-001)** for trade timing. The system monitors **Selected CE Option data** (not NIFTY Index) to validate buy/exit signals. All technical indicators (SuperTrend, EMA, RSI, MACD, StochRSI) are calculated from CE Option OHLC data, ensuring buy/exit validation is based on the actual option being traded. The system operates in a **continuous loop**, executing multiple trades throughout the trading day until market close.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     INTEGRATED NIFTY CE AUTO TRADER                               │
│                    (ADR-003 + ADR-001 Combined System)                            │
│                    (Uses CE Option Data for Buy/Exit Validation)                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 1: INITIALIZATION                                                │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   1. Authenticate with Kite Connect                                     │   │
│   │   2. Get Current Account Balance                                        │   │
│   │   3. Accept Expiry Date Input from User                                 │   │
│   │   4. Display Available Balance & Trading Capacity                       │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 2: OPTIONS SCANNER (ADR-003)                                     │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Filter NIFTY Options: Strike 24000-26000                           │   │
│   │   • Premium Range: ₹70-₹130                                             │   │
│   │   • Select Best CE Option (ATM or based on criteria)                   │   │
│   │   • Output: Selected CALL Option Instrument                             │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 3: QUANTITY CALCULATION                                          │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Available Margin = Balance × Risk Factor (default: 40%)            │   │
│   │   • Max Lots = Available Margin ÷ (Option Premium × Lot Size)          │   │
│   │   • Quantity = Max Lots × 75 (NIFTY Lot Size)                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 4: DOUBLE CONFIRMATION MONITORING (ADR-001 - Using CE Option)     │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Monitor SELECTED CE OPTION with 5-min and 2-min timeframes         │   │
│   │   • Fetch CE Option historical OHLC data (not NIFTY index)              │   │
│   │   • Calculate: SuperTrend, EMA, RSI, MACD, StochRSI on CE Option       │   │
│   │   • Validate buy conditions using CE Option price data                 │   │
│   │   • Wait for BOTH timeframes to confirm BUY signal on CE Option        │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                     ┌──────────────┴──────────────┐                             │
│                     ▼                              ▼                             │
│   ┌─────────────────────────────┐  ┌─────────────────────────────┐             │
│   │  PHASE 5A: EXECUTE BUY      │  │  PHASE 5B: WAIT FOR SIGNAL  │             │
│   │  ────────────────────────   │  │  ────────────────────────── │             │
│   │  • CHECK BALANCE FIRST      │  │  • Continue Monitoring      │             │
│   │  • Recalculate Quantity     │  │  • Check Every 5 Seconds    │             │
│   │  • Verify Sufficient Funds  │  │  • Update Scanner Data      │             │
│   │  • Place BUY Order          │  │  • Re-evaluate Selection    │             │
│   │  • MARKET Order             │  │                             │             │
│   └─────────────────────────────┘  └─────────────────────────────┘             │
│                     │                                                            │
│                     ▼                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 6: EXIT MONITORING                                               │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Monitor 2-min timeframe for exit signals                           │   │
│   │   • Check: EMA Low Falling + Price Below EMA Low                       │   │
│   │   • Check: Strong Bearish Signal Override                              │   │
│   │   • Check: MACD Bearish Momentum (MACD < Signal)                       │   │
│   │   • Execute SELL when ANY condition met                                │   │
│   │   • Force exit at market close (3:30 PM)                               │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  PHASE 7: REPEAT CYCLE (CONTINUOUS TRADING)                            │   │
│   │  ──────────────────────────────────────────────────────────────────     │   │
│   │   • Record trade P&L to daily summary                                  │   │
│   │   • Check if market is still open (before 3:15 PM)                     │   │
│   │   • If YES: Go back to PHASE 1 (Refresh Balance, Re-scan Options)      │   │
│   │   • If NO: Stop trading, display daily summary                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW ARCHITECTURE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌───────────┐     ┌─────────────────────────────────────────────────────────┐  │
│  │   USER    │────▶│   INPUT: Expiry Date (e.g., "Jan 23" or "2026-01-23")   │  │
│  └───────────┘     └────────────────────────────┬────────────────────────────┘  │
│                                                  │                               │
│                                                  ▼                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         KITE CONNECT API                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │   │
│  │  │ kite.margins() │  │ instruments()  │  │ kite.historical_data()     │ │   │
│  │  │ Get Balance    │  │ Get Options    │  │ Get CE Option OHLC Data    │ │   │
│  │  └───────┬────────┘  └───────┬────────┘  └─────────────┬──────────────┘ │   │
│  └──────────┼───────────────────┼─────────────────────────┼─────────────────┘   │
│             │                   │                         │                      │
│             ▼                   ▼                         ▼                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────────────┐   │
│  │ Account Balance │  │ Options Scanner │  │ Double Confirmation Strategy   │   │
│  │ ₹XX,XXX         │  │ (ADR-003)       │  │ (ADR-001)                      │   │
│  └────────┬────────┘  └────────┬────────┘  └───────────────┬────────────────┘   │
│           │                    │                           │                     │
│           │                    ▼                           │                     │
│           │         ┌───────────────────────┐             │                     │
│           │         │ Selected CE Option    │             │                     │
│           │         │ NIFTY26JAN25500CE     │             │                     │
│           │         │ Premium: ₹95          │             │                     │
│           │         └───────────┬───────────┘             │                     │
│           │                     │                          │                     │
│           └─────────────────────┼──────────────────────────┘                     │
│                                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      QUANTITY CALCULATOR                                  │   │
│  │                                                                           │   │
│  │  Available: ₹50,000  →  Premium: ₹95  →  Lot Size: 75                    │   │
│  │                                                                           │   │
│  │  Max Investment = ₹50,000 × 40% = ₹20,000                                │   │
│  │  Cost per Lot = ₹95 × 75 = ₹7,125                                        │   │
│  │  Max Lots = ₹20,000 ÷ ₹7,125 = 2 Lots                                    │   │
│  │  Quantity = 2 × 75 = 150                                                 │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                 │                                                │
│                                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     TRADING ENGINE                                        │   │
│  │                                                                           │   │
│  │  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐        │   │
│  │  │ WAIT STATE  │────────▶│ BUY ORDER   │────────▶│ POSITION    │        │   │
│  │  │ Monitoring  │  Signal │ Execute     │  Filled │ HOLDING     │        │   │
│  │  └─────────────┘         └─────────────┘         └──────┬──────┘        │   │
│  │                                                         │                │   │
│  │                                                   Exit  │                │   │
│  │                                                  Signal ▼                │   │
│  │                                                  ┌─────────────┐        │   │
│  │                                                  │ SELL ORDER  │        │   │
│  │                                                  │ Execute     │        │   │
│  │                                                  └─────────────┘        │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Expiry Date** | User Input | NIFTY Options expiry date |
| **Strike Min** | 24000 | Minimum strike price |
| **Strike Max** | 26000 | Maximum strike price |
| **Strike Multiple** | 100 | Only strikes in multiples of 100 |
| **Premium Min** | 70 | Minimum option premium |
| **Premium Max** | 130 | Maximum option premium |
| **Risk Factor** | 40% | Percentage of balance to use |
| **Lot Size** | 75 | NIFTY options lot size |
| **Scanner Refresh** | 5 seconds | Options scanner refresh rate |
| **Signal Source** | CE Option | Monitor selected CE option for buy/exit validation |
| **Primary TF** | 5-minute | Double confirmation primary timeframe (PE data) |
| **Confirm TF** | 2-minute | Double confirmation secondary timeframe (PE data) |
| **Market Open** | 9:15 AM IST | Market opens (monitoring starts) |
| **Watch-Only Period** | 9:25-9:30 AM IST | Monitor market, scan options, but NO trading |
| **Trading Start** | 9:30 AM IST | Active trading begins |
| **Market Close** | 3:30 PM IST | Trading end time |
| **Stop New Trades** | 15 minutes | Before market close (3:15 PM) |

---

## Balance & Quantity Calculation

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        BALANCE & QUANTITY CALCULATION                             │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   STEP 1: GET ACCOUNT BALANCE                                                    │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   margins = kite.margins(segment="equity")                                │ │
│   │   available_balance = margins['equity']['available']['live_balance']      │ │
│   │                                                                            │ │
│   │   Example Response:                                                        │ │
│   │   {                                                                        │ │
│   │     "equity": {                                                            │ │
│   │       "available": {                                                       │ │
│   │         "live_balance": 50000.00,                                         │ │
│   │         "adhoc_margin": 0,                                                │ │
│   │         "collateral": 0                                                   │ │
│   │       },                                                                   │ │
│   │       "utilised": { ... }                                                 │ │
│   │     }                                                                      │ │
│   │   }                                                                        │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 2: CALCULATE AVAILABLE MARGIN FOR TRADING                                │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   risk_factor = 0.40  # Use 40% of balance                                │ │
│   │   trading_capital = available_balance × risk_factor                       │ │
│   │                                                                            │ │
│   │   Example: ₹50,000 × 0.40 = ₹20,000 available for trading                 │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 3: GET SELECTED OPTION PREMIUM (FROM SCANNER)                            │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   selected_option = scanner.get_best_ce_option()                          │ │
│   │   option_premium = selected_option['ltp']  # e.g., ₹95                    │ │
│   │   lot_size = 75  # NIFTY lot size                                         │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                       │
│                                          ▼                                       │
│   STEP 4: CALCULATE QUANTITY                                                     │
│   ┌───────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                            │ │
│   │   cost_per_lot = option_premium × lot_size                                │ │
│   │   max_lots = floor(trading_capital ÷ cost_per_lot)                        │ │
│   │   quantity = max_lots × lot_size                                          │ │
│   │                                                                            │ │
│   │   Example:                                                                 │ │
│   │   ─────────                                                                │ │
│   │   cost_per_lot = ₹95 × 75 = ₹7,125                                        │ │
│   │   max_lots = floor(₹20,000 ÷ ₹7,125) = 2 lots                             │ │
│   │   quantity = 2 × 75 = 150 shares                                          │ │
│   │                                                                            │ │
│   │   Total Investment = 150 × ₹95 = ₹14,250                                  │ │
│   │                                                                            │ │
│   └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Option Selection Logic (From ADR-003)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        CE OPTION SELECTION CRITERIA                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   STEP 1: Get NIFTY Spot Price                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   nifty_ltp = kite.ltp("NSE:NIFTY 50")['NSE:NIFTY 50']['last_price']    │   │
│   │   Example: ₹25,480.50                                                    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 2: Calculate ATM Strike                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   atm_strike = round(nifty_ltp / 100) × 100                             │   │
│   │   Example: round(25480.50 / 100) × 100 = 25500                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 3: Filter Options (Premium ₹70-₹130)                                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   Available CE Options:                                                  │   │
│   │   ─────────────────────                                                  │   │
│   │   | Strike | Premium | Distance from ATM |                              │   │
│   │   |--------|---------|-------------------|                              │   │
│   │   | 25400  | ₹115.25 | -100 (ITM)        |                              │   │
│   │   | 25500  | ₹95.50  | 0 (ATM)           | ← SELECTED (Closest to ATM)  │   │
│   │   | 25600  | ₹82.75  | +100 (OTM)        |                              │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 4: Selection Priority                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Priority 1: ATM Strike CE (if premium in range)                       │   │
│   │   Priority 2: Nearest OTM CE (if ATM not in range)                      │   │
│   │   Priority 3: Nearest ITM CE (if no OTM in range)                       │   │
│   │                                                                          │   │
│   │   Selection = Option with premium closest to ₹100 (middle of range)     │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   OUTPUT: Selected Option                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   {                                                                      │   │
│   │     "tradingsymbol": "NIFTY26JAN25500CE",                               │   │
│   │     "instrument_token": 12345678,                                        │   │
│   │     "strike": 25500,                                                     │   │
│   │     "expiry": "2026-01-23",                                             │   │
│   │     "ltp": 95.50,                                                        │   │
│   │     "lot_size": 75                                                       │   │
│   │   }                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## CE Option Selection for Signal Monitoring

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                CE OPTION SELECTION FOR SIGNAL MONITORING                          │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   PURPOSE: Select CE option to monitor and validate buy/exit signals              │
│   LOGIC: All indicators and buy/exit validation based on selected CE option     │
│                                                                                   │
│   STEP 1: Use Selected CE Option                                                │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   ce_option = selected_ce_option  # Already selected by scanner        │   │
│   │   Example: "NIFTY26JAN25500CE"                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   STEP 2: Get CE Option Instrument Token                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   ce_tradingsymbol = selected_ce_option['tradingsymbol']               │   │
│   │   ce_instrument_token = selected_ce_option['instrument_token']          │   │
│   │   Example: Token 12345678 for "NIFTY26JAN25500CE"                      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   OUTPUT: CE Option for Signal Monitoring & Validation                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   {                                                                      │   │
│   │     "tradingsymbol": "NIFTY26JAN25500CE",                               │   │
│   │     "instrument_token": 12345678,                                        │   │
│   │     "strike": 25500,                                                     │   │
│   │     "expiry": "2026-01-23",                                             │   │
│   │     "ltp": 95.50,                                                        │   │
│   │     "purpose": "signal_monitoring_and_validation"                      │   │
│   │   }                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   USAGE:                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   • Fetch CE option OHLC data every 5 seconds                          │   │
│   │   • Calculate indicators (SuperTrend, EMA, RSI, MACD, StochRSI) on CE  │   │
│   │   • Validate buy conditions using CE Option price data                 │   │
│   │   • Validate exit conditions using CE Option price data                │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Double Confirmation Entry Logic (From ADR-001 - Using CE Option)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│              DOUBLE CONFIRMATION BUY SIGNAL (CE Option Based)                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   DIRECT VALIDATION LOGIC:                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │   • Monitor SELECTED CE OPTION (same expiry, ATM strike) OHLC data      │   │
│   │   • Calculate all indicators from CE Option price data                   │   │
│   │   • Validate buy conditions directly on CE Option price                 │   │
│   │   • CE Option bullish signals = CE BUY opportunity                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   5-MINUTE TIMEFRAME (Primary Signal) - CE OPTION DATA                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Check Every 10 Seconds on CE Option:                                  │   │
│   │   ────────────────────────────────────                                   │   │
│   │   ✓ SuperTrend (7,3) Direction = 1 (Bullish on CE)                     │   │
│   │   ✓ CE Close > SuperTrend Value (CE above SuperTrend)                   │   │
│   │   ✓ CE Close > EMA Low (8, offset 9) (CE above EMA)                      │   │
│   │   ✓ EMA 8 > EMA 9 (Bullish Crossover on CE)                             │   │
│   │   ✓ StochRSI < 50 OR Rising (Good momentum on CE)                       │   │
│   │   ✓ RSI < 65 AND Rising (Not overbought on CE)                          │   │
│   │   ✓ MACD Histogram > 0 OR Improving (Bullish on CE)                      │   │
│   │                                                                          │   │
│   │   PRIMARY_SIGNAL = All CE BULLISH conditions TRUE                        │   │
│   │                    (Validates CE BUY opportunity)                        │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   2-MINUTE TIMEFRAME (Confirmation Signal) - CE OPTION DATA                      │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   Check Every 5 Seconds on CE Option:                                   │   │
│   │   ───────────────────────────────────                                    │   │
│   │   ✓ SuperTrend (7,3) Direction = 1 (Bullish on CE)                     │   │
│   │   ✓ CE Close > SuperTrend Value (CE above SuperTrend)                   │   │
│   │   ✓ CE Close > EMA Low (8, offset 9) (CE above EMA)                      │   │
│   │   ✓ EMA 8 > EMA 9 (Bullish Crossover on CE)                             │   │
│   │   ✓ StochRSI < 50 OR Rising (Good momentum on CE)                       │   │
│   │   ✓ RSI < 65 AND Rising (Not overbought on CE)                          │   │
│   │   ✓ MACD Histogram > 0 OR Improving (Bullish on CE)                      │   │
│   │                                                                          │   │
│   │   CONFIRM_SIGNAL = All CE BULLISH conditions TRUE                       │   │
│   │                    (Confirms CE BUY opportunity)                         │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│   EXECUTE CE BUY (when CE Option shows BUY signals)                              │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   # CE BULLISH = CE BUY (Direct Validation)                             │   │
│   │   if PRIMARY_SIGNAL_CE_BULLISH AND CONFIRM_SIGNAL_CE_BULLISH:           │   │
│   │       # STEP 1: Refresh balance before buying CE                        │   │
│   │       current_balance = kite.margins()['equity']['available']           │   │
│   │       trading_capital = current_balance × 0.40                          │   │
│   │                                                                          │   │
│   │       # STEP 2: Recalculate quantity with fresh balance                 │   │
│   │       quantity = recalculate_quantity(trading_capital, ce_premium)      │   │
│   │                                                                          │   │
│   │       # STEP 3: Verify sufficient balance                               │   │
│   │       if quantity > 0:                                                  │   │
│   │           buy_option(                                                    │   │
│   │               tradingsymbol = selected_ce_option['tradingsymbol'],      │   │
│   │               quantity = quantity,                                       │   │
│   │               order_type = "MARKET"                                     │   │
│   │           )                                                              │   │
│   │       else:                                                              │   │
│   │           log("Insufficient balance - waiting 1 minute")                │   │
│   │           sleep(60)  # Wait 1 minute                                    │   │
│   │           GOTO STEP 1  # Re-scan options, wait for new signal           │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Exit Conditions (From ADR-001 - Using CE Option)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   EXIT (SELL CE) CONDITIONS - CE Option Based                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   MONITORED ON CE OPTION 2-MINUTE TIMEFRAME (Every 5 Seconds)                    │
│                                                                                   │
│   DIRECT VALIDATION: CE Option bearish signals → EXIT CE position                │
│                                                                                   │
│   EXIT TRIGGER 1: CE EMA LOW FALLING (CE Option Bearish)                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   # Monitor CE Option for BEARISH reversal                              │   │
│   │   ce_ema_low_falling = (                                                 │   │
│   │       current_ce['ema_low_8'] < previous_ce['ema_low_8'] AND            │   │
│   │       previous_ce['ema_low_8'] < prev2_ce['ema_low_8']                 │   │
│   │   )                                                                      │   │
│   │                                                                          │   │
│   │   ce_price_below_ema = ce_close < ce_ema_low_8                          │   │
│   │                                                                          │   │
│   │   EXIT CE if: ce_ema_low_falling AND ce_price_below_ema                 │   │
│   │   (CE Option showing weakness = Exit CE position)                        │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   EXIT TRIGGER 2: CE STRONG BEARISH SIGNAL (CE Option Bearish)                    │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   ce_strong_bearish = (                                                  │   │
│   │       ce_supertrend_direction == -1 AND   # Bearish SuperTrend on CE   │   │
│   │       ce_ema_8 < ce_ema_9 AND             # EMA Crossed Down on CE      │   │
│   │       ce_close < ce_ema_low_8             # CE Price Below EMA Low      │   │
│   │   )                                                                      │   │
│   │                                                                          │   │
│   │   EXIT CE if: ce_strong_bearish                                         │   │
│   │   (CE Option showing strong bearish = Exit CE position)                  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   EXIT TRIGGER 3: MACD BEARISH MOMENTUM (CE Option Bearish)                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   ce_macd_bearish = ce_macd < ce_macd_signal  # MACD below Signal line │   │
│   │                                                                          │   │
│   │   EXIT CE if: ce_macd_bearish                                           │   │
│   │   (CE Option MACD showing bearish momentum = Exit CE position)           │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   SELL CE ORDER EXECUTION                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │   if ce_exit_trigger_1 OR ce_exit_trigger_2 OR ce_exit_trigger_3:       │   │
│   │       sell_option(                                                       │   │
│   │           tradingsymbol = held_ce_option['tradingsymbol'],              │   │
│   │           quantity = position_quantity,                                  │   │
│   │           order_type = "MARKET"                                         │   │
│   │       )                                                                  │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Continuous Trading Mode

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         CONTINUOUS TRADING MODE                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   MARKET HOURS: 9:15 AM - 3:30 PM IST                                            │
│   ═══════════════════════════════════════════════════════════════════════════    │
│                                                                                   │
│   9:15 AM  9:25 AM  9:30 AM                                            3:30 PM   │
│      │        │        │                                                   │      │
│      │  WAIT  │ WATCH  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐         │      │
│      │  MODE  │ MODE   │  │Trade │ │Trade │ │Trade │ │Trade │  ...    │      │
│      │        │(monitor│  │  #1  │ │  #2  │ │  #3  │ │  #4  │         │      │
│      │        │  only) │  └──────┘ └──────┘ └──────┘ └──────┘         │      │
│      │        │        │                                                   │      │
│      ├────────┼────────┼───────────────────────────────────────────┬─────┤      │
│      │  WAIT  │ WATCH  │      ACTIVE TRADING ZONE                    │STOP │      │
│      │  MODE  │ MODE   │      (Trading enabled)                     │ZONE │      │
│      │        │(no     │                                             │15min│      │
│      │        │trade)  │                                             │     │      │
│      └────────┴────────┴─────────────────────────────────────────────┴─────┘      │
│                                                                                   │
│   TRADE CYCLE FLOW:                                                              │
│   ─────────────────                                                              │
│                                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                          │   │
│   │  START → [Scan Options] → [Wait for Double Confirmation]                │   │
│   │    ▲                                 │                                   │   │
│   │    │                                 ▼                                   │   │
│   │    │                     [CHECK BALANCE] → [Recalc Qty]                  │   │
│   │    │                           │                │                        │   │
│   │    │              Insufficient │                │ OK                     │   │
│   │    │                           ▼                ▼                        │   │
│   │    │                    [WAIT 1 MIN]      [BUY] ──▶ [Hold Position]     │   │
│   │    │                           │                                         │   │
│   │    └───────────────────────────┘                                         │   │
│   │            ▲                                      │                      │   │
│   │            │                                 EXIT │                      │   │
│   │            │                                      ▼                      │   │
│   │            │◄────── [Record P&L] ◄────── [Execute SELL]                 │   │
│   │            │                                                             │   │
│   │         REPEAT (if market still open)                                   │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│   SAFETY FEATURES:                                                               │
│   ────────────────                                                               │
│   • **Watch-only period (9:25-9:30 AM) - monitor market but NO trading**        │
│   • **Trading starts at 9:30 AM (not 9:15 AM)**                                 │
│   • No new trades initiated within 15 minutes of market close                   │
│   • Any open position is force-exited at market close (3:30 PM)                 │
│   • **Balance is checked immediately BEFORE each BUY order**                    │
│   • Quantity is recalculated with fresh balance before buying                   │
│   • **If insufficient balance → Wait 1 minute → Restart from Step 1**          │
│   • Options are re-scanned for each new trade (may select different strike)     │
│                                                                                   │
│   DAILY TRACKING:                                                                │
│   ───────────────                                                                │
│   • Each trade recorded with entry/exit prices, P&L, exit reason                │
│   • Running total P&L displayed throughout the day                              │
│   • Full daily summary displayed at end of trading session                      │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Execution Timeline

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE EXECUTION TIMELINE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  STARTUP PHASE                                                                   │
│  ─────────────                                                                   │
│  T+0s:   Authenticate with Kite Connect                                          │
│  T+1s:   Get Account Balance                                                     │
│  T+2s:   User Inputs Expiry Date                                                 │
│  T+3s:   Load NIFTY Options (NFO instruments)                                    │
│  T+4s:   Initial Scanner Run - Select CE Option                                  │
│  T+5s:   Calculate Quantity Based on Balance                                     │
│  T+6s:   Display Ready Status                                                    │
│                                                                                   │
│  MONITORING PHASE (No Position) - CE Option Based                                │
│  ──────────────────────────────────────────────────                              │
│  │                                                                               │
│  │  Second:  0    5    10   15   20   25   30   35   40   45   50   55         │
│  │           │    │    │    │    │    │    │    │    │    │    │    │          │
│  │  CE 5min: ✓         ✓         ✓         ✓         ✓         ✓              │
│  │  CE 2min: ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │  Scanner: ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │                                                                               │
│  │  Actions per 5-second cycle:                                                 │
│  │  • Refresh CE option premium via scanner                                     │
│  │  • Fetch CE Option historical data (5-min and 2-min OHLC)                   │
│  │  • Calculate indicators from CE Option price data                            │
│  │  • Check CE 2-min confirmation signal (CE BULLISH = CE BUY)                  │
│  │  • If 10s elapsed: Check CE 5-min primary signal (CE BULLISH = CE BUY)       │
│  │  • If BOTH CE BULLISH signals TRUE:                                          │
│  │      → CHECK BALANCE (fresh)                                                 │
│  │      → Recalculate CE quantity                                               │
│  │      → If sufficient funds: Execute CE BUY                                   │
│  │      → If insufficient: WAIT 1 MINUTE → RESTART FROM STEP 1                 │
│  │                                                                               │
│  HOLDING PHASE (CE Position Active) - CE Option Based                            │
│  ──────────────────────────────────────────────────────                          │
│  │                                                                               │
│  │  Second:  0    5    10   15   20   25   30   35   40   45   50   55         │
│  │           │    │    │    │    │    │    │    │    │    │    │    │          │
│  │  CE 2min: ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │  Exit:    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓    ✓         │
│  │                                                                               │
│  │  Actions per 5-second cycle:                                                 │
│  │  • Fetch CE Option 2-min historical data                                     │
│  │  • Calculate indicators from CE Option price data                            │
│  │  • Check CE EMA Low Falling condition (CE BEARISH = Exit CE)                 │
│  │  • Check CE Strong Bearish signal (CE BEARISH = Exit CE)                     │
│  │  • Check CE MACD Bearish (MACD < Signal = Exit CE)                           │
│  │  • If ANY CE EXIT condition TRUE: Execute CE SELL                            │
│  │                                                                               │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## State Machine (Continuous Trading)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    STATE MACHINE - CONTINUOUS TRADING MODE                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│                         ┌─────────────────────┐                                  │
│                         │    INITIALIZING     │                                  │
│                         │  • Accept Expiry    │                                  │
│                         │  • Load Options     │                                  │
│                         └──────────┬──────────┘                                  │
│                                    │                                             │
│  ┌─────────────────────────────────┼─────────────────────────────────────────┐  │
│  │                                 ▼                                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    TRADE CYCLE START                                 │  │  │
│  │  │  ─────────────────────────────────────────────────────────────────  │  │  │
│  │  │   1. Check Market Hours (9:15 AM - 3:30 PM IST)                     │  │  │
│  │  │   2. **Watch-only period (9:25-9:30 AM) - Monitor but don't trade** │  │  │
│  │  │   3. **Trading starts at 9:30 AM**                                  │  │  │
│  │  │   3. Refresh Account Balance                                         │  │  │
│  │  │   4. Scan & Select New CE Option                                    │  │  │
│  │  │   5. Calculate Quantity (40% of balance)                            │  │  │
│  │  └──────────────────────────────┬──────────────────────────────────────┘  │  │
│  │                                 │                                          │  │
│  │                                 ▼                                          │  │
│  │  ┌─────────────────────┐          ┌─────────────────────┐                 │  │
│  │  │    WAITING_CE_BUY   │          │   CE_POSITION_OPEN  │                 │  │
│  │  │  • Monitor CE 5-min │  CE BUY  │  • Monitor CE 2-min │                 │  │
│  │  │  • Monitor CE 2-min │─────────▶│  • Check CE Bearish │                 │  │
│  │  │  • Update Scanner   │  Signal  │  • Track CE P&L     │                 │  │
│  │  └─────────────────────┘(CE Bull) └──────────┬──────────┘                 │  │
│  │                                              │                             │  │
│  │                                        EXIT  │                             │  │
│  │                                       Signal │                             │  │
│  │                                              ▼                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    TRADE COMPLETED                                   │  │  │
│  │  │  ─────────────────────────────────────────────────────────────────  │  │  │
│  │  │   • Record Trade P&L                                                │  │  │
│  │  │   • Update Daily Summary                                            │  │  │
│  │  │   • Check: Market still open? (before 3:15 PM)                      │  │  │
│  │  │   • If YES → REPEAT (Go to TRADE CYCLE START)                       │  │  │
│  │  │   • If NO  → Exit to DAILY SUMMARY                                  │  │  │
│  │  └──────────────────────────────┬──────────────────────────────────────┘  │  │
│  │                                 │                                          │  │
│  │                    CONTINUOUS TRADING LOOP                                 │  │
│  │                 (Repeats until market closes)                              │  │
│  └─────────────────────────────────┼─────────────────────────────────────────┘  │
│                                    │                                             │
│                                    │ Market Close (3:30 PM) / Manual Stop        │
│                                    ▼                                             │
│                         ┌─────────────────────┐                                  │
│                         │   DAILY SUMMARY     │                                  │
│                         │  • Total Trades     │                                  │
│                         │  • Total P&L        │                                  │
│                         │  • Trade Details    │                                  │
│                         └─────────────────────┘                                  │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Display Output Format

```
════════════════════════════════════════════════════════════════════════════════════
  NIFTY CE AUTO TRADER - 2026-01-23 10:35:15
  MODE: CONTINUOUS TRADING | TRADE CYCLE #2
════════════════════════════════════════════════════════════════════════════════════

  MARKET STATUS
  ────────────────────────────────────────────────────────────────────────────────
  Market: OPEN | Time to Close: 295 minutes
  
  ACCOUNT STATUS
  ────────────────────────────────────────────────────────────────────────────────
  Available Balance: ₹50,000.00
  Trading Capital (40%): ₹20,000.00
  
  SELECTED OPTION (via ADR-003 Scanner)
  ────────────────────────────────────────────────────────────────────────────────
  Symbol: NIFTY26JAN25500CE
  Strike: 25500 (ATM)
  Expiry: 23-Jan-2026
  Current Premium: ₹95.50
  Lot Size: 75
  
  QUANTITY CALCULATION
  ────────────────────────────────────────────────────────────────────────────────
  Cost per Lot: ₹95.50 × 75 = ₹7,162.50
  Max Lots: floor(₹20,000 / ₹7,162.50) = 2 Lots
  Trading Quantity: 2 × 75 = 150
  Total Investment: ₹14,325.00

  DOUBLE CONFIRMATION STATUS (ADR-001 - CE Option Based)
  ────────────────────────────────────────────────────────────────────────────────
  NIFTY Spot: ₹25,480.50 (Reference only)
  
  ✓ Monitoring & Validating: CE Option NIFTY26JAN25500CE @ ₹95.50
  ⚠️  BUY validation based on CE Option price data (not NIFTY index)
  ⚠️  All indicators calculated from CE Option OHLC data
  
  | Indicator      | CE 5-MIN | CE 2-MIN | Status  |
  |----------------|----------|----------|---------|
  | SuperTrend     | BULLISH  | BULLISH  | ✓       |
  | Price > ST     | YES      | YES      | ✓       |
  | EMA Cross      | 8 > 9    | 8 > 9    | ✓       |
  | Price > EMA Lo | YES      | YES      | ✓       |
  | StochRSI       | 39.2     | 44.4     | ✓       |
  | RSI            | 50.1     | 48.2     | ✓       |
  | MACD Hist      | +0.22    | +1.68    | ✓       |
  
  PRIMARY SIGNAL (5-min CE BULLISH): ✓ → CE BUY
  CONFIRM SIGNAL (2-min CE BULLISH): ✓ → CE BUY
  
  ═══════════════════════════════════════════════════════════════════════════════
  >>> DOUBLE CONFIRMATION ACHIEVED - EXECUTING BUY ORDER <<<
  ═══════════════════════════════════════════════════════════════════════════════
  
  ORDER DETAILS
  ────────────────────────────────────────────────────────────────────────────────
  Order Type: MARKET BUY
  Symbol: NIFTY26JAN25500CE
  Quantity: 150
  Expected Cost: ₹14,325.00
  Order ID: 230123000012345

════════════════════════════════════════════════════════════════════════════════════
  Status: POSITION OPEN | Entry: ₹95.50 | Current: ₹97.25 | P&L: +₹262.50 (+1.83%)
════════════════════════════════════════════════════════════════════════════════════
```

### Daily Summary Output (End of Day)

```
════════════════════════════════════════════════════════════════════════════════════
  DAILY TRADING SUMMARY - 2026-01-23
════════════════════════════════════════════════════════════════════════════════════
  Total Trades: 4
  Total P&L: ₹3,250.00

  TRADE DETAILS:
  ──────────────────────────────────────────────────────────────────────────────────
  #1: NIFTY26JAN25500CE | Entry ₹95.50 → Exit ₹98.25 | P&L: +₹1,237.50 | ema_low_falling
  #2: NIFTY26JAN25400CE | Entry ₹112.00 → Exit ₹108.50 | P&L: -₹1,575.00 | strong_bearish
  #3: NIFTY26JAN25500CE | Entry ₹94.00 → Exit ₹99.00 | P&L: +₹2,250.00 | ema_low_falling
  #4: NIFTY26JAN25600CE | Entry ₹82.00 → Exit ₹85.00 | P&L: +₹1,337.50 | market_close
════════════════════════════════════════════════════════════════════════════════════
  Goodbye!
```

---

## Class Structure

```
IntegratedNiftyCETrader
├── __init__(kite_client, config)
│   ├── KiteClient for API access
│   ├── Account balance tracking
│   ├── Scanner configuration (from ADR-003)
│   ├── Strategy configuration (from ADR-001)
│   ├── Position state management
│   ├── Order tracking
│   └── Daily trade history tracking
│
├── INITIALIZATION METHODS
│   ├── get_account_balance()
│   │   └── Fetch available balance from kite.margins()
│   │
│   ├── get_expiry_date_input()
│   │   └── Accept and parse user expiry date input
│   │
│   └── display_trading_capacity()
│       └── Show balance and max lots available
│
├── MARKET HOURS METHODS (NEW)
│   ├── is_market_open()
│   │   └── Check if current time is within 9:15 AM - 3:30 PM IST
│   │
│   ├── get_time_to_market_close()
│   │   └── Return minutes remaining until market closes
│   │
│   ├── is_watch_only_period()
│   │   └── Check if within watch-only period (9:25-9:30 AM) - monitor but don't trade
│   ├── can_trade()
│   │   └── Check if trading is allowed (after 9:30 AM, before 3:15 PM)
│   │
│   └── should_stop_new_trades()
│       └── Check if < 15 minutes to market close
│
├── OPTIONS SCANNER METHODS (ADR-003)
│   ├── load_nifty_options(expiry_date)
│   │   └── Load all NIFTY options for given expiry
│   │
│   ├── filter_by_premium_range(options)
│   │   └── Filter options with premium ₹70-₹130
│   │
│   ├── get_nifty_spot_price()
│   │   └── Get current NIFTY index price
│   │
│   └── select_best_ce_option()
│       └── Select ATM or nearest suitable CE option
│
├── QUANTITY CALCULATOR
│   └── calculate_quantity(option_premium)
│       ├── Apply 40% risk factor to balance
│       ├── Calculate max lots affordable
│       └── Return quantity (lots × lot_size)
│
├── DOUBLE CONFIRMATION METHODS (ADR-001 - CE Option Based)
│   ├── get_historical_data(interval, use_ce_option=True)
│   │   └── Fetch CE OPTION OHLC data (not NIFTY index) for selected CE option
│   │
│   ├── calculate_indicators(df)
│   │   └── Calculate SuperTrend, EMA, RSI, MACD, StochRSI on CE Option data
│   │
│   ├── check_buy_conditions(df, timeframe)
│   │   └── Validate all BUY conditions using CE Option price data
│   │
│   └── check_exit_conditions(df_2min)
│       └── Validate EXIT conditions using CE Option price data
│
├── ORDER EXECUTION
│   ├── place_buy_order(symbol, quantity)
│   │   └── Execute market buy order
│   │
│   ├── place_sell_order(symbol, quantity, reason)
│   │   └── Execute market sell order
│   │
│   └── get_order_status(order_id)
│       └── Check order fill status
│
├── DISPLAY & LOGGING
│   ├── display_status()
│   │   └── Show current state, signals, position, trade cycle #
│   │
│   └── log_trade(trade_type, details)
│       └── Log trade to daily_trades list
│
└── MAIN EXECUTION (CONTINUOUS LOOP)
    └── run()
        ├── Initialize and get expiry date (once)
        │
        └── WHILE market is open:
            ├── Check market hours
            ├── Refresh account balance
            ├── Scan and select new CE option (for trading)
            ├── Calculate CE quantity
            ├── Fetch CE Option historical data (5-min and 2-min)
            ├── Calculate indicators from CE Option OHLC data
            ├── Wait for CE BULLISH signals (= CE BUY validated on CE Option)
            ├── Execute CE BUY
            ├── Monitor CE Option for BEARISH signals (= CE EXIT validated on CE Option)
            ├── Execute CE SELL
            ├── Record trade P&L to daily summary
            └── REPEAT (loop back to start)
            
        └── ON market close or manual stop:
            ├── Force exit any open position
            └── Display daily trading summary
```

---

## API Endpoints Used

| API Method | Purpose | Frequency |
|------------|---------|-----------|
| `kite.margins("equity")` | Get account balance | **Before each BUY order** |
| `kite.instruments("NFO")` | Load options chain | On startup |
| `kite.ltp(symbols)` | Get option premiums | Every 5 seconds |
| `kite.historical_data()` | Get CE Option OHLC | Every 5 seconds |
| `kite.place_order()` | Execute trades | On signal |
| `kite.order_history()` | Check order status | After order |
| `kite.positions()` | Verify positions | After order |

---

## Error Handling

| Error | Handling | Recovery |
|-------|----------|----------|
| Insufficient Balance | Alert user, reduce quantity | Wait for deposit |
| No Options in Range | Expand premium range | Use nearest option |
| API Rate Limit | Exponential backoff | Retry with delay |
| Order Rejected | Log reason, alert | Manual intervention |
| Network Timeout | Retry 3 times | Continue monitoring |
| Position Mismatch | Reconcile with API | Verify positions |

---

## Configuration File

```python
# config.py - Integrated Trader Configuration

TRADER_CONFIG = {
    # User Input
    "expiry_date": None,  # Set via user input
    
    # Options Scanner (ADR-003)
    "strike_min": 24000,
    "strike_max": 26000,
    "strike_multiple": 100,
    "premium_min": 70,
    "premium_max": 130,
    "scanner_refresh_seconds": 5,
    
    # Quantity Calculation
    "risk_factor": 0.40,  # Use 40% of balance
    "lot_size": 75,       # NIFTY lot size
    
    # Market Hours (IST)
    "market_open_hour": 9,
    "market_open_minute": 15,
    "market_close_hour": 15,
    "market_close_minute": 30,
    "watch_only_start_minute": 25,  # Watch-only period starts at 9:25 AM
    "trading_start_minute": 30,  # Trading starts at 9:30 AM
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
    "macd_fast": 5,
    "macd_slow": 13,
    "macd_signal": 6,
    
    # Trading
    "exchange": "NFO",
    "product_type": "MIS",  # Intraday
    "order_type": "MARKET",
    
    # Continuous Trading
    "continuous_mode": True,  # Repeat trades until market close
}
```

---

## Usage

### Interactive Mode
```bash
python integrated_nifty_ce_trader.py
```

### Programmatic Mode
```python
from integrated_nifty_ce_trader import IntegratedNiftyCETrader

# Initialize trader
trader = IntegratedNiftyCETrader()

# Run with expiry date
trader.run(expiry_date="Jan 23")

# Or with explicit configuration
config = {
    "expiry_date": "Jan 23",
    "risk_factor": 0.50,  # Use 50% of balance
    "premium_min": 70,
    "premium_max": 130
}
trader.run_with_config(config)
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pandas | Latest | Data manipulation |
| numpy | Latest | Numerical calculations |
| kiteconnect | Latest | Zerodha API integration |
| python-dotenv | Latest | Environment variables |
| tabulate | Latest | Pretty table output |

---

## Related Documents

- `ADR-001-NIFTY-DOUBLE-CONFIRMATION-OPTION-CE-BUY-STRATEGY BUY.md` - Original double confirmation strategy (NIFTY Index based)
- `ADR-002-NIFTY-DOUBLE-CONFIRMATION-OPTION-PE-SELL-STRATEGY.md` - PE-based double confirmation strategy (used for signals)
- `ADR-003-NIFTY-OPTIONS-SCANNER.md` - Options scanner strategy
- `integrated_nifty_ce_trader.py` - Main implementation
- `kite_client.py` - Kite API wrapper

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Team | Initial Integrated ADR combining ADR-001 and ADR-003 |
| 1.1 | Jan 2026 | Team | Updated risk factor 80% → 90%, Added continuous trading loop until market close, Added market hours checking (9:15 AM - 3:30 PM IST), Added daily P&L tracking across multiple trades, Added safety features (stop new trades 15 min before close, force exit at close) |
| 1.2 | Jan 2026 | Team | Balance check moved to immediately BEFORE each BUY order, Quantity recalculated with fresh balance before buying, If insufficient balance → wait 1 minute → restart from Step 1 (re-scan options, wait for new signal) |
| 1.3 | Jan 2026 | Team | Added Opening 15-minute Filter: Skip trading during 9:15-9:30 AM (volatile opening period with gaps, fake breakouts, unstable indicators). First trade allowed only after 9:30 AM. |
| 1.4 | Jan 2026 | Team | Reduced Capital Utilization: Risk factor changed from 90% → 40% for safer position sizing and better risk management. |
| 1.5 | Jan 2026 | Team | **CE Option-Based Signals**: Changed PHASE 4 Double Confirmation from NIFTY Index to Selected CE Option data (ADR-001). Entry: CE BULLISH signals = CE BUY validated. Exit: CE BEARISH signals = CE EXIT validated. All indicators and buy/exit validation based on CE Option price data for accurate signals. |
| 1.6 | Feb 2026 | Team | **Added Exit Trigger 3: MACD Bearish Momentum**: Added new exit condition - MACD < Signal line triggers exit. This provides earlier exit when momentum shifts bearish, before EMA Low falling or Strong Bearish conditions are met. |
