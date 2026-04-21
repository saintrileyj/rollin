from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Any

from . import brokers, data, strategy

log = logging.getLogger(__name__)


class BotRunner:
    """Bot you can start/stop from the web UI. Keeps a rolling signal/order log."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {
            "broker": "alpaca",
            "dry_run": True,
            "poll_interval": 60,
            "symbols": ["AAPL", "MSFT", "SPY"],
            "strategy": {"name": "sma_crossover", "fast": 10, "slow": 30},
            "lookback_days": 90,
            "order_size_usd": 500.0,
        }
        self._broker: brokers.Broker | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.events: deque[dict] = deque(maxlen=200)
        self.last_tick: float | None = None
        self.started_at: float | None = None

    # -- state ---------------------------------------------------------------

    def status(self) -> dict:
        running = self._thread is not None and self._thread.is_alive()
        return {
            "running": running,
            "started_at": self.started_at,
            "last_tick": self.last_tick,
            "config": self.config,
        }

    def update_config(self, patch: dict) -> dict:
        with self._lock:
            for k, v in patch.items():
                if k == "strategy" and isinstance(v, dict):
                    self.config["strategy"] = {**self.config["strategy"], **v}
                else:
                    self.config[k] = v
        self._log("info", f"config updated: {list(patch.keys())}")
        return self.config

    def _log(self, level: str, message: str, **extra) -> None:
        event = {"ts": time.time(), "level": level, "message": message, **extra}
        self.events.appendleft(event)
        getattr(log, level, log.info)(message)

    # -- broker --------------------------------------------------------------

    def broker(self) -> brokers.Broker:
        if self._broker is None:
            b = brokers.build(self.config["broker"], {"starting_cash": 10_000})
            b.connect()
            self._broker = b
            self._log("info", f"connected to {self.config['broker']}")
        return self._broker

    def disconnect(self) -> None:
        self._broker = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._loop, name="bot-loop", daemon=True)
        self._thread.start()
        self._log("info", "bot started")

    def stop(self) -> None:
        self._stop.set()
        self._log("info", "stop requested")
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # keep the loop alive on transient failures
                self._log("error", f"tick failed: {exc}")
            # Sleep in small increments so stop() is responsive.
            remaining = int(self.config.get("poll_interval", 60))
            while remaining > 0 and not self._stop.is_set():
                time.sleep(min(1, remaining))
                remaining -= 1

    # -- work ----------------------------------------------------------------

    def tick(self) -> list[dict]:
        """Run the strategy across all configured symbols, optionally place orders."""
        broker = self.broker()
        cfg = self.config
        strat = strategy.build(cfg["strategy"]["name"], cfg["strategy"])
        positions = broker.positions()
        out: list[dict] = []

        for symbol in cfg["symbols"]:
            try:
                history = data.get_history(symbol, int(cfg.get("lookback_days", 90)))
            except Exception as exc:
                self._log("warn", f"{symbol}: {exc}")
                continue

            signal = strat.evaluate(symbol, history)
            out.append(asdict(signal))

            if signal.side == "hold":
                continue

            self._log("info", f"{symbol} {signal.side.upper()} @ {signal.price:.2f} — {signal.reason}",
                      symbol=symbol, side=signal.side, price=signal.price)

            if cfg.get("dry_run", True):
                continue

            try:
                if signal.side == "buy":
                    res = broker.buy(symbol, float(cfg["order_size_usd"]), signal.price)
                else:
                    pos = positions.get(symbol)
                    if not pos:
                        self._log("info", f"{symbol} sell signal but no position")
                        continue
                    res = broker.sell(symbol, pos.quantity, signal.price)
                self._log(
                    "info",
                    f"order filled: {res.side} {res.quantity:.4f} {res.symbol} @ {res.price:.2f}",
                    broker_id=res.broker_id, symbol=res.symbol, side=res.side,
                )
            except Exception as exc:
                self._log("error", f"{symbol} order failed: {exc}")

        self.last_tick = time.time()
        return out

    # -- manual orders -------------------------------------------------------

    def manual_order(self, symbol: str, side: str, notional_usd: float | None, quantity: float | None) -> dict:
        broker = self.broker()
        price = data.get_last_price(symbol)
        side = side.lower()
        if side == "buy":
            if not notional_usd:
                raise ValueError("notional_usd required for manual buy")
            res = broker.buy(symbol, float(notional_usd), price)
        elif side == "sell":
            if quantity is None:
                pos = broker.positions().get(symbol)
                if not pos:
                    raise ValueError(f"no position in {symbol}")
                quantity = pos.quantity
            res = broker.sell(symbol, float(quantity), price)
        else:
            raise ValueError(f"unknown side: {side}")
        self._log("info", f"manual {res.side} {res.quantity:.4f} {res.symbol} @ {res.price:.2f}",
                  symbol=res.symbol, side=res.side, broker_id=res.broker_id)
        return asdict(res)
