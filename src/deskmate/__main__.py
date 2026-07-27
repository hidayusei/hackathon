"""DeskMate command-line entry point."""

import argparse
from pathlib import Path

from deskmate.app import DeskMateApp
from deskmate.config.loader import deep_merge, load_config
from deskmate.logging_setup import setup_logging


def main() -> int:
    """Parse command-line options and start DeskMate."""
    parser = argparse.ArgumentParser(prog="deskmate")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--source",
        choices=("auto", "metavision", "replay", "dummy", "file", "hdf5"),
    )
    parser.add_argument("--replay")
    parser.add_argument("--raw")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--break-demo", action="store_true")
    parser.add_argument("--config")
    args = parser.parse_args()
    # Merge deeply: a shallow update would let --source drop --demo's dummy settings.
    overrides: dict[str, object] = {}
    if args.demo:
        overrides = deep_merge(overrides, {"input": {"source": "dummy", "dummy": {"mode": "demo"}}})
    if args.debug:
        overrides = deep_merge(overrides, {"debug": {"enabled": True}})
    if args.break_demo:
        overrides = deep_merge(overrides, {"break": {"demo_scale": 0.02}})
    if args.fullscreen:
        overrides = deep_merge(overrides, {"app": {"fullscreen": True}})
    if args.replay:
        overrides = deep_merge(
            overrides,
            {"input": {"source": "replay", "file": {"path": args.replay}}},
        )
    if args.raw:
        overrides = deep_merge(
            overrides,
            {"input": {"source": "metavision", "metavision": {"input_path": args.raw}}},
        )
    if args.source:
        overrides = deep_merge(overrides, {"input": {"source": args.source}})
    config = load_config(
        overrides,
        config_path=Path(args.config) if args.config else None,
    )
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
