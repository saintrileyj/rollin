from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from . import brokers, data, strategy

log = logging.getLogger(__name__)


@dataclass
class BotConfig:
    broker: str
    dry_run: bool
    poll_interval: int
    starting_cash: float
    symbols: list[str]
    strategy_name: str
    strategy_params: dict[str, Any]
    order_size_usd: float
    lookback_days: int


def _config_from_yaml(raw: dict) -> BotConfig:
    strat = raw.get("strategy", {})
    return BotConfig(
        broker=raw.get("broker", "paper"),
        dry_run=bool(raw.get("dry_run", True)),
        poll_interval=int(raw.get("poll_interval", 60)),
        starting_cash=float(raw.get("starting_cash", 10_000)),
        symbols=list(raw.get("symbols", [])),
        strategy_name=strat.get("name", "sma_crossover"),
        strategy_params={k: v for k, v in strat.items() if k not in {"name", "lookback_days", "order_size_usd"}},
        order_size_usd=float(strat.get("order_size_usd", 500)),
        lookback_days=int(strat.get("lookback_days", 90)),
    )


class Bot:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.broker = brokers.build(cfg.broker, {"starting_cash": cfg.starting_cash})
        self.strategy = strategy.build(cfg.strategy_name, cfg.strategy_params)

    def start(self) -> None:
        self.broker.connect()
        log.info(
            "bot started: broker=%s dry_run=%s strategy=%s symbols=%s cash=$%.2f",
            self.cfg.broker, self.cfg.dry_run, self.cfg.strategy_name,
            self.cfg.symbols, self.broker.cash(),
        )

    def tick(self) -> None:
        positions = self.broker.positions()
        for symbol in self.cfg.symbols:
            try:
                history = data.get_history(symbol, self.cfg.lookback_days)
            except Exception as exc:  # network / bad ticker
                log.warning("skipping %s: %s", symbol, exc)
                continue

            signal = self.strategy.evaluate(symbol, history)
            if signal.side == "hold":
                log.debug("%s hold @ %.2f (%s)", symbol, signal.price, signal.reason)
                continue

            log.info("%s SIGNAL %s @ %.2f — %s", symbol, signal.side.upper(), signal.price, signal.reason)
            if self.cfg.dry_run:
                continue

            try:
                if signal.side == "buy":
                    result = self.broker.buy(symbol, self.cfg.order_size_usd, signal.price)
                elif signal.side == "sell":
                    pos = positions.get(symbol)
                    if not pos:
                        log.info("%s sell signal but no open position — skipping", symbol)
                        continue
                    result = self.broker.sell(symbol, pos.quantity, signal.price)
                else:
                    continue
                log.info("order filled: %s %.6f %s @ %.2f (id=%s)",
                         result.side, result.quantity, result.symbol, result.price, result.broker_id)
            except Exception as exc:
                log.exception("order failed for %s: %s", symbol, exc)

    def run_forever(self) -> None:
        self.start()
        while True:
            try:
                self.tick()
            except KeyboardInterrupt:
                log.info("interrupted, shutting down")
                return
            except Exception:
                log.exception("tick failed")
            time.sleep(self.cfg.poll_interval)


def from_yaml(raw: dict) -> Bot:
    return Bot(_config_from_yaml(raw))
