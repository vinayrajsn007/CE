# Zerodha Kite API Trading Automation

Automated trading system using Zerodha Kite Connect API.

## Prerequisites

1. **Zerodha Account**: You need an active Zerodha trading account
2. **Kite Connect App**: Create an app at https://kite.trade/apps/ to get API credentials
3. **Python 3.7+**: Required for running the scripts

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up API credentials**:
   - Create a `.env` file in the project root
   - Add your credentials:
```
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
```

## Project Structure

The codebase is organized into domain-based modules:

```
CE/
├── trading/          # Core trading modules (trader)
├── scanner/          # Options scanning (scanner, option chain)
├── indicators/       # Technical indicators
├── api/              # Kite API wrappers (client, auth)
├── backtest/         # Backtesting engine
├── utils/            # Utilities (config, historical fetcher)
└── docs/             # Documentation (ADR files)
```

Entry point scripts remain in the root directory for easy execution.

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

### Running Automated Trading

```bash
python automated_trading.py
```

## File Structure

- `kite_client.py`: Core Kite Connect API wrapper
- `automated_trading.py`: Trading automation and strategies
- `auth_helper.py`: Authentication helper script
- `config.py`: Configuration settings
- `requirements.txt`: Python dependencies

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
