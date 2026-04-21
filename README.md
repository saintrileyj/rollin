# rollin

A small trade bot with a mobile-friendly web UI. Runs an SMA-crossover
strategy against an **Alpaca** account (free paper or live), with optional
Robinhood and built-in paper brokers.

<img alt="ui" src="docs/ui.png" width="320" onerror="this.style.display='none'">

## Test it on your phone right now

1. Get free Alpaca paper keys → <https://app.alpaca.markets/paper/dashboard/overview>
   (sign in, "Generate New Key", copy the Key ID and Secret).

2. On your computer:

   ```bash
   git clone <this repo> && cd rollin
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt

   cp .env.example .env
   # edit .env and paste your ALPACA_KEY_ID / ALPACA_SECRET_KEY
   # leave ALPACA_BASE_URL=https://paper-api.alpaca.markets to stay on paper
   ```

3. Start the server:

   ```bash
   python -m tradebot.web
   ```

   It prints a line like `tradebot web UI:  http://192.168.1.42:5050`.

4. On your phone (same Wi-Fi as your computer), open that URL in Safari /
   Chrome. Add it to the home screen for an app-like launch — the UI is a
   PWA-style full-width layout with a dark theme.

> If you're not on the same network, tunnel it:
> `ngrok http 5050` (or `cloudflared tunnel --url http://localhost:5050`),
> then open the public URL on your phone. Keep `dry_run` on until you trust
> it — even paper orders are rate-limited.

## What you get in the UI

- **Portfolio** card — cash, buying power, portfolio value, account status.
- **Controls** — Start/Stop the bot, tick once on demand, toggle dry-run,
  tune poll interval, SMA windows, order size, lookback, and symbol list.
- **Positions** — live list of open positions with quantity and avg price.
- **Manual trade** — buy a dollar-notional amount or sell a whole position.
- **Activity** — rolling log of signals, orders, and errors.

All of it calls the same JSON API (`GET /api/account`, `POST /api/orders`,
etc.) so you can script against it too.

## About the brokers

- **Alpaca (default)** — real HTTP trading API, free paper endpoint, no
  commissions, fractional shares. Set `ALPACA_BASE_URL` to
  `https://api.alpaca.markets` to go live.
- **Paper** — fully simulated, state persisted to `state/paper.json`. Good
  for poking at the UI with no account.
- **Robinhood** — community `robin_stocks` library, no official API. Using
  it may conflict with Robinhood's ToS. Proceed at your own risk.
- **Cash App** — **not supported.** Cash App Investing has no public trading
  API. The adapter exists only to surface that clearly and point you at
  Alpaca.

## CLI (no UI)

```bash
cp config.example.yaml config.yaml
python -m tradebot -c config.yaml        # loop forever
python -m tradebot --once                # single tick, useful for cron
```

## Layout

```
tradebot/
  __main__.py        # CLI entry
  web.py             # Flask entry (python -m tradebot.web)
  runner.py          # threaded bot runner shared by CLI and UI
  bot.py             # simple CLI loop
  brokers.py         # Alpaca, Paper, Robinhood, CashApp (stub)
  strategy.py        # SMA crossover
  data.py            # yfinance price data
  templates/index.html
  static/app.js
  static/style.css
```

## Disclaimers

Educational software. Bugs can cost real money — keep `dry_run: true` and
`ALPACA_BASE_URL` pointing at the paper endpoint until you're sure. Nothing
here is financial advice.
