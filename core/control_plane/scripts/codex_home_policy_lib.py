#!/usr/bin/env python3
"""Shared helpers for codex-home governance policy tools."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _surface_group_from_registry(
    root: Path,
    root_path: str,
    registry_relpath: str,
    selector_type: str,
) -> Optional[Tuple[str, str]]:
    registry = load_json(root / registry_relpath)
    for entry in registry.get("surfaces", []):
        if entry.get("root_path") == root_path:
            return selector_type, entry["category"]
    return None


def surface_group_from_root_path(root: Path, root_path: str) -> Tuple[str, str]:
    for registry_relpath, selector_type in (
        ("core/core_surface_registry.json", "core_category"),
        ("runtime/runtime_surface_registry.json", "runtime_category"),
        ("history/history_surface_registry.json", "history_category"),
    ):
        match = _surface_group_from_registry(
            root,
            root_path,
            registry_relpath,
            selector_type,
        )
        if match is not None:
            return match
    raise KeyError("unknown governed root surface: %s" % root_path)


def namespace_type_from_path(path: str, registry: Dict[str, Any]) -> Optional[str]:
    for namespace in registry.get("namespaces", []):
        ns_path = namespace.get("path", "")
        if path == ns_path or path.startswith(ns_path + "/"):
            return namespace.get("type")
    return None


def find_surface(
    root: Path,
    target: str,
    manifest: Dict[str, Any],
    registry: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = target.strip("/")
    for key in ("core_surfaces", "runtime_surfaces", "history_surfaces"):
        for surface in manifest.get(key, []):
            if normalized == surface["root_path"]:
                selector_type, selector = surface_group_from_root_path(
                    root,
                    surface["root_path"]
                )
                return {
                    "kind": "root_surface",
                    "root_path": surface["root_path"],
                    "selector_type": selector_type,
                    "selector": selector,
                    "source": key,
                }

    for surface in manifest.get("compatibility_surfaces", []):
        if normalized == surface["path"]:
            return {
                "kind": "compatibility_surface",
                "path": surface["path"],
                "expected_target": surface.get("expected_target", ""),
                "selector_type": "compatibility_category",
                "selector": surface.get("category", "compatibility"),
                "source": "compatibility_surfaces",
            }

    namespace_type = namespace_type_from_path(normalized, registry)
    if namespace_type is not None:
        return {
            "kind": "namespace_surface",
            "path": normalized,
            "selector_type": "namespace_type",
            "selector": namespace_type,
            "source": "project_assets",
        }

    for surface in manifest.get("compatibility_surfaces", []):
        if normalized == surface.get("expected_target", ""):
            return {
                "kind": "compatibility_target",
                "path": surface.get("expected_target", ""),
                "compatibility_entrypoint": surface["path"],
                "selector_type": "compatibility_category",
                "selector": surface.get("category", "compatibility"),
                "source": "compatibility_surfaces",
            }
    raise KeyError(
        "surface is not governed by the codex home contracts: %s" % target
    )


def index_policy(
    entries: List[Dict[str, Any]],
    selector_type: str,
    selector: str,
    value_key: str,
) -> List[str]:
    for entry in entries:
        if entry.get("selector_type") == selector_type and entry.get(
            "selector"
        ) == selector:
            return list(entry.get(value_key, []))
    return []


def explain_surface(root: Path, target: str) -> Dict[str, Any]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    namespace_registry = load_json(root / "project_assets/namespace_registry.json")
    operations = load_json(
        root / "core/control_plane/codex_home_lifecycle_operations.json"
    )
    execution_modes = load_json(
        root / "core/control_plane/codex_home_execution_modes.json"
    )

    surface = find_surface(root, target, manifest, namespace_registry)
    selector_type = surface["selector_type"]
    selector = surface["selector"]
    allowed_actions = index_policy(
        operations.get("surface_policies", []),
        selector_type,
        selector,
        "allowed_actions",
    )
    execution_mode_list = index_policy(
        execution_modes.get("selector_modes", []),
        selector_type,
        selector,
        "execution_modes",
    )

    return {
        "target": target,
        "layout_version": manifest.get("layout_version"),
        "global_rules": operations.get("global_rules", {}),
        "surface": surface,
        "allowed_actions": allowed_actions,
        "execution_modes": execution_mode_list,
    }


def diagnose_surface(root: Path, target: str) -> Dict[str, Any]:
    payload = explain_surface(root, target)
    payload["health_class"] = classify_surface_health(payload)
    payload["recommended_action"] = recommend_surface_action(payload)
    return payload


def classify_surface_health(payload: Dict[str, Any]) -> str:
    actions = set(payload.get("allowed_actions", []))
    modes = set(payload.get("execution_modes", []))
    if "manual_review_only" not in modes:
        return "policy_gap"
    if "preserve_only" in modes:
        return "stable_preserve"
    if "archive_only" in modes:
        return "archive_governed"
    if "reversible_only" in modes and "tool_only" in modes:
        return "tool_governed_reversible"
    if "reversible_only" in modes:
        return "reversible_governed"
    if "tool_only" in actions or "tool_only" in modes:
        return "tool_governed"
    return "needs_review"


def recommend_surface_action(payload: Dict[str, Any]) -> str:
    modes = set(payload.get("execution_modes", []))
    if "preserve_only" in modes:
        return "preserve_in_place"
    if "archive_only" in modes:
        return "archive_with_continuity"
    if "reversible_only" in modes and "tool_only" in modes:
        return "use_owning_tool_or_quarantine"
    if "reversible_only" in modes:
        return "quarantine_or_rotate"
    return "manual_review_required"


def governed_targets(root: Path) -> List[str]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    namespace_registry = load_json(root / "project_assets/namespace_registry.json")

    targets: List[str] = []
    for key in ("core_surfaces", "runtime_surfaces", "history_surfaces"):
        for surface in manifest.get(key, []):
            targets.append(surface["root_path"])
    for surface in manifest.get("compatibility_surfaces", []):
        path = surface.get("path")
        if isinstance(path, str) and path:
            targets.append(path)
    for namespace in namespace_registry.get("namespaces", []):
        path = namespace.get("path")
        if isinstance(path, str) and path:
            targets.append(path)
    return targets
