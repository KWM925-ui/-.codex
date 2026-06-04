"""Shared helpers for focused codex-home operator review surfaces."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from codex_home_policy_lib import load_json


def load_namespace_registry_and_compatibility(
    root: Path,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    registry = load_json(root / "project_assets/namespace_registry.json")
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    by_namespace_path = {
        entry["path"]: entry
        for entry in registry.get("namespaces", [])
    }
    by_entrypoint = {
        entry["path"]: entry
        for entry in manifest.get("compatibility_surfaces", [])
    }
    return by_namespace_path, by_entrypoint


def compatibility_details(
    root: Path,
    entrypoint: str,
    compat_entry: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    path = root / entrypoint
    exists = path.exists() or path.is_symlink()
    payload = {
        "path": entrypoint,
        "expected_target": compat_entry["expected_target"] if compat_entry else "",
        "exists": exists,
        "is_symlink": path.is_symlink(),
        "link_target": "",
        "resolves_to_expected": False,
    }
    if path.is_symlink():
        payload["link_target"] = os.readlink(str(path))
        if compat_entry is not None and path.exists():
            payload["resolves_to_expected"] = (
                path.resolve() == (root / compat_entry["expected_target"]).resolve()
            )
    return payload


def subsurface_status(root: Path, relative_path: str) -> Dict[str, Any]:
    path = root / relative_path
    payload = {
        "path": relative_path,
        "exists": path.exists(),
        "kind": "missing",
    }
    if not path.exists():
        return payload
    if path.is_symlink():
        payload["kind"] = "symlink"
    elif path.is_dir():
        payload["kind"] = "dir"
    else:
        payload["kind"] = "file"
    return payload


def subsurface_inventory(root: Path, relative_path: str) -> Dict[str, Any]:
    path = root / relative_path
    payload = {
        "path": relative_path,
        "exists": path.exists(),
        "inventory_state": "missing",
        "file_count": 0,
        "non_placeholder_count": 0,
        "non_placeholder_examples": [],
    }
    if not path.exists():
        return payload
    if path.is_file():
        payload["file_count"] = 1
        payload["non_placeholder_count"] = 0 if path.name == ".keep" else 1
        payload["inventory_state"] = (
            "placeholder_only" if path.name == ".keep" else "materialized"
        )
        if path.name != ".keep":
            payload["non_placeholder_examples"] = [path.name]
        return payload

    non_placeholder_examples: List[str] = []
    file_count = 0
    non_placeholder_count = 0
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        file_count += 1
        if child.name == ".keep":
            continue
        non_placeholder_count += 1
        if len(non_placeholder_examples) < 5:
            non_placeholder_examples.append(child.relative_to(path).as_posix())

    payload["file_count"] = file_count
    payload["non_placeholder_count"] = non_placeholder_count
    payload["non_placeholder_examples"] = non_placeholder_examples
    if file_count == 0:
        payload["inventory_state"] = "empty"
    elif non_placeholder_count == 0:
        payload["inventory_state"] = "placeholder_only"
    else:
        payload["inventory_state"] = "materialized"
    return payload
