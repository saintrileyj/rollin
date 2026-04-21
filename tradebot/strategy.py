from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

Side = Literal["buy", "sell", "hold"]


@dataclass
class Signal:
    symbol: str
    side: Side
    price: float
    reason: str


class SmaCrossover:
    """Classic two-SMA crossover: buy when fast crosses above slow, sell when it crosses below."""

    def __init__(self, fast: int = 10, slow: int = 30):
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self.fast = fast
        self.slow = slow

    def evaluate(self, symbol: str, history: pd.DataFrame) -> Signal:
        closes = history["Close"]
        if len(closes) < self.slow + 2:
            return Signal(symbol, "hold", float(closes.iloc[-1]), "not enough bars")

        fast_now = closes.rolling(self.fast).mean().iloc[-1]
        fast_prev = closes.rolling(self.fast).mean().iloc[-2]
        slow_now = closes.rolling(self.slow).mean().iloc[-1]
        slow_prev = closes.rolling(self.slow).mean().iloc[-2]
        price = float(closes.iloc[-1])

        if fast_prev <= slow_prev and fast_now > slow_now:
            return Signal(symbol, "buy", price, f"SMA{self.fast} crossed above SMA{self.slow}")
        if fast_prev >= slow_prev and fast_now < slow_now:
            return Signal(symbol, "sell", price, f"SMA{self.fast} crossed below SMA{self.slow}")
        return Signal(symbol, "hold", price, "no crossover")


def build(name: str, params: dict):
    if name == "sma_crossover":
        return SmaCrossover(fast=params.get("fast", 10), slow=params.get("slow", 30))
    raise ValueError(f"unknown strategy: {name}")
