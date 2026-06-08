#!/usr/bin/env python3
"""Explain the governance and execution policy for one ~/.codex surface."""

import argparse
import json
from pathlib import Path

from codex_home_policy_lib import DEFAULT_ROOT, explain_surface


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explain the current codex-home governance policy for one surface.",
    )
    parser.add_argument(
        "target",
        help="A governed root surface such as sessions, tmp, config.toml, or a project_assets path.",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = explain_surface(Path(args.root).resolve(), args.target)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    surface = payload["surface"]
    print("target: %s" % payload["target"])
    print("layout_version: %s" % payload["layout_version"])
    print("selector: %s/%s" % (surface["selector_type"], surface["selector"]))
    print("kind: %s" % surface["kind"])
    print("source: %s" % surface["source"])
    print("allowed_actions: %s" % ", ".join(payload["allowed_actions"]))
    print("execution_modes: %s" % ", ".join(payload["execution_modes"]))
    print("global_rules:")
    for key, value in sorted(payload["global_rules"].items()):
        print("  %s = %s" % (key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
