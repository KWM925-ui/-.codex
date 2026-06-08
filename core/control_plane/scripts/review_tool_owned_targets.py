#!/usr/bin/env python3
"""Render an operator-focused review for tool-owned governed targets."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from codex_home_policy_lib import DEFAULT_ROOT, load_json
from governed_operator_review_lib import (
    compatibility_details,
    load_namespace_registry_and_compatibility,
    subsurface_inventory,
)
from report_codex_home_policy import build_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review the governed tool-owned targets as one operator batch.",
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


def _workflow_artifacts(
    root: Path,
    namespace_path: str,
    ignored_relative_paths: List[str],
) -> List[str]:
    namespace_root = root / namespace_path
    if not namespace_root.exists():
        return []

    ignored = set(ignored_relative_paths)
    artifacts: List[str] = []
    direct_files = {"SKILL.md", "plugin.json"}
    workflow_dirs = {".codex-plugin", "scripts", "tools", "workflows"}
    direct_suffixes = {".py", ".sh"}

    for child in sorted(namespace_root.iterdir(), key=lambda item: item.name):
        child_rel = child.relative_to(root).as_posix()
        if child_rel in ignored:
            continue
        if child.is_file():
            if child.name in direct_files or child.suffix in direct_suffixes:
                artifacts.append(child_rel)
            continue
        if child.is_dir() and child.name in workflow_dirs:
            for nested in sorted(child.rglob("*")):
                if not nested.is_file():
                    continue
                artifacts.append(nested.relative_to(root).as_posix())
                if len(artifacts) >= 20:
                    return artifacts
    return artifacts


def build_tool_owned_review(root: Path) -> Dict[str, Any]:
    report = build_report(root)
    namespace_registry, compatibility_surfaces = (
        load_namespace_registry_and_compatibility(root)
    )
    operations = load_json(
        root / "core/control_plane/codex_home_lifecycle_operations.json"
    )
    group = next(
        (
            item
            for item in report.get("action_groups", [])
            if item.get("group_id") == "tool_owned_reversible"
        ),
        {
            "group_id": "tool_owned_reversible",
            "title": "Tool-Owned Reversible Targets",
            "recommended_action": "use_owning_tool_or_quarantine",
            "operator_focus": "Use the owning toolchain before any manual quarantine decision.",
            "targets": [],
        },
    )
    by_target = {
        item["target"]: item
        for item in report.get("surfaces", [])
    }

    targets: List[Dict[str, Any]] = []
    for group_target in sorted(group.get("targets", []), key=lambda item: item["target"]):
        target = group_target["target"]
        namespace_entry = namespace_registry[target]
        registered_subsurfaces = []
        for subsurface in namespace_entry.get("subsurfaces", []):
            detail = dict(subsurface)
            detail.update(subsurface_inventory(root, subsurface["path"]))
            registered_subsurfaces.append(detail)
        workflow_artifacts = _workflow_artifacts(
            root,
            namespace_entry["path"],
            [subsurface["path"] for subsurface in namespace_entry.get("subsurfaces", [])],
        )
        compatibility_entrypoints = [
            compatibility_details(
                root,
                entrypoint,
                compatibility_surfaces.get(entrypoint),
            )
            for entrypoint in namespace_entry.get("compatibility_entrypoints", [])
        ]
        detail = by_target[target]
        workflow_status = (
            "workflow_artifacts_present"
            if workflow_artifacts
            else "no_local_workflow_artifacts_detected"
        )
        targets.append(
            {
                "target": target,
                "namespace_id": namespace_entry["id"],
                "namespace_type": namespace_entry["type"],
                "health_class": detail["health_class"],
                "recommended_action": detail["recommended_action"],
                "allowed_actions": detail["allowed_actions"],
                "execution_modes": detail["execution_modes"],
                "compatibility_entrypoints": compatibility_entrypoints,
                "registered_subsurfaces": registered_subsurfaces,
                "workflow_artifacts": workflow_artifacts,
                "workflow_status": workflow_status,
                "operator_bias": "owning_tool_first",
                "quarantine_fallback_allowed": "quarantine" in detail["allowed_actions"],
            }
        )

    other_attention_groups = []
    for action_group in report.get("action_groups", []):
        if action_group.get("group_id") == group["group_id"]:
            continue
        other_attention_groups.append(
            {
                "group_id": action_group["group_id"],
                "title": action_group["title"],
                "recommended_action": action_group["recommended_action"],
                "targets": [
                    item["target"]
                    for item in action_group.get("targets", [])
                ],
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
            "by_namespace_type": dict(
                sorted(Counter(item["namespace_type"] for item in targets).items())
            ),
            "workflow_status_counts": dict(
                sorted(Counter(item["workflow_status"] for item in targets).items())
            ),
            "total_registered_subsurfaces": sum(
                len(item["registered_subsurfaces"])
                for item in targets
            ),
            "total_compatibility_entrypoints": sum(
                len(item["compatibility_entrypoints"])
                for item in targets
            ),
        },
        "operator_sequence": [
            "Stay inside the tool_owned_reversible batch; do not widen this review to runtime or archive-governed surfaces.",
            "Use an owning workflow before any manual filesystem mutation whenever local workflow artifacts exist.",
            "If no local workflow artifacts are present, treat the namespace as manual-review-only and keep compatibility entrypoints intact.",
            "Do not promote imported bundles into core without a separate reusable-core decision and contract update.",
        ],
        "targets": targets,
        "other_attention_groups": other_attention_groups,
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
        compat = ", ".join(
            detail["path"]
            for detail in item["compatibility_entrypoints"]
        ) or "(none)"
        print(
            "- %s | %s | %s | compat=%s | workflow=%s"
            % (
                item["target"],
                item["namespace_type"],
                item["recommended_action"],
                compat,
                item["workflow_status"],
            )
        )
    print("")
    print("other_attention_groups:")
    for group in payload["other_attention_groups"]:
        print(
            "- %s | %s | %s"
            % (
                group["title"],
                group["recommended_action"],
                ", ".join(group["targets"]) or "(none)",
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_tool_owned_review(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
