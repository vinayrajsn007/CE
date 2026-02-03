"""
Fetch NIFTY Options Historical Data using Kite API
Uses direct API call with proper authentication
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv('KITE_API_KEY')
ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')

# NIFTY CE Options for 20th Jan 2026, Strike 25500-26000
OPTIONS = {
    # CE Options Only
    'NIFTY2612025500CE': 12185346,
    'NIFTY2612025550CE': 12185858,
    'NIFTY2612025600CE': 12186370,
    'NIFTY2612025650CE': 12188418,
    'NIFTY2612025700CE': 12188930,
    'NIFTY2612025750CE': 12189442,
    'NIFTY2612025800CE': 12189954,
    'NIFTY2612025850CE': 12190466,
    'NIFTY2612025900CE': 12190978,
    'NIFTY2612025950CE': 12191490,
    'NIFTY2612026000CE': 12192002,
}


def fetch_historical_data(instrument_token, symbol, from_date, to_date, interval="day"):
    """
    Fetch historical data using direct API call
    """
    url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
    
    params = {
        'from': from_date,
        'to': to_date,
        'oi': 1  # Include Open Interest
    }
    
    headers = {
        'X-Kite-Version': '3',
        'Authorization': f'token {API_KEY}:{ACCESS_TOKEN}'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('candles', [])
        else:
            print(f"Error for {symbol}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Exception for {symbol}: {e}")
        return None


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════════════════════╗
║     NIFTY CE OPTIONS HISTORICAL DATA - 16th January 2026                          ║
║     Strike Range: 25500 - 26000 | CE Options Only                                 ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    if not API_KEY or not ACCESS_TOKEN:
        print("❌ API_KEY or ACCESS_TOKEN not found in .env file")
        return
    
    print(f"API Key: {API_KEY[:8]}...")
    print(f"Access Token: {ACCESS_TOKEN[:8]}...")
    
    # Date range - 16th January 2026
    from_date = "2026-01-16 09:15:00"
    to_date = "2026-01-16 15:30:00"
    
    print(f"\n📅 Fetching data for: {from_date[:10]}")
    print("-" * 80)
    
    results = {}
    
    for symbol, token in OPTIONS.items():
        print(f"Fetching {symbol}...", end=" ")
        
        candles = fetch_historical_data(token, symbol, from_date, to_date, "day")
        
        if candles and len(candles) > 0:
            # Candle format: [timestamp, open, high, low, close, volume, oi]
            candle = candles[-1]
            results[symbol] = {
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
                'oi': candle[6] if len(candle) > 6 else 0
            }
            print(f"✓ Close: ₹{candle[4]:.2f}")
        else:
            print("✗ No data")
    
    # Display results - CE Options Only
    if results:
        print("\n" + "=" * 100)
        print(f"  NIFTY CE OPTION CHAIN - 16th January 2026 (Historical)")
        print("=" * 100)
        print(f"{'Strike':<8} {'CE Symbol':<22} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<12} {'OI':<15}")
        print("-" * 100)
        
        # Sort by strike price
        sorted_results = sorted(results.items(), key=lambda x: int(x[0].replace('NIFTY26120', '').replace('CE', '')))
        
        for symbol, data in sorted_results:
            strike = symbol.replace('NIFTY26120', '').replace('CE', '')
            ce_open = f"₹{data.get('open', 0):.2f}" if data.get('open') else "-"
            ce_high = f"₹{data.get('high', 0):.2f}" if data.get('high') else "-"
            ce_low = f"₹{data.get('low', 0):.2f}" if data.get('low') else "-"
            ce_close = f"₹{data.get('close', 0):.2f}" if data.get('close') else "-"
            volume = f"{data.get('volume', 0):,}" if data.get('volume') else "0"
            oi = f"{data.get('oi', 0):,}" if data.get('oi') else "0"
            
            print(f"{strike:<8} {symbol:<22} {ce_open:<10} {ce_high:<10} {ce_low:<10} {ce_close:<10} {volume:<12} {oi:<15}")
        
        print("=" * 100)
        print(f"\n✅ Successfully fetched {len(results)} CE option prices")
    else:
        print("\n⚠️  No historical data retrieved. Check API permissions.")


if __name__ == "__main__":
    main()
