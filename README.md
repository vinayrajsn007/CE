# NIFTY CE Auto Trader

Automated NIFTY CE Options trading system using Zerodha Kite Connect API with Double Confirmation Strategy.

## Features

- **Double Confirmation Strategy**: Uses 5-minute and 2-minute timeframes for entry signals
- **Options Scanner**: Automatically selects CE options in premium range ₹70-₹130
- **Technical Indicators**: SuperTrend, EMA, RSI, MACD, StochRSI
- **Continuous Trading**: Multiple trades throughout the trading day
- **Risk Management**: Position sizing based on account balance (40% utilization)
- **Market Hours**: Operates 9:30 AM - 3:30 PM IST

## Prerequisites

1. **Zerodha Account**: Active Zerodha trading account
2. **Kite Connect App**: Create an app at https://kite.trade/apps/
3. **Python 3.10+**: Required for running the scripts

## Quick Start

```bash
# 1. Create virtual environment and install dependencies
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 2. Set up API credentials (first time only)
python3 -m api.auth_helper

# 3. Run the trader
source venv/bin/activate && python3 integrated_nifty_ce_trader.py
```

## Installation

1. **Clone or download this repository**

2. **Create virtual environment and install dependencies**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up API credentials**:
   - Copy `.env.example` to `.env`
   - Add your credentials:
```
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
```

## Project Structure

```
CE/
├── integrated_nifty_ce_trader.py  # Main entry point
├── trading/
│   └── trader.py                  # Core trading logic (IntegratedNiftyCETrader)
├── scanner/
│   ├── options_scanner.py         # NIFTY options scanner
│   └── option_chain.py            # Option chain utilities
├── indicators/
│   └── technical_indicators.py    # SuperTrend, EMA, RSI, MACD, StochRSI
├── api/
│   ├── kite_client.py             # Kite Connect API wrapper
│   └── auth_helper.py             # Authentication helper
├── backtest/
│   └── backtest_engine.py         # Backtesting framework
├── utils/
│   ├── config.py                  # Configuration settings
│   ├── logging_config.py          # Logging setup
│   └── historical_fetcher.py      # Historical data fetcher
├── docs/
│   ├── ADR-001-*.md               # Double Confirmation Strategy
│   └── ADR-004-*.md               # Integrated Auto Trader
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment template
```

## Authentication

### First Time Setup

Run the authentication helper:
```bash
python -m api.auth_helper
# Or use the entry point:
python fetch_historical_options.py  # (if it includes auth)
```

This will:
1. Ask for your API Key and Secret
2. Open a browser for login
3. Generate an access token
4. Optionally save it to `.env` file

### Manual Authentication

1. Get your API Key and Secret from https://kite.trade/apps/
2. Use `generate_login_url()` to get login URL
3. Login and get the `request_token` from redirect URL
4. Use `generate_session(request_token)` to get access token

## Usage

### Basic Trading

```python
from kite_client import KiteTradingClient
from automated_trading import AutomatedTrader

# Initialize client
kite = KiteTradingClient()

# Initialize trader
trader = AutomatedTrader(kite)

# Get current price
price = trader.get_current_price("NSE", "RELIANCE")

# Place market order
order_id = trader.place_market_order(
    exchange="NSE",
    symbol="RELIANCE",
    transaction_type="BUY",
    quantity=1,
    product="MIS"
)

# Place limit order
order_id = trader.place_limit_order(
    exchange="NSE",
    symbol="RELIANCE",
    transaction_type="BUY",
    quantity=1,
    price=2500,
    product="MIS"
)

# Place bracket order (with stop loss and target)
order_id = trader.place_bracket_order(
    exchange="NSE",
    symbol="RELIANCE",
    transaction_type="BUY",
    quantity=1,
    price=2500,
    stoploss=2450,
    target=2600,
    product="MIS"
)
```

### Order Management

```python
# Get all orders
orders = kite.get_orders()

# Get order history
history = kite.get_order_history(order_id)

# Modify order
kite.modify_order(order_id, price=2550, quantity=2)

# Cancel order
kite.cancel_order(order_id)
```

### Position Management

```python
# Get positions
positions = kite.get_positions()

# Get holdings
holdings = kite.get_holdings()

# Square off all positions
trader.square_off_all_positions(product="MIS")
```

### Market Data

```python
# Get quote
quote = kite.get_quote(["NSE:RELIANCE"])

# Get LTP
ltp = kite.get_ltp(["NSE:RELIANCE"])

# Get OHLC
ohlc = kite.get_ohlc(["NSE:RELIANCE"])

# Get historical data
from datetime import datetime, timedelta
historical = kite.get_historical_data(
    instrument_token=738561,
    from_date=datetime.now() - timedelta(days=30),
    to_date=datetime.now(),
    interval="day"
)
```

### Running the NIFTY CE Auto Trader

```bash
# Activate virtual environment
source venv/bin/activate

# Run the integrated trader
python integrated_nifty_ce_trader.py
```

The trader will:
1. Authenticate with Kite Connect
2. Ask for expiry date input
3. Scan for CE options in premium range ₹70-₹130
4. Wait for double confirmation signals (5-min + 2-min)
5. Execute trades automatically
6. Monitor for exit conditions
7. Continue trading until market close

## Exit Conditions

The trader exits positions when any of these conditions are met:

| Trigger | Condition |
|---------|-----------|
| EMA Low Falling | EMA Low falling 2+ candles AND Price < EMA Low |
| Strong Bearish | SuperTrend Red AND EMA 8 < EMA 9 AND Price < EMA Low |
| MACD Bearish | MACD < Signal Line |
| Market Close | 3:30 PM IST |

## Important Notes

⚠️ **Risk Warning**: 
- Trading involves financial risk
- Always test with paper trading or small amounts first
- Use proper risk management
- Set stop losses for all positions
- Never risk more than you can afford to lose

⚠️ **API Limits**:
- Kite Connect has rate limits
- Don't make excessive API calls
- Use WebSocket for real-time data when possible

⚠️ **Security**:
- Never commit `.env` file to version control
- Keep your API credentials secure
- Access tokens expire - you may need to regenerate them

## Order Types

- **MARKET**: Execute immediately at market price
- **LIMIT**: Execute at specified price or better
- **SL**: Stop Loss order
- **SL-M**: Stop Loss Market order

## Product Types

- **MIS**: Margin Intraday Square-off (Intraday)
- **CNC**: Cash and Carry (Delivery)
- **NRML**: Normal (Carry Forward)

## Order Varieties

- **regular**: Regular order
- **bo**: Bracket Order (with stop loss and target)
- **co**: Cover Order (with stop loss)
- **amo**: After Market Order

## Example Strategies

The `automated_trading.py` includes example strategy templates:
- Momentum scanner
- Mean reversion
- Position monitoring and exit

Customize these according to your trading strategy.

## Support

- Kite Connect Documentation: https://kite.trade/docs/connect/v4/
- Zerodha Support: https://support.zerodha.com/

## License

This is a sample implementation. Use at your own risk.

# 1. Create virtual environment and install dependencies
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 2. Copy .env.example to .env and add your API credentials
cp .env.example .env
# Edit .env with your Kite Connect credentials

# 3. Authenticate (first time only)
python3 -m api.auth_helper

# 4. Run the trader
python3 integrated_nifty_ce_trader.py
