from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib

from .generator import generate
from .model import parse_blueprint


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netforge",
        description="Validate a network source of truth and generate Linux router, DHCP and documentation artifacts.",
    )
    parser.add_argument("blueprint", type=Path, help="Path to the TOML blueprint")
    parser.add_argument("--output", type=Path, default=Path("generated"), help="Generated output directory")
    parser.add_argument("--check", action="store_true", help="Validate only; do not generate files")
    parser.add_argument("--clean", action="store_true", help="Remove the output directory before generation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with args.blueprint.open("rb") as handle:
            data = tomllib.load(handle)
        blueprint = parse_blueprint(data)
        if args.check:
            print(
                f"Blueprint valid: {len(blueprint.networks)} networks, "
                f"{len(blueprint.hosts)} static hosts."
            )
            return 0
        written = generate(blueprint, args.output, clean=args.clean)
        print(f"Generated {len(written)} files in {args.output}")
        for path in written:
            print(f"  {path}")
        return 0
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
