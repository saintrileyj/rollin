from __future__ import annotations

import pandas as pd
import yfinance as yf


def get_history(symbol: str, days: int) -> pd.DataFrame:
    period = f"{max(days, 5)}d"
    df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"no price history returned for {symbol}")
    df.index = pd.to_datetime(df.index)
    return df


def get_last_price(symbol: str) -> float:
    df = yf.Ticker(symbol).history(period="1d", interval="1m", auto_adjust=True)
    if df.empty:
        df = get_history(symbol, 5)
    return float(df["Close"].iloc[-1])
