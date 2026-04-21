from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float


@dataclass
class OrderResult:
    symbol: str
    side: str
    quantity: float
    price: float
    broker_id: str | None = None


class Broker(Protocol):
    def connect(self) -> None: ...
    def cash(self) -> float: ...
    def positions(self) -> dict[str, Position]: ...
    def buy(self, symbol: str, notional_usd: float, price: float) -> OrderResult: ...
    def sell(self, symbol: str, quantity: float, price: float) -> OrderResult: ...


# ---------------------------------------------------------------------------
# Paper broker — fully simulated, state persisted to disk.
# ---------------------------------------------------------------------------

@dataclass
class PaperBroker:
    starting_cash: float = 10_000.0
    state_path: Path = field(default_factory=lambda: Path("state/paper.json"))
    _cash: float = 0.0
    _positions: dict[str, Position] = field(default_factory=dict)

    def connect(self) -> None:
        if self.state_path.exists():
            raw = json.loads(self.state_path.read_text())
            self._cash = raw["cash"]
            self._positions = {
                s: Position(**p) for s, p in raw["positions"].items()
            }
        else:
            self._cash = self.starting_cash
            self._positions = {}
            self._save()

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({
            "cash": self._cash,
            "positions": {s: p.__dict__ for s, p in self._positions.items()},
        }, indent=2))

    def cash(self) -> float:
        return self._cash

    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def buy(self, symbol: str, notional_usd: float, price: float) -> OrderResult:
        notional = min(notional_usd, self._cash)
        if notional <= 0:
            raise RuntimeError("paper broker out of cash")
        qty = notional / price
        self._cash -= notional
        existing = self._positions.get(symbol)
        if existing:
            total_qty = existing.quantity + qty
            avg = (existing.avg_price * existing.quantity + price * qty) / total_qty
            self._positions[symbol] = Position(symbol, total_qty, avg)
        else:
            self._positions[symbol] = Position(symbol, qty, price)
        self._save()
        return OrderResult(symbol, "buy", qty, price, broker_id="paper")

    def sell(self, symbol: str, quantity: float, price: float) -> OrderResult:
        pos = self._positions.get(symbol)
        if not pos or pos.quantity <= 0:
            raise RuntimeError(f"no position to sell for {symbol}")
        qty = min(quantity, pos.quantity)
        self._cash += qty * price
        remaining = pos.quantity - qty
        if remaining <= 1e-9:
            del self._positions[symbol]
        else:
            self._positions[symbol] = Position(symbol, remaining, pos.avg_price)
        self._save()
        return OrderResult(symbol, "sell", qty, price, broker_id="paper")


# ---------------------------------------------------------------------------
# Robinhood broker — uses the community `robin_stocks` library.
#
# Robinhood does not publish an official trading API. `robin_stocks` talks to
# the same private endpoints the mobile/web apps use. Using it may conflict
# with Robinhood's Terms of Service — proceed at your own risk and never with
# money you can't afford to lose.
# ---------------------------------------------------------------------------

class RobinhoodBroker:
    def __init__(self) -> None:
        self._rh = None

    def connect(self) -> None:
        import robin_stocks.robinhood as rh  # lazy import so paper mode works without the dep

        username = os.environ.get("ROBINHOOD_USERNAME")
        password = os.environ.get("ROBINHOOD_PASSWORD")
        if not username or not password:
            raise RuntimeError("set ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD in the environment")

        mfa_code = None
        secret = os.environ.get("ROBINHOOD_MFA_SECRET")
        if secret:
            import pyotp
            mfa_code = pyotp.TOTP(secret).now()

        rh.login(username=username, password=password, mfa_code=mfa_code, store_session=True)
        self._rh = rh

    def cash(self) -> float:
        profile = self._rh.profiles.load_account_profile()
        return float(profile.get("buying_power") or profile.get("cash") or 0)

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self._rh.account.get_open_stock_positions():
            qty = float(p.get("quantity") or 0)
            if qty <= 0:
                continue
            instrument = self._rh.helper.request_get(p["instrument"])
            symbol = instrument["symbol"]
            out[symbol] = Position(symbol, qty, float(p.get("average_buy_price") or 0))
        return out

    def buy(self, symbol: str, notional_usd: float, price: float) -> OrderResult:
        resp = self._rh.orders.order_buy_fractional_by_price(symbol, round(notional_usd, 2))
        return OrderResult(symbol, "buy", notional_usd / price, price, broker_id=resp.get("id"))

    def sell(self, symbol: str, quantity: float, price: float) -> OrderResult:
        resp = self._rh.orders.order_sell_fractional_by_quantity(symbol, round(quantity, 6))
        return OrderResult(symbol, "sell", quantity, price, broker_id=resp.get("id"))


# ---------------------------------------------------------------------------
# Cash App — not supported.
#
# Cash App Investing does NOT expose a public API for programmatic trading.
# There is no sanctioned way to place trades on a Cash App brokerage account
# from code. This adapter exists to make that explicit and to redirect you to
# a free alternative (Alpaca) that behaves similarly to Cash App: commission
# free, fractional shares, paper or live trading over HTTP.
# ---------------------------------------------------------------------------

class CashAppBroker:
    def connect(self) -> None:
        raise NotImplementedError(
            "Cash App does not offer a public trading API. Use broker='robinhood' or "
            "switch to a broker with a real API (e.g. Alpaca — see README)."
        )

    def cash(self) -> float: raise NotImplementedError
    def positions(self) -> dict[str, Position]: raise NotImplementedError
    def buy(self, symbol, notional_usd, price): raise NotImplementedError
    def sell(self, symbol, quantity, price): raise NotImplementedError


def build(name: str, config: dict) -> Broker:
    name = name.lower()
    if name == "paper":
        return PaperBroker(starting_cash=float(config.get("starting_cash", 10_000)))
    if name == "robinhood":
        return RobinhoodBroker()
    if name == "cashapp":
        return CashAppBroker()
    raise ValueError(f"unknown broker: {name}")
