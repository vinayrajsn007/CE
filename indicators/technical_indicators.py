"""
Technical Indicators Module
Your exact indicator settings:
- SuperTrend (7, 3)
- Moving Average (Period 8, Field: Low, Type: EMA, Offset 9)
- EMA (8, 9) Crossover
- StochasticRSI
- RSI (14)
- MACD (5, 13, 6)
"""

import numpy as np
import pandas as pd


def ema(data, period):
    """
    Exponential Moving Average
    
    Args:
        data: Price data (list or array)
        period: EMA period
    
    Returns:
        EMA values
    """
    return pd.Series(data).ewm(span=period, adjust=False).mean().values


def sma(data, period):
    """Simple Moving Average"""
    return pd.Series(data).rolling(window=period).mean().values


def atr(high, low, close, period=14):
    """
    Average True Range
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
    
    Returns:
        ATR values
    """
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_values = true_range.ewm(span=period, adjust=False).mean()
    
    return atr_values.values


def supertrend(high, low, close, period=7, multiplier=3):
    """
    SuperTrend Indicator (7, 3)
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period (default 7)
        multiplier: ATR multiplier (default 3)
    
    Returns:
        tuple: (supertrend_values, trend_direction)
        trend_direction: 1 for bullish (green), -1 for bearish (red)
    """
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    
    # Calculate ATR
    atr_values = pd.Series(atr(high, low, close, period))
    
    # Calculate basic upper and lower bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr_values)
    basic_lower = hl2 - (multiplier * atr_values)
    
    # Initialize
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend_arr = pd.Series(index=close.index, dtype=float)
    trend = pd.Series(index=close.index, dtype=int)
    
    for i in range(1, len(close)):
        # Final Upper Band
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
        
        # Final Lower Band
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
    
    # Determine trend
    for i in range(1, len(close)):
        if i == 1:
            trend.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        else:
            if trend.iloc[i-1] == -1 and close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1
            elif trend.iloc[i-1] == 1 and close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]
        
        # Set SuperTrend value
        if trend.iloc[i] == 1:
            supertrend_arr.iloc[i] = final_lower.iloc[i]
        else:
            supertrend_arr.iloc[i] = final_upper.iloc[i]
    
    return supertrend_arr.values, trend.values


def ema_on_low(low_prices, period=8, offset=9):
    """
    Moving Average on Low prices with offset
    Period 8, Field: Low, Type: EMA, Offset 9
    
    Args:
        low_prices: Low price data
        period: EMA period (8)
        offset: Offset value (9)
    
    Returns:
        EMA values with offset applied
    """
    ema_values = pd.Series(low_prices).ewm(span=period, adjust=False).mean()
    # Apply offset (shift the EMA line by offset periods)
    ema_offset = ema_values.shift(offset)
    return ema_values.values, ema_offset.values


def rsi(data, period=14):
    """
    Relative Strength Index
    
    Args:
        data: Price data
        period: RSI period (default 14)
    
    Returns:
        RSI values (0-100)
    """
    delta = pd.Series(data).diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).values


def stochastic_rsi(data, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    """
    Stochastic RSI
    
    Args:
        data: Price data
        rsi_period: RSI calculation period
        stoch_period: Stochastic calculation period
        smooth_k: %K smoothing period
        smooth_d: %D smoothing period
    
    Returns:
        tuple: (stoch_k, stoch_d) values (0-100)
    """
    rsi_values = pd.Series(rsi(data, rsi_period))
    
    # Stochastic calculation on RSI
    lowest_rsi = rsi_values.rolling(window=stoch_period).min()
    highest_rsi = rsi_values.rolling(window=stoch_period).max()
    
    stoch_rsi = ((rsi_values - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100
    
    # Smooth K and D
    k = stoch_rsi.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    
    return k.values, d.values


def macd(data, fast=5, slow=13, signal=6):
    """
    MACD (Moving Average Convergence Divergence)
    Using your settings: (5, 13, 6)
    
    Args:
        data: Price data
        fast: Fast EMA period (default 5)
        slow: Slow EMA period (default 13)
        signal: Signal line period (default 6)
    
    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    prices = pd.Series(data)
    
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line.values, signal_line.values, histogram.values


def calculate_all_indicators(df):
    """
    Calculate all indicators matching your chart
    
    Args:
        df: DataFrame with OHLC data (columns: open, high, low, close)
    
    Returns:
        DataFrame with all indicators added
    """
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # SuperTrend (7, 3)
    df['supertrend'], df['supertrend_direction'] = supertrend(high, low, close, period=7, multiplier=3)
    
    # EMA on Low (Period 8, Offset 9)
    df['ema_low_8'], df['ema_low_8_offset9'] = ema_on_low(low, period=8, offset=9)
    
    # EMA 8 and 9 on Close
    df['ema_8'] = ema(close, 8)
    df['ema_9'] = ema(close, 9)
    
    # RSI 14
    df['rsi_14'] = rsi(close, 14)
    
    # Stochastic RSI
    df['stoch_rsi_k'], df['stoch_rsi_d'] = stochastic_rsi(close)
    
    # MACD (5, 13, 6)
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(close, 5, 13, 6)
    
    return df


def get_signal(df):
    """
    Generate trading signal based on all indicators
    
    Returns:
        'BUY', 'SELL', or 'HOLD'
    """
    if len(df) < 3:
        return 'HOLD', {}
    
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    signals = {}
    
    # 1. SuperTrend Signal
    signals['supertrend'] = 'BUY' if current['supertrend_direction'] == 1 else 'SELL'
    signals['supertrend_crossover'] = (
        current['supertrend_direction'] != prev['supertrend_direction']
    )
    
    # 2. EMA on Low crossover with price
    signals['ema_low_cross'] = 'BUY' if current['close'] > current['ema_low_8'] else 'SELL'
    
    # 3. EMA 8/9 Crossover
    signals['ema_crossover'] = 'BUY' if current['ema_8'] > current['ema_9'] else 'SELL'
    ema_just_crossed = (
        (current['ema_8'] > current['ema_9'] and prev['ema_8'] <= prev['ema_9']) or
        (current['ema_8'] < current['ema_9'] and prev['ema_8'] >= prev['ema_9'])
    )
    signals['ema_just_crossed'] = ema_just_crossed
    
    # 4. RSI
    signals['rsi'] = current['rsi_14']
    signals['rsi_signal'] = 'BUY' if current['rsi_14'] < 50 else 'SELL'
    
    # 5. StochasticRSI
    signals['stoch_rsi'] = current['stoch_rsi_k']
    signals['stoch_rsi_signal'] = 'BUY' if current['stoch_rsi_k'] < 40 else ('SELL' if current['stoch_rsi_k'] > 60 else 'HOLD')
    
    # 6. MACD
    signals['macd_hist'] = current['macd_hist']
    signals['macd_signal'] = 'BUY' if current['macd_hist'] > 0 else 'SELL'
    
    # Combined Signal Logic
    buy_count = sum([
        signals['supertrend'] == 'BUY',
        signals['ema_crossover'] == 'BUY',
        signals['stoch_rsi_signal'] == 'BUY',
        signals['macd_signal'] == 'BUY'
    ])
    
    sell_count = sum([
        signals['supertrend'] == 'SELL',
        signals['ema_crossover'] == 'SELL',
        signals['stoch_rsi_signal'] == 'SELL',
        signals['macd_signal'] == 'SELL'
    ])
    
    # Generate final signal
    if buy_count >= 3 and signals['supertrend'] == 'BUY':
        return 'BUY', signals
    elif sell_count >= 3 and signals['supertrend'] == 'SELL':
        return 'SELL', signals
    else:
        return 'HOLD', signals


def print_indicator_status(df):
    """Print current indicator values"""
    if len(df) < 2:
        return
    
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    print("\n" + "=" * 60)
    print("INDICATOR STATUS")
    print("=" * 60)
    
    # SuperTrend
    st_trend = "BULLISH (Green)" if current['supertrend_direction'] == 1 else "BEARISH (Red)"
    print(f"SuperTrend (7,3): {current['supertrend']:.2f} | Trend: {st_trend}")
    
    # EMA on Low
    print(f"EMA Low (8): {current['ema_low_8']:.2f}")
    
    print("-" * 60)
    
    # EMA Crossover
    print(f"EMA 8: {current['ema_8']:.2f}")
    print(f"EMA 9: {current['ema_9']:.2f}")
    ema_trend = "BULLISH" if current['ema_8'] > current['ema_9'] else "BEARISH"
    print(f"EMA Trend: {ema_trend}")
    
    print("-" * 60)
    
    # RSI
    print(f"RSI (14): {current['rsi_14']:.2f}")
    rsi_zone = "OVERSOLD" if current['rsi_14'] < 30 else "OVERBOUGHT" if current['rsi_14'] > 70 else "NEUTRAL"
    print(f"RSI Zone: {rsi_zone}")
    
    print("-" * 60)
    
    # StochasticRSI
    print(f"StochasticRSI K: {current['stoch_rsi_k']:.2f}")
    print(f"StochasticRSI D: {current['stoch_rsi_d']:.2f}")
    stoch_zone = "OVERSOLD" if current['stoch_rsi_k'] < 20 else "OVERBOUGHT" if current['stoch_rsi_k'] > 80 else "NEUTRAL"
    print(f"StochRSI Zone: {stoch_zone}")
    
    print("-" * 60)
    
    # MACD
    print(f"MACD (5,13,6): {current['macd']:.2f}")
    print(f"MACD Signal: {current['macd_signal']:.2f}")
    print(f"MACD Histogram: {current['macd_hist']:.2f}")
    macd_trend = "BULLISH" if current['macd_hist'] > 0 else "BEARISH"
    print(f"MACD Trend: {macd_trend}")
    
    print("=" * 60)
    
    signal, details = get_signal(df)
    print(f"\n>>> OVERALL SIGNAL: {signal} <<<\n")
