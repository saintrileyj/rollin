from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .bot import from_yaml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tradebot", description="SMA trade bot for Robinhood / paper accounts")
    parser.add_argument("-c", "--config", default="config.yaml", help="path to YAML config (default: config.yaml)")
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    load_dotenv()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"config not found: {cfg_path} (copy config.example.yaml to {cfg_path})", file=sys.stderr)
        return 2
    raw = yaml.safe_load(cfg_path.read_text())
    bot = from_yaml(raw)

    if args.once:
        bot.start()
        bot.tick()
        return 0
    bot.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
