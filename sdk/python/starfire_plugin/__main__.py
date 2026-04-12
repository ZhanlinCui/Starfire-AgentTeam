"""CLI entry point: ``python -m starfire_plugin validate <path>``.

Validates a Starfire plugin directory against both:

1. The plugin-level ``plugin.yaml`` (Starfire-specific manifest).
2. Every ``skills/<name>/SKILL.md`` inside it, against the
   `agentskills.io open standard <https://agentskills.io/specification>`_.

Exit code 0 when valid, 1 when any errors are found. Intended for CI
(``python -m starfire_plugin validate plugins/*``) and local author
workflows before publishing a plugin repo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manifest import validate_plugin


def _validate(paths: list[str]) -> int:
    total_errors = 0
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print(f"✗ {path}: does not exist", file=sys.stderr)
            total_errors += 1
            continue
        if not path.is_dir():
            print(f"✗ {path}: not a directory", file=sys.stderr)
            total_errors += 1
            continue

        results = validate_plugin(path)
        if not results:
            print(f"✓ {path}: valid (plugin.yaml + all skills pass agentskills.io spec)")
            continue

        for source, errors in results.items():
            total_errors += len(errors)
            for err in errors:
                print(f"✗ {path}/{source}: {err}", file=sys.stderr)

    return 0 if total_errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="starfire_plugin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate one or more plugin directories")
    v.add_argument("paths", nargs="+", help="plugin directory paths to validate")

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        return _validate(args.paths)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
