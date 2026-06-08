#!/usr/bin/env python3
"""Summarize governance posture and suggested operator action for one surface."""

import argparse
import json
from pathlib import Path

from codex_home_policy_lib import (
    DEFAULT_ROOT,
    diagnose_surface,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Doctor one codex-home governed surface and suggest the safe operator path.",
    )
    parser.add_argument("target", help="Governed surface or project_assets path.")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = diagnose_surface(Path(args.root).resolve(), args.target)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("target: %s" % payload["target"])
    print("health_class: %s" % payload["health_class"])
    print("recommended_action: %s" % payload["recommended_action"])
    print("allowed_actions: %s" % ", ".join(payload["allowed_actions"]))
    print("execution_modes: %s" % ", ".join(payload["execution_modes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
