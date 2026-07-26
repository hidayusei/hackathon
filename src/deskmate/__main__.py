"""DeskMate command-line entry point."""

import argparse

from deskmate.app import DeskMateApp
from deskmate.config.loader import deep_merge, load_config
from deskmate.logging_setup import setup_logging


def main() -> int:
    """Parse command-line options and start DeskMate."""
    parser = argparse.ArgumentParser(prog="deskmate")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--source")
    parser.add_argument("--config")
    args = parser.parse_args()
    # Merge deeply: a shallow update would let --source drop --demo's dummy settings.
    overrides: dict[str, object] = {}
    if args.demo:
        overrides = deep_merge(overrides, {"input": {"source": "dummy", "dummy": {"mode": "demo"}}})
    if args.debug:
        overrides = deep_merge(overrides, {"debug": {"enabled": True}})
    if args.source:
        overrides = deep_merge(overrides, {"input": {"source": args.source}})
    config = load_config(overrides)
    setup_logging(config.logging, config.privacy)
    app = DeskMateApp(config, headless=args.headless)
    if args.headless:
        app.runner.status_changed.connect(
            lambda snapshot: print(
                f"{snapshot.updated_at.isoformat()} {snapshot.status.value} "
                f"{snapshot.confidence:.2f}",
                flush=True,
            )
        )
    try:
        return app.run()
    finally:
        app.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
