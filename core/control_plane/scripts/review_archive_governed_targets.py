#!/usr/bin/env python3
"""Render a continuity-safe archive planning review for archive-governed targets."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from codex_home_policy_lib import DEFAULT_ROOT, load_json
from governed_operator_review_lib import (
    compatibility_details,
    load_namespace_registry_and_compatibility,
    subsurface_status,
)
from report_codex_home_policy import build_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review the governed archive candidates as one continuity-safe planning batch.",
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


def _load_history_indexes(
    root: Path,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    registry = load_json(root / "history/history_surface_registry.json")
    snapshot_policy = load_json(root / "history/config_snapshot_policy.json")
    by_root_path = {
        entry["root_path"]: entry
        for entry in registry.get("surfaces", [])
    }
    snapshot_by_root_path = {
        entry["root_path"]: entry
        for entry in snapshot_policy.get("surfaces", [])
    }
    return by_root_path, snapshot_by_root_path


def _history_continuity_profile(entry: Dict[str, Any]) -> Dict[str, Any]:
    category = entry["category"]
    root_path = entry["root_path"]
    protected_paths = [root_path]
    mirror_path = entry.get("mirror_path", "")
    if mirror_path:
        protected_paths.append(mirror_path)

    if category == "sessions":
        return {
            "archive_bias": "index_continuity_first",
            "protected_paths": protected_paths + [
                "session_index.jsonl",
                "history/session_index.jsonl",
            ],
            "preserve_only_dependencies": ["session_index.jsonl"],
            "continuity_dependencies": [
                "Keep the session lookup/index surface stable while session history remains authoritative at the root.",
                "Do not leave the root session tree and history mirror out of sync during any future archive move.",
            ],
        }
    if category == "memory":
        return {
            "archive_bias": "generated_recall_continuity_first",
            "protected_paths": protected_paths,
            "preserve_only_dependencies": [],
            "continuity_dependencies": [
                "Treat generated memories as recall aids; archive planning must not imply they outrank fresh repo evidence.",
                "Keep the root memory store and history mirror aligned until a compatibility phase explicitly changes authority.",
            ],
        }
    if category == "shell_snapshots":
        return {
            "archive_bias": "tty_evidence_continuity_first",
            "protected_paths": protected_paths,
            "preserve_only_dependencies": [],
            "continuity_dependencies": [
                "TTY continuation evidence should remain namespaced and continuous across the root and mirror views.",
                "Do not rewrite shell evidence in place just to normalize layout.",
            ],
        }
    if category == "config_snapshot":
        return {
            "archive_bias": "frozen_evidence_first",
            "protected_paths": protected_paths,
            "preserve_only_dependencies": [],
            "continuity_dependencies": [
                "Typed config evidence must not be rewritten in place.",
                "Any future archive handling remains gated on a compatibility-preserving migration phase.",
            ],
        }
    return {
        "archive_bias": "continuity_first",
        "protected_paths": protected_paths,
        "preserve_only_dependencies": [],
        "continuity_dependencies": [
            "Preserve authoritative lookup continuity during archive planning.",
        ],
    }


def _namespace_continuity_profile(
    namespace_entry: Dict[str, Any],
) -> Dict[str, Any]:
    namespace_type = namespace_entry["type"]
    base_dependencies = [
        "Keep compatibility entrypoints stable to existing callers while archive planning stays non-destructive.",
        "Registered subsurface roots remain the continuity anchors for this namespace.",
    ]
    if namespace_type == "productization_workspace":
        return {
            "archive_bias": "live_supervisor_anchor_first",
            "continuity_dependencies": base_dependencies + [
                "The self-productization supervisor pack remains the live continuation anchor for future rounds.",
            ],
        }
    if namespace_type == "project_overlay":
        return {
            "archive_bias": "project_overlay_anchor_first",
            "continuity_dependencies": base_dependencies + [
                "Project overlays must keep operator-facing supervisor and evidence roots namespaced together.",
            ],
        }
    if namespace_type == "reference_bundle":
        return {
            "archive_bias": "provenance_first",
            "continuity_dependencies": base_dependencies + [
                "Reference mirrors should preserve provenance and bundle identity during any future archive handling.",
            ],
        }
    return {
        "archive_bias": "namespace_continuity_first",
        "continuity_dependencies": base_dependencies,
    }


def build_archive_governed_review(root: Path) -> Dict[str, Any]:
    report = build_report(root)
    operations = load_json(
        root / "core/control_plane/codex_home_lifecycle_operations.json"
    )
    history_registry, snapshot_policy = _load_history_indexes(root)
    namespace_registry, compatibility_surfaces = (
        load_namespace_registry_and_compatibility(root)
    )
    by_target = {
        item["target"]: item
        for item in report.get("surfaces", [])
    }
    archive_targets = [
        item
        for item in report.get("surfaces", [])
        if item["recommended_action"] == "archive_with_continuity"
    ]
    archive_targets.sort(
        key=lambda item: (
            item["surface"]["kind"],
            item["surface"].get("selector", ""),
            item["target"],
        )
    )

    targets: List[Dict[str, Any]] = []
    history_bucket_targets: List[Dict[str, Any]] = []
    namespace_bucket_targets: List[Dict[str, Any]] = []

    for detail in archive_targets:
        target = detail["target"]
        surface = detail["surface"]
        if surface["kind"] == "root_surface":
            history_entry = history_registry[target]
            profile = _history_continuity_profile(history_entry)
            snapshot_entry = snapshot_policy.get(target, {})
            item = {
                "target": target,
                "scope": "history_surface",
                "history_category": history_entry["category"],
                "retention_role": history_entry["retention_role"],
                "mirror_path": history_entry.get("mirror_path", ""),
                "authoritative_at_root": history_entry["authoritative_at_root"],
                "health_class": detail["health_class"],
                "recommended_action": detail["recommended_action"],
                "allowed_actions": detail["allowed_actions"],
                "execution_modes": detail["execution_modes"],
                "archive_bias": profile["archive_bias"],
                "protected_paths": profile["protected_paths"],
                "preserve_only_dependencies": profile["preserve_only_dependencies"],
                "continuity_dependencies": profile["continuity_dependencies"],
                "move_gate": snapshot_entry.get(
                    "move_gate",
                    "future compatibility phase required",
                ),
                "rewrite_policy": snapshot_entry.get("rewrite_policy", ""),
            }
            history_bucket_targets.append(item)
            targets.append(item)
            continue

        namespace_entry = namespace_registry[target]
        profile = _namespace_continuity_profile(namespace_entry)
        compatibility_entrypoints = [
            compatibility_details(
                root,
                entrypoint,
                compatibility_surfaces.get(entrypoint),
            )
            for entrypoint in namespace_entry.get("compatibility_entrypoints", [])
        ]
        registered_subsurfaces = []
        for subsurface in namespace_entry.get("subsurfaces", []):
            status = dict(subsurface)
            status.update(subsurface_status(root, subsurface["path"]))
            registered_subsurfaces.append(status)
        protected_paths = [target]
        protected_paths.extend(
            item["path"] for item in compatibility_entrypoints
        )
        protected_paths.extend(
            item["path"] for item in registered_subsurfaces
        )
        item = {
            "target": target,
            "scope": "namespace_surface",
            "namespace_id": namespace_entry["id"],
            "namespace_type": namespace_entry["type"],
            "health_class": detail["health_class"],
            "recommended_action": detail["recommended_action"],
            "allowed_actions": detail["allowed_actions"],
            "execution_modes": detail["execution_modes"],
            "archive_bias": profile["archive_bias"],
            "protected_paths": protected_paths,
            "continuity_dependencies": profile["continuity_dependencies"],
            "compatibility_entrypoints": compatibility_entrypoints,
            "registered_subsurfaces": registered_subsurfaces,
        }
        namespace_bucket_targets.append(item)
        targets.append(item)

    preserve_only_history_surfaces = []
    for detail in report.get("surfaces", []):
        surface = detail["surface"]
        if detail["recommended_action"] != "preserve_in_place":
            continue
        if surface["kind"] != "root_surface":
            continue
        if surface["selector_type"] != "history_category":
            continue
        history_entry = history_registry.get(detail["target"])
        if history_entry is None:
            continue
        preserve_only_history_surfaces.append(
            {
                "target": detail["target"],
                "history_category": history_entry["category"],
                "retention_role": history_entry["retention_role"],
                "mirror_path": history_entry.get("mirror_path", ""),
            }
        )

    planning_buckets = [
        {
            "bucket_id": "history_archive",
            "title": "History Archive Candidates",
            "planning_focus": "Protect root history lookup paths, mirrors, and typed evidence rules while planning continuity-safe archive handling.",
            "targets": [
                {
                    "target": item["target"],
                    "history_category": item["history_category"],
                    "archive_bias": item["archive_bias"],
                }
                for item in history_bucket_targets
            ],
        },
        {
            "bucket_id": "namespace_archive",
            "title": "Project Namespace Archive Candidates",
            "planning_focus": "Protect namespace anchors, registered subsurfaces, and compatibility entrypoints while planning archive moves.",
            "targets": [
                {
                    "target": item["target"],
                    "namespace_type": item["namespace_type"],
                    "archive_bias": item["archive_bias"],
                }
                for item in namespace_bucket_targets
            ],
        },
    ]

    return {
        "root": root.as_posix(),
        "layout_version": report["layout_version"],
        "group": {
            "group_id": "archive_governed",
            "title": "Archive-Governed Targets",
            "recommended_action": "archive_with_continuity",
            "operator_focus": "Plan continuity-safe archive handling without mutating authoritative paths in the current phase.",
        },
        "operator_constraints": {
            "manual_review_required": True,
            "allow_hard_delete": operations["global_rules"]["allow_hard_delete"],
            "allow_hot_path_physical_move": operations["global_rules"]["allow_hot_path_physical_move"],
            "preferred_reversible_action": operations["global_rules"]["preferred_reversible_action"],
        },
        "summary": {
            "total_targets": len(targets),
            "by_scope": dict(
                sorted(Counter(item["scope"] for item in targets).items())
            ),
            "by_archive_bias": dict(
                sorted(Counter(item["archive_bias"] for item in targets).items())
            ),
            "targets_with_mirror_continuity": sum(
                1 for item in history_bucket_targets if item["mirror_path"]
            ),
            "targets_with_compatibility_entrypoints": sum(
                1
                for item in namespace_bucket_targets
                if item["compatibility_entrypoints"]
            ),
        },
        "planning_buckets": planning_buckets,
        "operator_sequence": [
            "Stay inside the archive_governed batch; do not widen this review to runtime-reversible or tool-owned targets.",
            "Archive planning is continuity-first: protect authoritative roots, mirrors, indexes, and compatibility entrypoints before discussing any move.",
            "Do not rewrite typed evidence or normalize historical files in place merely to make the layout look cleaner.",
            "Any future archive move remains gated on a compatibility phase with updated contracts and green validation.",
        ],
        "targets": targets,
        "preserve_only_history_surfaces": preserve_only_history_surfaces,
        "other_attention_groups": [
            {
                "group_id": group["group_id"],
                "title": group["title"],
                "recommended_action": group["recommended_action"],
                "targets": [
                    item["target"]
                    for item in group.get("targets", [])
                ],
            }
            for group in report.get("action_groups", [])
        ],
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("group: %s" % payload["group"]["title"])
    print("recommended_action: %s" % payload["group"]["recommended_action"])
    print("operator_focus: %s" % payload["group"]["operator_focus"])
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("operator_constraints: %s" % json.dumps(payload["operator_constraints"], ensure_ascii=False, sort_keys=True))
    print("")
    print("planning_buckets:")
    for bucket in payload["planning_buckets"]:
        targets = ", ".join(item["target"] for item in bucket["targets"])
        print(
            "- %s | %s | %s"
            % (
                bucket["title"],
                bucket["planning_focus"],
                targets or "(none)",
            )
        )
    print("")
    print("operator_sequence:")
    for step in payload["operator_sequence"]:
        print("- %s" % step)
    print("")
    print("targets:")
    for item in payload["targets"]:
        print(
            "- %s | %s | %s | bias=%s"
            % (
                item["target"],
                item["scope"],
                item["recommended_action"],
                item["archive_bias"],
            )
        )
    print("")
    print("preserve_only_history_surfaces:")
    for item in payload["preserve_only_history_surfaces"]:
        print(
            "- %s | %s | %s"
            % (
                item["target"],
                item["history_category"],
                item["retention_role"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_archive_governed_review(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
