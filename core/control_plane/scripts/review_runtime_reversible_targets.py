#!/usr/bin/env python3
"""Render an operator-focused review for reversible runtime targets."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from codex_home_policy_lib import DEFAULT_ROOT, load_json
from report_codex_home_policy import build_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review the governed reversible runtime targets as one operator batch.",
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


def _load_runtime_indexes(
    root: Path,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    registry = load_json(root / "runtime/runtime_surface_registry.json")
    class_policy = load_json(root / "runtime/runtime_class_policy.json")
    by_root_path = {
        entry["root_path"]: entry
        for entry in registry.get("surfaces", [])
    }
    by_category = {
        entry["category"]: entry
        for entry in class_policy.get("allowed_categories", [])
    }
    return by_root_path, by_category


def _operator_bias(retention_class: str) -> str:
    if retention_class == "rebuildable_runtime_cache":
        return "rotation_first"
    if retention_class == "live_runtime_temp":
        return "quarantine_first"
    return "manual_review_first"


def build_runtime_reversible_review(root: Path) -> Dict[str, Any]:
    report = build_report(root)
    runtime_registry, category_policy = _load_runtime_indexes(root)
    operations = load_json(
        root / "core/control_plane/codex_home_lifecycle_operations.json"
    )
    group = next(
        (
            item
            for item in report.get("action_groups", [])
            if item.get("group_id") == "runtime_reversible"
        ),
        {
            "group_id": "runtime_reversible",
            "title": "Runtime Reversible Targets",
            "recommended_action": "quarantine_or_rotate",
            "operator_focus": "Review cache/temp surfaces together for reversible rotation or quarantine.",
            "targets": [],
        },
    )
    by_target = {
        item["target"]: item
        for item in report.get("surfaces", [])
    }

    targets: List[Dict[str, Any]] = []
    group_targets = {item["target"] for item in group.get("targets", [])}
    for target in sorted(group_targets):
        registry_entry = runtime_registry[target]
        runtime_category = registry_entry["category"]
        class_entry = category_policy[runtime_category]
        detail = by_target[target]
        targets.append(
            {
                "target": target,
                "runtime_category": runtime_category,
                "retention_class": class_entry["retention_class"],
                "mirror_path": registry_entry.get("mirror_path", ""),
                "authoritative_at_root": registry_entry.get("authoritative_at_root", False),
                "mirror_required": class_entry["mirror_required"],
                "allow_optional_root": class_entry["allow_optional_root"],
                "health_class": detail["health_class"],
                "recommended_action": detail["recommended_action"],
                "allowed_actions": detail["allowed_actions"],
                "execution_modes": detail["execution_modes"],
                "rotation_allowed": "rotation_allowed" in detail["execution_modes"],
                "operator_bias": _operator_bias(class_entry["retention_class"]),
            }
        )

    out_of_scope_runtime_surfaces: List[Dict[str, Any]] = []
    for target, detail in sorted(by_target.items()):
        surface = detail["surface"]
        if surface["kind"] != "root_surface":
            continue
        if surface["selector_type"] != "runtime_category":
            continue
        if target in group_targets:
            continue
        registry_entry = runtime_registry.get(target)
        if registry_entry is None:
            continue
        runtime_category = registry_entry["category"]
        class_entry = category_policy[runtime_category]
        out_of_scope_runtime_surfaces.append(
            {
                "target": target,
                "runtime_category": runtime_category,
                "retention_class": class_entry["retention_class"],
                "health_class": detail["health_class"],
                "recommended_action": detail["recommended_action"],
            }
        )

    return {
        "root": root.as_posix(),
        "layout_version": report["layout_version"],
        "group": {
            "group_id": group["group_id"],
            "title": group["title"],
            "recommended_action": group["recommended_action"],
            "operator_focus": group["operator_focus"],
        },
        "operator_constraints": {
            "manual_review_required": True,
            "allow_hard_delete": operations["global_rules"]["allow_hard_delete"],
            "allow_hot_path_physical_move": operations["global_rules"]["allow_hot_path_physical_move"],
            "preferred_reversible_action": operations["global_rules"]["preferred_reversible_action"],
        },
        "summary": {
            "total_targets": len(targets),
            "by_runtime_category": dict(
                sorted(Counter(item["runtime_category"] for item in targets).items())
            ),
            "by_retention_class": dict(
                sorted(Counter(item["retention_class"] for item in targets).items())
            ),
        },
        "operator_sequence": [
            "Stay inside the runtime_reversible batch; do not widen this review to live runtime state surfaces.",
            "For rebuildable runtime cache surfaces, bounded rotation is eligible before any stronger cleanup idea.",
            "For live runtime temp surfaces, keep the root lookup path stable and prefer reversible quarantine handling.",
            "Any action remains manual-review-only and must preserve mirror continuity plus current compatibility entrypoints.",
        ],
        "targets": targets,
        "out_of_scope_runtime_surfaces": out_of_scope_runtime_surfaces,
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("group: %s" % payload["group"]["title"])
    print("recommended_action: %s" % payload["group"]["recommended_action"])
    print("operator_focus: %s" % payload["group"]["operator_focus"])
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("operator_constraints: %s" % json.dumps(payload["operator_constraints"], ensure_ascii=False, sort_keys=True))
    print("")
    print("operator_sequence:")
    for step in payload["operator_sequence"]:
        print("- %s" % step)
    print("")
    print("targets:")
    for item in payload["targets"]:
        print(
            "- %s | %s | %s | %s | mirror=%s | bias=%s"
            % (
                item["target"],
                item["runtime_category"],
                item["retention_class"],
                item["recommended_action"],
                item["mirror_path"] or "(none)",
                item["operator_bias"],
            )
        )
    print("")
    print("out_of_scope_runtime_surfaces:")
    for item in payload["out_of_scope_runtime_surfaces"]:
        print(
            "- %s | %s | %s | %s"
            % (
                item["target"],
                item["runtime_category"],
                item["retention_class"],
                item["recommended_action"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_runtime_reversible_review(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
