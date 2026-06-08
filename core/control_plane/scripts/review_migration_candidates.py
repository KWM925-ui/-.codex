#!/usr/bin/env python3
"""Render the governed codex-home migration candidates."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from codex_home_policy_lib import DEFAULT_ROOT, load_json
from governed_operator_review_lib import compatibility_details


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review governed migration candidates for ~/.codex productization.",
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


def build_migration_candidate_review(root: Path) -> Dict[str, Any]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    contract = load_json(
        root / "core/control_plane/codex_home_migration_candidates.json"
    )
    compatibility_index = {
        entry["path"]: entry
        for entry in manifest.get("compatibility_surfaces", [])
    }

    candidates: List[Dict[str, Any]] = []
    for entry in contract.get("candidates", []):
        candidate = dict(entry)
        candidate["compatibility_status"] = [
            compatibility_details(root, path, compatibility_index.get(path))
            for path in entry.get("compatibility_entrypoints", [])
        ]
        candidate["all_compatibility_entrypoints_resolve"] = all(
            item["resolves_to_expected"] for item in candidate["compatibility_status"]
        )
        candidates.append(candidate)

    return {
        "root": root.as_posix(),
        "layout_version": manifest.get("layout_version"),
        "summary": {
            "total_candidates": len(candidates),
            "all_compatibility_entrypoints_resolve": all(
                item["all_compatibility_entrypoints_resolve"]
                for item in candidates
            ) if candidates else True,
            "candidate_ids": [item["id"] for item in candidates],
        },
        "candidates": candidates,
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("")
    print("candidates:")
    for item in payload["candidates"]:
        print(
            "- %s | %s | %s | compat_ok=%s"
            % (
                item["id"],
                item["candidate_kind"],
                item["target"],
                item["all_compatibility_entrypoints_resolve"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_migration_candidate_review(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
