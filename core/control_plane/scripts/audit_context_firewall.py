#!/usr/bin/env python3
"""Audit the governed context-firewall contracts."""

import argparse
import json
from pathlib import Path

from context_firewall_lib import (
    DEFAULT_ROOT,
    checks_as_jsonable,
    load_json,
    summarize_context_firewall,
    validate_context_firewall_contracts,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the context-firewall contracts for ~/.codex.",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root = Path(args.root).resolve()
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    checks = validate_context_firewall_contracts(root, manifest)
    ok = all(check.ok for check in checks)
    payload = {
        "ok": ok,
        "root": root.as_posix(),
        "layout_version": manifest.get("layout_version"),
        "summary": summarize_context_firewall(root, manifest) if ok else {},
        "checks": checks_as_jsonable(checks),
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    passed = sum(1 for check in checks if check.ok)
    total = len(checks)
    print("%s %d/%d checks passed" % ("PASS" if ok else "FAIL", passed, total))
    if ok:
        print(
            "stages: %s"
            % ", ".join(payload["summary"].get("stages", []))
        )
        print(
            "source_classes: %s"
            % ", ".join(payload["summary"].get("source_classes", []))
        )
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print("[%s] %s - %s" % (status, check.name, check.details))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
