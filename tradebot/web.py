from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from .runner import BotRunner


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False
    runner = BotRunner()
    app.config["runner"] = runner

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        return jsonify(runner.status())

    @app.get("/api/account")
    def account():
        try:
            b = runner.broker()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        if hasattr(b, "account"):
            return jsonify(b.account())
        return jsonify({"cash": b.cash()})

    @app.get("/api/positions")
    def positions():
        try:
            b = runner.broker()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify([dataclasses.asdict(p) for p in b.positions().values()])

    @app.get("/api/events")
    def events():
        return jsonify(list(runner.events))

    @app.post("/api/config")
    def set_config():
        patch = request.get_json(force=True, silent=True) or {}
        # Broker change invalidates the cached client.
        if "broker" in patch and patch["broker"] != runner.config.get("broker"):
            runner.disconnect()
        return jsonify(runner.update_config(patch))

    @app.post("/api/bot/start")
    def start_bot():
        runner.start()
        return jsonify(runner.status())

    @app.post("/api/bot/stop")
    def stop_bot():
        runner.stop()
        return jsonify(runner.status())

    @app.post("/api/tick")
    def tick_once():
        try:
            signals = runner.tick()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"signals": signals, "last_tick": runner.last_tick})

    @app.post("/api/orders")
    def manual_order():
        body = request.get_json(force=True, silent=True) or {}
        try:
            result = runner.manual_order(
                symbol=body["symbol"].upper(),
                side=body["side"],
                notional_usd=body.get("notional_usd"),
                quantity=body.get("quantity"),
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tradebot.web", description="Mobile-friendly trade bot UI")
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default: 0.0.0.0 so your phone can reach it)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = create_app()
    lan = _guess_lan_ip()
    print(f"\n  tradebot web UI:  http://{lan}:{args.port}  (open this on your phone)\n", file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


def _guess_lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == "__main__":
    sys.exit(main())
