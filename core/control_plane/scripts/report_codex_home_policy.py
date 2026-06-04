#!/usr/bin/env python3
"""Render a batch governance report over all governed codex-home surfaces."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from codex_home_policy_lib import DEFAULT_ROOT, diagnose_surface, governed_targets


def _build_action_groups(surfaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for item in surfaces:
        action = item["recommended_action"]
        health = item["health_class"]
        surface = item["surface"]
        if health in {"stable_preserve", "archive_governed"}:
            continue

        if action == "quarantine_or_rotate":
            group_id = "runtime_reversible"
            title = "Runtime Reversible Targets"
            operator_focus = "Review cache/temp surfaces together for reversible rotation or quarantine."
        elif action == "use_owning_tool_or_quarantine":
            group_id = "tool_owned_reversible"
            title = "Tool-Owned Reversible Targets"
            operator_focus = "Use the owning toolchain before any manual quarantine decision."
        else:
            group_id = "manual_review"
            title = "Manual Review Targets"
            operator_focus = "Manual policy review is required before action."

        group = groups.setdefault(
            group_id,
            {
                "group_id": group_id,
                "title": title,
                "recommended_action": action,
                "operator_focus": operator_focus,
                "targets": [],
            },
        )
        group["targets"].append(
            {
                "target": item["target"],
                "health_class": health,
                "selector_type": surface["selector_type"],
                "selector": surface["selector"],
            }
        )

    ordered = []
    for group_id in ("runtime_reversible", "tool_owned_reversible", "manual_review"):
        group = groups.get(group_id)
        if group is not None:
            group["targets"].sort(key=lambda item: item["target"])
            ordered.append(group)
    return ordered


def build_report(root: Path) -> Dict[str, Any]:
    surfaces = [diagnose_surface(root, target) for target in governed_targets(root)]
    surfaces.sort(key=lambda item: (item["surface"]["kind"], item["target"]))

    by_health = Counter(item["health_class"] for item in surfaces)
    by_kind = Counter(item["surface"]["kind"] for item in surfaces)
    by_action = Counter(item["recommended_action"] for item in surfaces)
    attention = [
        item["target"]
        for item in surfaces
        if item["health_class"] not in {"stable_preserve", "archive_governed"}
    ]

    return {
        "root": root.as_posix(),
        "layout_version": surfaces[0]["layout_version"] if surfaces else None,
        "summary": {
            "total_surfaces": len(surfaces),
            "by_health_class": dict(sorted(by_health.items())),
            "by_kind": dict(sorted(by_kind.items())),
            "by_recommended_action": dict(sorted(by_action.items())),
            "attention_targets": attention,
        },
        "action_groups": _build_action_groups(surfaces),
        "targets": surfaces,
        "surfaces": surfaces,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report governance posture for all governed codex-home surfaces.",
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


def _print_text(payload: Dict[str, Any]) -> None:
    summary = payload["summary"]
    print("layout_version: %s" % payload["layout_version"])
    print("total_surfaces: %s" % summary["total_surfaces"])
    print("by_health_class: %s" % json.dumps(summary["by_health_class"], ensure_ascii=False, sort_keys=True))
    print("by_recommended_action: %s" % json.dumps(summary["by_recommended_action"], ensure_ascii=False, sort_keys=True))
    print("attention_targets: %s" % (", ".join(summary["attention_targets"]) if summary["attention_targets"] else "(none)"))
    print("")
    print("action_groups:")
    for group in payload["action_groups"]:
        targets = ", ".join(item["target"] for item in group["targets"])
        print(
            "- %s | %s | %s"
            % (group["title"], group["recommended_action"], targets or "(none)")
        )
    print("")
    print("surfaces:")
    for item in payload["surfaces"]:
        surface = item["surface"]
        print(
            "- %s | %s | %s | %s | %s/%s"
            % (
                item["target"],
                surface["kind"],
                item["health_class"],
                item["recommended_action"],
                surface["selector_type"],
                surface["selector"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_report(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
