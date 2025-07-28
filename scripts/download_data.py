#!/usr/bin/env python3
"""
Import stock and options data using yfinance and save to CSV
"""

import os
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime
from config import SYMBOL, DATA_PERIOD, VOLATILITY_WINDOW, TARGET_EXPIRY_DAYS

def get_stock_data(symbol, period="1y"):
    """Get stock data from yfinance"""
    ticker = yf.Ticker(symbol)
    return ticker.history(period=period)

def get_options_chain(symbol, max_expirations=5):
    """Get options chain from yfinance with filtering"""
    ticker = yf.Ticker(symbol)
    
    try:
        exp_dates = ticker.options
        if not exp_dates:
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
        
        all_calls = []
        all_puts = []
        today = datetime.now()
        
        for exp_date in exp_dates[:max_expirations]:
            chain = ticker.option_chain(exp_date)
            
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            
            # Add derived fields
            exp_datetime = pd.to_datetime(exp_date)
            days_to_expiry = (exp_datetime - today).days
            
            calls['expiration'] = exp_date
            puts['expiration'] = exp_date
            calls['days_to_expiry'] = days_to_expiry
            puts['days_to_expiry'] = days_to_expiry
            calls['time_to_expiry'] = days_to_expiry / 365.25
            puts['time_to_expiry'] = days_to_expiry / 365.25
            calls['mid_price'] = (calls['bid'] + calls['ask']) / 2
            puts['mid_price'] = (puts['bid'] + puts['ask']) / 2
            
            # Filter liquid options
            calls = calls[
                (calls['volume'] > 0) & 
                (calls['openInterest'] > 0) &
                (calls['bid'] > 0) & 
                (calls['ask'] > 0)
            ]
            puts = puts[
                (puts['volume'] > 0) & 
                (puts['openInterest'] > 0) &
                (puts['bid'] > 0) & 
                (puts['ask'] > 0)
            ]
            
            all_calls.append(calls)
            all_puts.append(puts)
        
        result_calls = pd.concat(all_calls, ignore_index=True) if all_calls else pd.DataFrame()
        result_puts = pd.concat(all_puts, ignore_index=True) if all_puts else pd.DataFrame()
        
        return {'calls': result_calls, 'puts': result_puts}
    
    except Exception as e:
        print(f"Options data error: {e}")
        return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

def calculate_volatility(price_series, window=252):
    """Calculate annualized volatility"""
    returns = price_series.pct_change().dropna()
    return returns.std() * np.sqrt(window)

def get_risk_free_rate():
    """Get 3-month Treasury rate"""
    try:
        treasury = yf.Ticker("^IRX")
        hist = treasury.history(period="5d")
        if not hist.empty:
            return hist['Close'][-1] / 100
    except:
        pass
    return 0.0525

def get_current_price(symbol):
    """Get current stock price"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if 'currentPrice' in info:
            return info['currentPrice']
        elif 'regularMarketPrice' in info:
            return info['regularMarketPrice']
    except:
        pass
    
    try:
        df = get_stock_data(symbol, period="5d")
        return df['Close'].iloc[-1]
    except:
        return None

def filter_target_expiry(options_df, target_days=TARGET_EXPIRY_DAYS, tolerance=15):
    """Filter options near target expiry"""
    if options_df.empty:
        return options_df
    
    return options_df[
        (options_df['days_to_expiry'] >= target_days - tolerance) &
        (options_df['days_to_expiry'] <= target_days + tolerance)
    ]

def main():
    print(f"Downloading data for {SYMBOL}...")
    
    # Get stock data
    stock_data = get_stock_data(SYMBOL, DATA_PERIOD)
    current_price = get_current_price(SYMBOL)
    volatility = calculate_volatility(stock_data['Close'], VOLATILITY_WINDOW)
    risk_free_rate = get_risk_free_rate()
    
    # Get options data
    options = get_options_chain(SYMBOL)
    
    # Filter options for target expiry
    calls_filtered = filter_target_expiry(options['calls'])
    puts_filtered = filter_target_expiry(options['puts'])
    
    # Save data
    os.makedirs('data', exist_ok=True)
    
    # Stock data
    stock_file = f"data/{SYMBOL}_stock.csv"
    stock_data.to_csv(stock_file)
    print(f"Stock data saved: {stock_file}")
    
    # Options data
    if not calls_filtered.empty:
        calls_file = f"data/{SYMBOL}_calls.csv"
        calls_filtered.to_csv(calls_file, index=False)
        print(f"Calls saved: {calls_file} ({len(calls_filtered)} options)")
    
    if not puts_filtered.empty:
        puts_file = f"data/{SYMBOL}_puts.csv"
        puts_filtered.to_csv(puts_file, index=False)
        print(f"Puts saved: {puts_file} ({len(puts_filtered)} options)")
    
    # Summary
    summary = {
        'symbol': SYMBOL,
        'current_price': current_price,
        'historical_volatility': volatility,
        'risk_free_rate': risk_free_rate,
        'stock_data_points': len(stock_data),
        'calls_count': len(calls_filtered),
        'puts_count': len(puts_filtered),
        'download_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    summary_file = f"data/{SYMBOL}_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nSummary:")
    print(f"Current Price: ${current_price:.2f}")
    print(f"Volatility: {volatility:.1%}")
    print(f"Risk-Free Rate: {risk_free_rate:.3%}")
    print(f"Target Options: {len(calls_filtered)} calls, {len(puts_filtered)} puts")

if __name__ == "__main__":
    main()