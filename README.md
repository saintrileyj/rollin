# rollin

A small Python trade bot that runs an SMA-crossover strategy against a
**Robinhood** account or a built-in **paper** account.

> **⚠️ Read this before running it**
>
> - This is educational software. Markets move fast; bugs lose money. Use the
>   paper broker until you trust the code.
> - **Robinhood has no official public API.** This bot uses the community
>   [`robin_stocks`](https://github.com/jmfernandes/robin_stocks) library, which
>   drives the same private endpoints the Robinhood apps use. Automating your
>   account may conflict with Robinhood's Terms of Service. Proceed at your own
>   risk, and never with money you cannot afford to lose.
> - **Cash App is not supported.** Cash App Investing does not expose a public
>   trading API — there is no sanctioned way to place trades on a Cash App
>   brokerage account from code. If you want something that behaves like Cash
>   App (commission free, fractional shares, simple HTTP API), use
>   [Alpaca](https://alpaca.markets); it has a free paper account and is easy
>   to swap in as another broker adapter.
> - Nothing here is financial advice.

## Layout

```
tradebot/
  __main__.py     # CLI entry (python -m tradebot)
  bot.py          # main loop
  brokers.py      # PaperBroker, RobinhoodBroker, CashAppBroker (stub)
  strategy.py     # SMA crossover
  data.py         # yfinance price history
config.example.yaml
.env.example
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml
cp .env.example .env        # only needed for the robinhood broker
```

Edit `config.yaml` to pick your broker, symbols, and strategy parameters.
If you set `broker: robinhood`, fill in `ROBINHOOD_USERNAME` /
`ROBINHOOD_PASSWORD` in `.env`. If your account has 2FA enabled, add
`ROBINHOOD_MFA_SECRET` (the base32 secret from your authenticator app, *not*
a 6-digit code — the bot generates codes on demand with `pyotp`).

## Run

Dry-run paper loop (safe — only logs intended orders):

```bash
python -m tradebot -c config.yaml
```

Single tick and exit (useful for cron):

```bash
python -m tradebot --once
```

To actually place orders, flip `dry_run: false` in `config.yaml`.

## Strategy

`sma_crossover` is the only strategy included. Each tick it pulls daily bars
for every configured symbol, computes a fast and slow simple moving average,
and emits:

- **buy** when the fast SMA crosses above the slow SMA
- **sell** (close the full position) when it crosses below
- **hold** otherwise

Add new strategies by implementing `evaluate(symbol, history) -> Signal` in
`tradebot/strategy.py` and registering them in `build()`.

## Adding another broker

Implement the `Broker` protocol in `tradebot/brokers.py`:

```python
def connect(self) -> None: ...
def cash(self) -> float: ...
def positions(self) -> dict[str, Position]: ...
def buy(self, symbol, notional_usd, price) -> OrderResult: ...
def sell(self, symbol, quantity, price) -> OrderResult: ...
```

then register it in `build()`. Alpaca is a natural next adapter — its
`alpaca-py` SDK maps almost one-for-one onto these methods.
