#!/usr/bin/env python3
"""Audit the productized ~/.codex home layout against its manifest."""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from context_firewall_lib import validate_context_firewall_contracts

DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _load_toml(text: str) -> Dict[str, Any]:
    try:
        import tomllib  # type: ignore[attr-defined]

        return tomllib.loads(text)
    except ModuleNotFoundError:
        import toml  # type: ignore[import-not-found]

        return toml.loads(text)


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


def _kind_matches(path: Path, expected: str) -> bool:
    if expected == "dir":
        return path.is_dir()
    if expected == "file":
        return path.is_file()
    raise ValueError("unsupported kind: %s" % expected)


def _check_path(
    path: Path,
    expected_kind: str,
    must_not_be_symlink: bool,
    label: str,
) -> CheckResult:
    if not path.exists():
        return CheckResult(label, False, "missing: %s" % path)
    if must_not_be_symlink and path.is_symlink():
        return CheckResult(label, False, "unexpected symlink: %s" % path)
    if not _kind_matches(path, expected_kind):
        return CheckResult(
            label,
            False,
            "expected %s at %s" % (expected_kind, path),
        )
    return CheckResult(label, True, "%s ok: %s" % (expected_kind, path))


def _check_symlink(path: Path, expected_target: str, label: str) -> CheckResult:
    if not path.exists() and not path.is_symlink():
        return CheckResult(label, False, "missing symlink: %s" % path)
    if not path.is_symlink():
        return CheckResult(label, False, "expected symlink: %s" % path)
    actual_target = os.readlink(path.as_posix())
    if actual_target != expected_target:
        return CheckResult(
            label,
            False,
            "target mismatch at %s: expected %s got %s"
            % (path, expected_target, actual_target),
        )
    if not path.resolve().exists():
        return CheckResult(label, False, "broken target: %s" % path)
    return CheckResult(label, True, "symlink ok: %s -> %s" % (path, actual_target))


def _check_same_realpath(source: Path, mirror: Path, label: str) -> CheckResult:
    if not source.exists():
        return CheckResult(label, False, "source missing: %s" % source)
    if not mirror.exists() and not mirror.is_symlink():
        return CheckResult(label, False, "mirror missing: %s" % mirror)
    if source.resolve() != mirror.resolve():
        return CheckResult(
            label,
            False,
            "realpath mismatch: %s != %s" % (source.resolve(), mirror.resolve()),
        )
    return CheckResult(label, True, "mirror resolves to source")


def _try_load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_json_document(
    path: Path,
    label: str,
) -> Tuple[List[CheckResult], Optional[Dict[str, Any]]]:
    checks = [_check_path(path, "file", True, "%s:file" % label)]
    if not path.exists():
        return checks, None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        checks.append(
            CheckResult(
                "%s:json" % label,
                False,
                "invalid json at %s: %s" % (path, exc),
            )
        )
        return checks, None
    return checks, data


def _load_list_document(
    path: Path,
    label: str,
    expected_key: str,
) -> Tuple[List[CheckResult], Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    checks, data = _load_json_document(path, label)
    if data is None:
        return checks, None, None

    value = data.get(expected_key)
    if not isinstance(value, list):
        checks.append(
            CheckResult(
                "%s:key" % label,
                False,
                "expected list key %s in %s" % (expected_key, path),
            )
        )
        return checks, data, None

    checks.append(
        CheckResult(
            "%s:key" % label,
            True,
            "registry contains list key %s with %d entries"
            % (expected_key, len(value)),
        )
    )
    return checks, data, value


def _require_dict(
    data: Dict[str, Any],
    key: str,
    label: str,
    checks: List[CheckResult],
) -> Optional[Dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, dict):
        checks.append(CheckResult(label, False, "%s must be an object" % key))
        return None
    checks.append(CheckResult(label, True, "%s present" % key))
    return value


def _require_list(
    data: Dict[str, Any],
    key: str,
    label: str,
    checks: List[CheckResult],
) -> Optional[List[Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        checks.append(CheckResult(label, False, "%s must be a list" % key))
        return None
    checks.append(CheckResult(label, True, "%s present" % key))
    return value


def _index_by(entries: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {entry[key]: entry for entry in entries}


def _compare_expected_keys(
    actual_keys: List[str],
    expected_keys: List[str],
    label: str,
    success_details: str,
) -> CheckResult:
    actual = set(actual_keys)
    expected = set(expected_keys)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    return CheckResult(
        label,
        not (missing or extra),
        success_details if not (missing or extra) else "missing=%s extra=%s" % (missing, extra),
    )


def _audit_surface_group(
    root: Path,
    entries: List[Dict[str, Any]],
    group_name: str,
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for entry in entries:
        root_path = root / entry["root_path"]
        mirror_path = root / entry["mirror_path"]
        short_name = "%s:%s" % (group_name, entry["root_path"])
        if not entry.get("required", True) and not root_path.exists():
            checks.append(
                CheckResult(
                    "%s:root" % short_name,
                    True,
                    "optional surface absent: %s" % root_path,
                )
            )
            if mirror_path.is_symlink():
                checks.append(
                    CheckResult(
                        "%s:mirror_link" % short_name,
                        True,
                        "optional mirror symlink retained: %s" % mirror_path,
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        "%s:mirror_link" % short_name,
                        True,
                        "optional mirror may remain absent when source is absent",
                    )
                )
            checks.append(
                CheckResult(
                    "%s:mirror_resolution" % short_name,
                    True,
                    "optional source absent; resolution check skipped",
                )
            )
            continue
        checks.append(
            _check_path(
                root_path,
                entry["root_kind"],
                entry.get("root_must_not_be_symlink", False),
                "%s:root" % short_name,
            )
        )
        if not entry.get("mirror_path"):
            checks.append(
                CheckResult(
                    "%s:mirror_link" % short_name,
                    True,
                    "no mirror required for %s" % root_path,
                )
            )
            checks.append(
                CheckResult(
                    "%s:mirror_resolution" % short_name,
                    True,
                    "no mirror required for %s" % root_path,
                )
            )
            continue
        checks.append(
            _check_symlink(
                mirror_path,
                entry["expected_mirror_target"],
                "%s:mirror_link" % short_name,
            )
        )
        checks.append(
            _check_same_realpath(
                root_path,
                mirror_path,
                "%s:mirror_resolution" % short_name,
            )
        )
    return checks


def _audit_core_surfaces(
    root: Path,
    entries: List[Dict[str, Any]],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for entry in entries:
        root_path = root / entry["root_path"]
        label = "core_surface:%s" % entry["root_path"]
        checks.append(
            _check_path(
                root_path,
                entry["root_kind"],
                entry.get("root_must_not_be_symlink", False),
                "%s:root" % label,
            )
        )
        canonical_path = root / entry["canonical_path"]
        checks.append(
            CheckResult(
                "%s:canonical_path" % label,
                canonical_path == root_path,
                "canonical=%s root=%s" % (canonical_path, root_path),
            )
        )
    return checks


def _check_generated_layout_version(
    path: Path,
    data: Dict[str, Any],
    manifest: Dict[str, Any],
    label: str,
) -> CheckResult:
    expected = manifest.get("layout_version")
    actual = data.get("generated_for_layout_version")
    return CheckResult(
        "%s:layout_version" % label,
        actual == expected,
        "expected=%s actual=%s path=%s" % (expected, actual, path),
    )


def _surface_categories_by_registry(root: Path) -> Dict[Tuple[str, str], List[str]]:
    categories: Dict[Tuple[str, str], List[str]] = {
        ("core", "core_category"): [],
        ("runtime", "runtime_category"): [],
        ("history", "history_category"): [],
        ("namespace", "namespace_type"): [],
    }
    core_registry = _try_load_json(root / "core/core_surface_registry.json")
    if core_registry is not None:
        categories[("core", "core_category")] = sorted(
            {surface["category"] for surface in core_registry.get("surfaces", [])}
        )

    runtime_registry = _try_load_json(root / "runtime/runtime_surface_registry.json")
    if runtime_registry is not None:
        categories[("runtime", "runtime_category")] = sorted(
            {surface["category"] for surface in runtime_registry.get("surfaces", [])}
        )

    history_registry = _try_load_json(root / "history/history_surface_registry.json")
    if history_registry is not None:
        categories[("history", "history_category")] = sorted(
            {surface["category"] for surface in history_registry.get("surfaces", [])}
        )

    namespace_registry = _try_load_json(root / "project_assets/namespace_registry.json")
    if namespace_registry is not None:
        categories[("namespace", "namespace_type")] = sorted(
            {namespace["type"] for namespace in namespace_registry.get("namespaces", [])}
        )
    return categories


def _audit_selector_coverage(
    root: Path,
    policy_entries: Dict[Tuple[str, str], Dict[str, Any]],
    label: str,
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for (scope, selector_type), selectors in _surface_categories_by_registry(root).items():
        for selector in selectors:
            checks.append(
                CheckResult(
                    "%s:coverage:%s:%s" % (label, scope, selector),
                    (selector_type, selector) in policy_entries,
                    "covered=%s" % ((selector_type, selector) in policy_entries),
                )
            )
    return checks


def _audit_namespace_registry(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    registry_path = root / "project_assets/namespace_registry.json"
    checks, data, registry_namespaces = _load_list_document(
        registry_path,
        "namespace_registry",
        "namespaces",
    )
    if data is None or registry_namespaces is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            registry_path,
            data,
            manifest,
            "namespace_registry",
        )
    )
    manifest_namespaces = manifest.get("project_namespaces", [])
    registry_by_id = _index_by(registry_namespaces, "id")
    manifest_by_id = _index_by(manifest_namespaces, "id")
    checks.append(
        _compare_expected_keys(
            list(registry_by_id.keys()),
            list(manifest_by_id.keys()),
            "namespace_registry:ids",
            "namespace ids match manifest",
        )
    )

    for namespace_id, manifest_entry in manifest_by_id.items():
        registry_entry = registry_by_id.get(namespace_id)
        if registry_entry is None:
            continue
        manifest_path = manifest_entry["path"]
        registry_path_value = registry_entry.get("path")
        checks.append(
            CheckResult(
                "namespace_registry:path:%s" % namespace_id,
                registry_path_value == manifest_path,
                "manifest=%s registry=%s" % (manifest_path, registry_path_value),
            )
        )
        registry_subsurfaces = {
            entry["path"] for entry in registry_entry.get("subsurfaces", [])
        }
        manifest_required_paths = set(manifest_entry.get("required_paths", []))
        missing_subsurfaces = sorted(manifest_required_paths - registry_subsurfaces)
        if missing_subsurfaces:
            checks.append(
                CheckResult(
                    "namespace_registry:subsurfaces:%s" % namespace_id,
                    False,
                    "missing subsurfaces: %s" % missing_subsurfaces,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "namespace_registry:subsurfaces:%s" % namespace_id,
                    True,
                    "all manifest required paths registered",
                )
            )

    return checks


def _compare_surface_registry(
    registry_entries: List[Dict[str, Any]],
    manifest_entries: List[Dict[str, Any]],
    group_name: str,
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    registry_by_root = _index_by(registry_entries, "root_path")
    manifest_by_root = _index_by(manifest_entries, "root_path")
    checks.append(
        _compare_expected_keys(
            list(registry_by_root.keys()),
            list(manifest_by_root.keys()),
            "%s_registry:root_paths" % group_name,
            "registry root paths match manifest",
        )
    )

    for root_path, manifest_entry in manifest_by_root.items():
        registry_entry = registry_by_root.get(root_path)
        if registry_entry is None:
            continue
        checks.append(
            CheckResult(
                "%s_registry:mirror:%s" % (group_name, root_path),
                registry_entry.get("mirror_path") == manifest_entry["mirror_path"],
                "manifest=%s registry=%s"
                % (manifest_entry["mirror_path"], registry_entry.get("mirror_path")),
            )
        )
        checks.append(
            CheckResult(
                "%s_registry:required:%s" % (group_name, root_path),
                bool(registry_entry.get("required", True))
                == bool(manifest_entry.get("required", True)),
                "manifest=%s registry=%s"
                % (
                    bool(manifest_entry.get("required", True)),
                    bool(registry_entry.get("required", True)),
                ),
            )
        )
    return checks


def _audit_surface_registry(
    root: Path,
    manifest: Dict[str, Any],
    registry_relpath: str,
    expected_key: str,
    manifest_key: str,
    group_name: str,
) -> List[CheckResult]:
    registry_path = root / registry_relpath
    checks, data, registry_entries = _load_list_document(
        registry_path,
        "%s_registry" % group_name,
        expected_key,
    )
    if data is None or registry_entries is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            registry_path,
            data,
            manifest,
            "%s_registry" % group_name,
        )
    )
    manifest_entries = manifest.get(manifest_key, [])
    checks.extend(
        _compare_surface_registry(
            registry_entries,
            manifest_entries,
            group_name,
        )
    )
    return checks


def _audit_core_surface_registry(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    registry_path = root / "core/core_surface_registry.json"
    checks, data, registry_entries = _load_list_document(
        registry_path,
        "core_registry",
        "surfaces",
    )
    if data is None or registry_entries is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            registry_path,
            data,
            manifest,
            "core_registry",
        )
    )
    manifest_entries = manifest.get("core_surfaces", [])
    registry_by_root = _index_by(registry_entries, "root_path")
    manifest_by_root = _index_by(manifest_entries, "root_path")
    checks.append(
        _compare_expected_keys(
            list(registry_by_root.keys()),
            list(manifest_by_root.keys()),
            "core_registry:root_paths",
            "registry root paths match manifest",
        )
    )

    for root_path, manifest_entry in manifest_by_root.items():
        registry_entry = registry_by_root.get(root_path)
        if registry_entry is None:
            continue
        checks.append(
            CheckResult(
                "core_registry:canonical:%s" % root_path,
                registry_entry.get("canonical_path") == manifest_entry["canonical_path"],
                "manifest=%s registry=%s"
                % (
                    manifest_entry["canonical_path"],
                    registry_entry.get("canonical_path"),
                ),
            )
        )
        checks.append(
            CheckResult(
                "core_registry:required:%s" % root_path,
                bool(registry_entry.get("required", True)) is True,
                "registry required=%s" % bool(registry_entry.get("required", True)),
            )
        )
    return checks


def _audit_history_snapshot_policy(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    policy_path = root / "history/config_snapshot_policy.json"
    checks, data, registry_entries = _load_list_document(
        policy_path,
        "history_snapshot_policy",
        "surfaces",
    )
    if data is None or registry_entries is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            policy_path,
            data,
            manifest,
            "history_snapshot_policy",
        )
    )
    manifest_entries = manifest.get("history_snapshot_surfaces", [])
    registry_by_root = _index_by(registry_entries, "root_path")
    manifest_by_root = _index_by(manifest_entries, "root_path")
    checks.append(
        _compare_expected_keys(
            list(registry_by_root.keys()),
            list(manifest_by_root.keys()),
            "history_snapshot_policy:root_paths",
            "snapshot policy root paths match manifest",
        )
    )

    for root_path, manifest_entry in manifest_by_root.items():
        registry_entry = registry_by_root.get(root_path)
        if registry_entry is None:
            continue
        for key in ("snapshot_kind", "retention_role", "mirror_path", "required"):
            checks.append(
                CheckResult(
                    "history_snapshot_policy:%s:%s" % (key, root_path),
                    registry_entry.get(key) == manifest_entry.get(key),
                    "manifest=%s registry=%s"
                    % (manifest_entry.get(key), registry_entry.get(key)),
                )
            )
    return checks


def _audit_migration_candidates(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    contract_path = root / "core/control_plane/codex_home_migration_candidates.json"
    checks, data, candidates = _load_list_document(
        contract_path,
        "migration_candidates",
        "candidates",
    )
    if data is None or candidates is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            contract_path,
            data,
            manifest,
            "migration_candidates",
        )
    )

    manifest_candidates = manifest.get("migration_candidates", [])
    manifest_by_id = _index_by(manifest_candidates, "id")
    contract_by_id = _index_by(candidates, "id")
    checks.append(
        _compare_expected_keys(
            list(contract_by_id.keys()),
            list(manifest_by_id.keys()),
            "migration_candidates:ids",
            "migration candidate ids match manifest",
        )
    )

    required_keys = _migration_candidate_required_keys()
    selector_types = set(manifest.get("execution_mode_policy", {}).get("required_selector_types", []))
    namespace_by_path, compatibility_manifest = _migration_candidate_indexes(root, manifest)

    for candidate_id, manifest_entry in manifest_by_id.items():
        contract_entry = contract_by_id.get(candidate_id)
        if contract_entry is None:
            continue
        checks.extend(
            _audit_migration_candidate(
                root,
                candidate_id,
                manifest_entry,
                contract_entry,
                required_keys,
                selector_types,
                namespace_by_path,
                compatibility_manifest,
            )
        )

    return checks


def _migration_candidate_required_keys() -> set:
    return {
        "id",
        "selector_type",
        "selector",
        "target",
        "candidate_kind",
        "phase",
        "scope_root",
        "compatibility_entrypoints",
        "protected_paths",
        "preconditions",
        "planned_steps",
        "forbidden_actions",
        "validation_commands",
    }


def _migration_candidate_indexes(
    root: Path,
    manifest: Dict[str, Any],
) -> Tuple[Dict[Any, Dict[str, Any]], Dict[Any, Dict[str, Any]]]:
    namespace_registry = _try_load_json(root / "project_assets/namespace_registry.json") or {}
    namespace_by_path = {
        entry.get("path"): entry
        for entry in namespace_registry.get("namespaces", [])
    }
    compatibility_manifest = {
        entry.get("path"): entry
        for entry in manifest.get("compatibility_surfaces", [])
    }
    return namespace_by_path, compatibility_manifest


def _audit_migration_candidate(
    root: Path,
    candidate_id: str,
    manifest_entry: Dict[str, Any],
    contract_entry: Dict[str, Any],
    required_keys: set,
    selector_types: set,
    namespace_by_path: Dict[Any, Dict[str, Any]],
    compatibility_manifest: Dict[Any, Dict[str, Any]],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    checks.extend(
        _audit_migration_candidate_identity(
            candidate_id,
            manifest_entry,
            contract_entry,
            required_keys,
            selector_types,
            namespace_by_path,
        )
    )
    checks.extend(_audit_migration_candidate_list_fields(candidate_id, contract_entry))

    target = contract_entry.get("target")
    scope_root = contract_entry.get("scope_root", "")
    protected_paths = set(contract_entry.get("protected_paths", []))
    checks.extend(
        _audit_migration_candidate_compatibility(
            root,
            candidate_id,
            scope_root,
            protected_paths,
            contract_entry.get("compatibility_entrypoints", []),
            compatibility_manifest,
        )
    )
    checks.extend(
        _audit_migration_candidate_protection(
            candidate_id,
            target,
            scope_root,
            protected_paths,
        )
    )
    return checks


def _audit_migration_candidate_identity(
    candidate_id: str,
    manifest_entry: Dict[str, Any],
    contract_entry: Dict[str, Any],
    required_keys: set,
    selector_types: set,
    namespace_by_path: Dict[Any, Dict[str, Any]],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    missing_keys = sorted(required_keys - set(contract_entry.keys()))
    checks.append(
        CheckResult(
            "migration_candidates:keys:%s" % candidate_id,
            not missing_keys,
            "missing_keys=%s" % missing_keys,
        )
    )

    for key in (
        "selector_type",
        "selector",
        "target",
        "candidate_kind",
        "phase",
        "scope_root",
    ):
        checks.append(
            CheckResult(
                "migration_candidates:%s:%s" % (key, candidate_id),
                contract_entry.get(key) == manifest_entry.get(key),
                "manifest=%s contract=%s"
                % (manifest_entry.get(key), contract_entry.get(key)),
            )
        )

    selector_type = contract_entry.get("selector_type")
    checks.append(
        CheckResult(
            "migration_candidates:selector_type:%s" % candidate_id,
            selector_type in selector_types,
            "selector_type=%s allowed=%s" % (selector_type, sorted(selector_types)),
        )
    )

    target = contract_entry.get("target")
    scope_root = contract_entry.get("scope_root", "")
    checks.append(
        CheckResult(
            "migration_candidates:target:%s" % candidate_id,
            namespace_by_path.get(target) is not None,
            "target=%s" % target,
        )
    )
    checks.append(
        CheckResult(
            "migration_candidates:scope_root:%s" % candidate_id,
            isinstance(scope_root, str)
            and bool(scope_root)
            and (scope_root == target or scope_root.startswith(target + "/")),
            "target=%s scope_root=%s" % (target, scope_root),
        )
    )
    return checks


def _audit_migration_candidate_list_fields(
    candidate_id: str,
    contract_entry: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for list_key in (
        "compatibility_entrypoints",
        "protected_paths",
        "preconditions",
        "planned_steps",
        "forbidden_actions",
        "validation_commands",
    ):
        value = contract_entry.get(list_key)
        checks.append(
            CheckResult(
                "migration_candidates:%s_type:%s" % (list_key, candidate_id),
                isinstance(value, list) and bool(value),
                "%s=%s" % (list_key, value),
            )
        )
    return checks


def _audit_migration_candidate_compatibility(
    root: Path,
    candidate_id: str,
    scope_root: Any,
    protected_paths: set,
    compatibility_entrypoints: Any,
    compatibility_manifest: Dict[Any, Dict[str, Any]],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    if not isinstance(compatibility_entrypoints, list):
        return checks
    for entrypoint in compatibility_entrypoints:
        manifest_compat = compatibility_manifest.get(entrypoint)
        checks.append(
            CheckResult(
                "migration_candidates:compat_registered:%s:%s"
                % (candidate_id, entrypoint),
                manifest_compat is not None,
                "entrypoint=%s manifest_present=%s"
                % (entrypoint, manifest_compat is not None),
            )
        )
        if manifest_compat is None:
            continue
        checks.append(
            CheckResult(
                "migration_candidates:compat_target:%s:%s"
                % (candidate_id, entrypoint),
                manifest_compat.get("expected_target") == scope_root,
                "expected_target=%s scope_root=%s"
                % (manifest_compat.get("expected_target"), scope_root),
            )
        )
        checks.append(
            CheckResult(
                "migration_candidates:compat_protected:%s:%s"
                % (candidate_id, entrypoint),
                entrypoint in protected_paths,
                "protected_paths=%s" % sorted(protected_paths),
            )
        )
        checks.append(
            _check_symlink(
                root / entrypoint,
                manifest_compat["expected_target"],
                "migration_candidates:compat_resolution:%s:%s"
                % (candidate_id, entrypoint),
            )
        )
    return checks


def _audit_migration_candidate_protection(
    candidate_id: str,
    target: Any,
    scope_root: Any,
    protected_paths: set,
) -> List[CheckResult]:
    return [
        CheckResult(
            "migration_candidates:scope_root_protected:%s" % candidate_id,
            scope_root in protected_paths,
            "protected_paths=%s" % sorted(protected_paths),
        ),
        CheckResult(
            "migration_candidates:target_protected:%s" % candidate_id,
            target in protected_paths,
            "protected_paths=%s" % sorted(protected_paths),
        ),
    ]


def _audit_context_firewall(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    return [
        CheckResult(check.name, check.ok, check.details)
        for check in validate_context_firewall_contracts(root, manifest)
    ]


def _audit_runtime_class_policy(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    policy_path = root / "runtime/runtime_class_policy.json"
    checks, data, registry_entries = _load_list_document(
        policy_path,
        "runtime_class_policy",
        "allowed_categories",
    )
    if data is None or registry_entries is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            policy_path,
            data,
            manifest,
            "runtime_class_policy",
        )
    )
    manifest_entries = manifest.get("runtime_category_policy", [])
    registry_by_category = _index_by(registry_entries, "category")
    manifest_by_category = _index_by(manifest_entries, "category")
    checks.append(
        _compare_expected_keys(
            list(registry_by_category.keys()),
            list(manifest_by_category.keys()),
            "runtime_class_policy:categories",
            "runtime categories match manifest",
        )
    )

    for category, manifest_entry in manifest_by_category.items():
        registry_entry = registry_by_category.get(category)
        if registry_entry is None:
            continue
        for key in ("mirror_required", "allow_optional_root", "retention_class"):
            checks.append(
                CheckResult(
                    "runtime_class_policy:%s:%s" % (key, category),
                    registry_entry.get(key) == manifest_entry.get(key),
                    "manifest=%s registry=%s"
                    % (manifest_entry.get(key), registry_entry.get(key)),
                )
            )

    surface_registry_path = root / "runtime/runtime_surface_registry.json"
    surface_registry = _try_load_json(surface_registry_path)
    if surface_registry is not None:
        for surface in surface_registry.get("surfaces", []):
            category = surface.get("category")
            policy = registry_by_category.get(category)
            label = "runtime_class_policy:surface:%s" % surface.get("root_path")
            if policy is None:
                checks.append(
                    CheckResult(
                        label,
                        False,
                        "no runtime class policy for category %s" % category,
                    )
                )
                continue
            mirror_required = bool(policy.get("mirror_required"))
            has_mirror = bool(surface.get("mirror_path"))
            allow_optional_root = bool(policy.get("allow_optional_root"))
            is_optional = not bool(surface.get("required", True))
            checks.append(
                CheckResult(
                    "%s:mirror_requirement" % label,
                    has_mirror == mirror_required,
                    "category=%s mirror_required=%s mirror_path=%s"
                    % (category, mirror_required, surface.get("mirror_path", "")),
                )
            )
            checks.append(
                CheckResult(
                    "%s:optional_root" % label,
                    (not is_optional) or allow_optional_root,
                    "category=%s optional=%s allow_optional_root=%s"
                    % (category, is_optional, allow_optional_root),
                )
            )
    return checks


def _audit_operations_policy(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    policy_path = root / "core/control_plane/codex_home_lifecycle_operations.json"
    checks, data = _load_json_document(policy_path, "operations_policy")
    if data is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            policy_path,
            data,
            manifest,
            "operations_policy",
        )
    )
    global_rules = _require_dict(
        data,
        "global_rules",
        "operations_policy:global_rules",
        checks,
    )
    if global_rules is None:
        return checks

    action_classes = _require_list(
        data,
        "action_classes",
        "operations_policy:action_classes",
        checks,
    )
    if action_classes is None:
        return checks

    surface_policies = _require_list(
        data,
        "surface_policies",
        "operations_policy:surface_policies",
        checks,
    )
    if surface_policies is None:
        return checks

    policy_manifest = manifest.get("operations_policy", {})
    checks.extend(_audit_required_mapping_keys(global_rules, policy_manifest, "operations_policy"))

    action_names = {entry.get("action") for entry in action_classes}
    checks.extend(
        _audit_required_named_entries(
            action_names,
            policy_manifest.get("required_action_classes", []),
            "operations_policy",
            "action",
        )
    )

    policy_entries, selector_types, policy_checks = _audit_selector_action_entries(
        surface_policies,
        action_names,
        "operations_policy",
        "allowed_actions",
        "known_actions",
    )
    checks.extend(policy_checks)
    checks.extend(
        _audit_required_selector_types(
            selector_types,
            policy_manifest.get("required_selector_types", []),
            "operations_policy",
        )
    )

    checks.extend(_audit_selector_coverage(root, policy_entries, "operations_policy"))
    checks.extend(_audit_operations_global_safety_rules(global_rules))
    return checks


def _audit_required_mapping_keys(
    data: Dict[str, Any],
    policy_manifest: Dict[str, Any],
    label: str,
) -> List[CheckResult]:
    return [
        CheckResult(
            "%s:global_rule:%s" % (label, key),
            key in data,
            "present=%s" % (key in data),
        )
        for key in policy_manifest.get("global_rule_keys", [])
    ]


def _audit_required_named_entries(
    present_names: set,
    required_names: List[str],
    label: str,
    item_label: str,
) -> List[CheckResult]:
    return [
        CheckResult(
            "%s:%s:%s" % (label, item_label, name),
            name in present_names,
            "present=%s" % (name in present_names),
        )
        for name in required_names
    ]


def _audit_selector_action_entries(
    entries: List[Any],
    known_names: set,
    label: str,
    list_key: str,
    known_label: str,
) -> Tuple[Dict[Tuple[Any, Any], Any], set, List[CheckResult]]:
    checks: List[CheckResult] = []
    policy_entries: Dict[Tuple[Any, Any], Any] = {}
    selector_types = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        selector_type = entry.get("selector_type")
        selector = entry.get("selector")
        selector_types.add(selector_type)
        policy_entries[(selector_type, selector)] = entry
        values = entry.get(list_key, [])
        checks.append(
            CheckResult(
                "%s:%s:%s:%s" % (label, list_key, selector_type, selector),
                isinstance(values, list) and bool(values),
                "%s=%s" % (list_key, values),
            )
        )
        if isinstance(values, list):
            unknown = sorted(set(values) - known_names)
            unknown_detail_key = (
                "unknown_actions"
                if known_label == "known_actions"
                else "unknown_%s" % list_key
            )
            checks.append(
                CheckResult(
                    "%s:%s:%s:%s" % (label, known_label, selector_type, selector),
                    not unknown,
                    "%s=%s" % (unknown_detail_key, unknown),
                )
            )
    return policy_entries, selector_types, checks


def _audit_required_selector_types(
    selector_types: set,
    required_selector_types: List[str],
    label: str,
) -> List[CheckResult]:
    return [
        CheckResult(
            "%s:selector_type:%s" % (label, selector_type),
            selector_type in selector_types,
            "present=%s" % (selector_type in selector_types),
        )
        for selector_type in required_selector_types
    ]


def _audit_operations_global_safety_rules(
    global_rules: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    if global_rules.get("allow_hard_delete") is not False:
        checks.append(
            CheckResult(
                "operations_policy:allow_hard_delete",
                False,
                "expected false got %s" % global_rules.get("allow_hard_delete"),
            )
        )
    else:
        checks.append(
            CheckResult(
                "operations_policy:allow_hard_delete",
                True,
                "hard delete disabled",
            )
        )

    if global_rules.get("allow_hot_path_physical_move") is not False:
        checks.append(
            CheckResult(
                "operations_policy:allow_hot_path_physical_move",
                False,
                "expected false got %s" % global_rules.get("allow_hot_path_physical_move"),
            )
        )
    else:
        checks.append(
            CheckResult(
                "operations_policy:allow_hot_path_physical_move",
                True,
                "hot-path physical move disabled",
            )
        )
    return checks


def _audit_execution_mode_policy(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    policy_path = root / "core/control_plane/codex_home_execution_modes.json"
    checks, data = _load_json_document(policy_path, "execution_mode_policy")
    if data is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            policy_path,
            data,
            manifest,
            "execution_mode_policy",
        )
    )

    mode_classes = _require_list(
        data,
        "mode_classes",
        "execution_mode_policy:mode_classes",
        checks,
    )
    if mode_classes is None:
        return checks

    selector_modes = _require_list(
        data,
        "selector_modes",
        "execution_mode_policy:selector_modes",
        checks,
    )
    if selector_modes is None:
        return checks

    policy_manifest = manifest.get("execution_mode_policy", {})
    mode_names = {entry.get("mode") for entry in mode_classes}
    checks.extend(
        _audit_required_named_entries(
            mode_names,
            policy_manifest.get("required_mode_classes", []),
            "execution_mode_policy",
            "mode",
        )
    )

    selector_entries, selector_types, selector_checks = _audit_execution_selector_modes(
        selector_modes,
        mode_names,
    )
    checks.extend(selector_checks)
    checks.extend(
        _audit_required_selector_types(
            selector_types,
            policy_manifest.get("required_selector_types", []),
            "execution_mode_policy",
        )
    )

    checks.extend(
        _audit_selector_coverage(root, selector_entries, "execution_mode_policy")
    )

    return checks


def _audit_execution_selector_modes(
    selector_modes: List[Any],
    mode_names: set,
) -> Tuple[Dict[Tuple[Any, Any], Any], set, List[CheckResult]]:
    checks: List[CheckResult] = []
    selector_entries: Dict[Tuple[Any, Any], Any] = {}
    selector_types = set()
    for entry in selector_modes:
        if not isinstance(entry, dict):
            continue
        selector_type = entry.get("selector_type")
        selector = entry.get("selector")
        selector_types.add(selector_type)
        selector_entries[(selector_type, selector)] = entry
        execution_modes = entry.get("execution_modes", [])
        checks.append(
            CheckResult(
                "execution_mode_policy:execution_modes:%s:%s"
                % (selector_type, selector),
                isinstance(execution_modes, list) and bool(execution_modes),
                "execution_modes=%s" % execution_modes,
            )
        )
        if isinstance(execution_modes, list):
            checks.extend(
                _audit_execution_mode_values(
                    selector_type,
                    selector,
                    execution_modes,
                    mode_names,
                )
            )
    return selector_entries, selector_types, checks


def _audit_execution_mode_values(
    selector_type: Any,
    selector: Any,
    execution_modes: List[Any],
    mode_names: set,
) -> List[CheckResult]:
    unknown_modes = sorted(set(execution_modes) - mode_names)
    base_modes = {
        mode
        for mode in execution_modes
        if mode in {"preserve_only", "reversible_only", "archive_only"}
    }
    return [
        CheckResult(
            "execution_mode_policy:known_modes:%s:%s" % (selector_type, selector),
            not unknown_modes,
            "unknown_modes=%s" % unknown_modes,
        ),
        CheckResult(
            "execution_mode_policy:base_mode:%s:%s" % (selector_type, selector),
            len(base_modes) == 1,
            "base_modes=%s" % sorted(base_modes),
        ),
    ]


def _audit_namespace_standards(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    standards_path = root / "project_assets/namespace_standards.json"
    checks, data, standards = _load_list_document(
        standards_path,
        "namespace_standards",
        "allowed_namespace_types",
    )
    if data is None or standards is None:
        return checks

    checks.append(
        _check_generated_layout_version(
            standards_path,
            data,
            manifest,
            "namespace_standards",
        )
    )
    standards_by_type = {entry["type"]: entry for entry in standards}
    registry_path = root / "project_assets/namespace_registry.json"
    if not registry_path.exists():
        checks.append(
            CheckResult(
                "namespace_standards:registry_dependency",
                False,
                "namespace registry missing: %s" % registry_path,
            )
        )
        return checks

    registry = _try_load_json(registry_path)
    if registry is None:
        checks.append(
            CheckResult(
                "namespace_standards:registry_dependency",
                False,
                "namespace registry unreadable: %s" % registry_path,
            )
        )
        return checks
    for namespace in registry.get("namespaces", []):
        namespace_type = namespace.get("type")
        namespace_path = namespace.get("path", "")
        namespace_name = namespace.get("id", "<unknown>")
        standard = standards_by_type.get(namespace_type)
        checks.append(
            CheckResult(
                "namespace_standards:type:%s" % namespace_name,
                standard is not None,
                "namespace type=%s" % namespace_type,
            )
        )
        if standard is None:
            continue

        compatibility_entrypoints = namespace.get("compatibility_entrypoints", [])
        allow_compat = bool(standard.get("allow_compatibility_entrypoints", False))
        checks.append(
            CheckResult(
                "namespace_standards:compat:%s" % namespace_name,
                allow_compat or not compatibility_entrypoints,
                "allow=%s entrypoints=%s" % (allow_compat, compatibility_entrypoints),
            )
        )

        subsurface_paths = [entry["path"] for entry in namespace.get("subsurfaces", [])]
        for required_suffix in standard.get("required_subsurface_prefixes", []):
            if namespace_type == "productization_workspace":
                expected_path = required_suffix
                ok = expected_path in subsurface_paths
            else:
                expected_path = namespace_path + "/" + required_suffix
                ok = any(path == expected_path or path.startswith(expected_path + "/") for path in subsurface_paths)
            checks.append(
                CheckResult(
                    "namespace_standards:required:%s:%s"
                    % (namespace_name, required_suffix),
                    ok,
                    "expected=%s subsurfaces=%s" % (expected_path, subsurface_paths),
                )
            )
    return checks


def _audit_config(config_path: Path, expectations: Dict[str, Any]) -> List[CheckResult]:
    checks: List[CheckResult] = [
        _check_path(config_path, "file", True, "config:file"),
    ]
    if not config_path.exists():
        return checks

    data = _load_toml(config_path.read_text(encoding="utf-8"))
    projects = data.get("projects", {})
    keys = sorted(projects.keys())
    checks.append(
        CheckResult(
            "config:trusted_projects_portable",
            isinstance(projects, dict),
            "trusted project entries=%d; exact local paths are intentionally not governed"
            % len(keys),
        )
    )

    forbidden_exact = expectations.get("forbidden_exact_project_keys", [])
    exact_hits = [key for key in keys if key in forbidden_exact]
    if exact_hits:
        checks.append(
            CheckResult(
                "config:forbidden_exact_project_keys",
                False,
                "forbidden keys present: %s" % exact_hits,
            )
        )
    else:
        checks.append(
            CheckResult(
                "config:forbidden_exact_project_keys",
                True,
                "no forbidden exact project keys",
            )
        )

    forbidden_prefixes = expectations.get("forbidden_project_key_prefixes", [])
    prefix_hits = [
        key for key in keys if any(key.startswith(prefix) for prefix in forbidden_prefixes)
    ]
    if prefix_hits:
        checks.append(
            CheckResult(
                "config:forbidden_project_key_prefixes",
                False,
                "forbidden prefixed keys present: %s" % prefix_hits,
            )
        )
    else:
        checks.append(
            CheckResult(
                "config:forbidden_project_key_prefixes",
                True,
                "no forbidden prefixed project keys",
            )
        )
    checks.extend(_audit_config_plain_language_contract(data))
    return checks


def _audit_config_plain_language_contract(data: Dict[str, Any]) -> List[CheckResult]:
    instructions = data.get("developer_instructions", "")
    if not isinstance(instructions, str):
        instructions = ""
    plain_language_phrases = [
        "说人话",
        "clear Chinese",
        "cause/effect",
        "English process labels",
        "control-plane jargon",
    ]
    clarification_phrases = [
        "clarifying questions",
        "goal, constraints, success criteria, or risk tolerance",
        "do not guess the user's intent",
        "stop and ask",
        "do not replace clarification",
        "low-risk refactor",
        "When stopping to clarify",
        "no files were changed",
        "no substantive action was taken",
    ]
    evidence_phrases = [
        "memory, experience, or plausibility",
        "fresh evidence",
        "inference, assumption, or uncertainty",
    ]
    checks = []
    missing = [phrase for phrase in plain_language_phrases if phrase not in instructions]
    checks.append(
        CheckResult(
            "config:plain_language_developer_instruction",
            not missing,
            "missing=%s" % missing,
        )
    )
    missing = [phrase for phrase in clarification_phrases if phrase not in instructions]
    checks.append(
        CheckResult(
            "config:clarify_before_substantive_work",
            not missing,
            "missing=%s" % missing,
        )
    )
    missing = [phrase for phrase in evidence_phrases if phrase not in instructions]
    checks.append(
        CheckResult(
            "config:evidence_before_conclusion",
            not missing,
            "missing=%s" % missing,
        )
    )
    return checks


def _audit_root_surface_index(
    root: Path,
    index_path: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks, data = _load_json_document(index_path, "root_index")
    if data is None:
        return checks

    entries = data.get("root_surfaces", [])
    optional_surface_paths = _optional_manifest_surface_paths(manifest)
    checks.append(_audit_root_index_coverage(root, entries, optional_surface_paths))
    checks.extend(_audit_root_index_entries(root, entries, optional_surface_paths))
    checks.extend(_audit_root_index_manifest_alignment(entries, manifest))
    return checks


def _optional_manifest_surface_paths(manifest: Dict[str, Any]) -> set:
    return {
        surface["root_path"]
        for key in ("runtime_surfaces", "history_surfaces")
        for surface in manifest.get(key, [])
        if not surface.get("required", True)
    }


def _audit_root_index_coverage(
    root: Path,
    entries: List[Dict[str, Any]],
    optional_surface_paths: set,
) -> CheckResult:
    indexed_paths = {entry["path"] for entry in entries}
    ignored_paths = {"manifest.json"}
    actual_paths = {path.name for path in root.iterdir() if path.name not in ignored_paths}
    missing_from_index = sorted(actual_paths - indexed_paths)
    stale_required_in_index = sorted(
        path for path in indexed_paths - actual_paths if path not in optional_surface_paths
    )
    stale_optional_in_index = sorted(
        path for path in indexed_paths - actual_paths if path in optional_surface_paths
    )
    if missing_from_index or stale_required_in_index:
        return CheckResult(
            "root_index:coverage",
            False,
            "missing_from_index=%s stale_required_in_index=%s stale_optional_in_index=%s"
            % (missing_from_index, stale_required_in_index, stale_optional_in_index),
        )
    return CheckResult(
        "root_index:coverage",
        True,
        "root surface index covers current top-level paths; stale_optional_in_index=%s"
        % stale_optional_in_index,
    )


def _audit_root_index_entries(
    root: Path,
    entries: List[Dict[str, Any]],
    optional_surface_paths: set,
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for entry in entries:
        path = root / entry["path"]
        label = "root_index:%s" % entry["path"]
        expected_kind = entry["kind"]
        if entry["path"] in optional_surface_paths and not path.exists():
            checks.append(
                CheckResult(
                    label,
                    True,
                    "optional indexed surface absent: %s" % path,
                )
            )
            continue
        if expected_kind == "symlink":
            checks.append(_audit_indexed_symlink(path, label))
        else:
            checks.append(_check_path(path, expected_kind, False, label))
    return checks


def _audit_indexed_symlink(path: Path, label: str) -> CheckResult:
    if not path.is_symlink():
        return CheckResult(label, False, "expected symlink: %s" % path)
    return CheckResult(label, True, "symlink indexed")


def _audit_root_index_manifest_alignment(
    entries: List[Dict[str, Any]],
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    manifest_paths_by_layer = {
        "core": {surface.get("root_path") for surface in manifest.get("core_surfaces", [])},
        "runtime": {surface.get("root_path") for surface in manifest.get("runtime_surfaces", [])},
        "history": {surface.get("root_path") for surface in manifest.get("history_surfaces", [])},
    }
    for layer, manifest_paths in manifest_paths_by_layer.items():
        missing_from_manifest = sorted(
            entry["path"]
            for entry in entries
            if entry.get("layer") == layer
            and entry.get("status") == "authoritative_root"
            and entry.get("path") not in manifest_paths
        )
        checks.append(
            CheckResult(
                "root_index:%s_manifest_alignment" % layer,
                not missing_from_manifest,
                (
                    "all indexed authoritative %s roots are manifest surfaces"
                    % layer
                )
                if not missing_from_manifest
                else "missing_from_manifest=%s" % missing_from_manifest,
            )
        )
    return checks


def audit_home(root: Path, manifest: Dict[str, Any], config_path: Path) -> List[CheckResult]:
    checks: List[CheckResult] = []
    root_index_path = root / "core/control_plane/codex_home_surface_index.json"
    manifest_root_value = str(manifest["home_root"])
    manifest_root = Path(manifest_root_value).expanduser().resolve()
    portable_root = manifest_root_value in {"~/.codex", "$CODEX_HOME", "${CODEX_HOME}"}
    checks.append(
        CheckResult(
            "manifest:home_root",
            portable_root or manifest_root == root.resolve(),
            "manifest root=%s audit root=%s portable=%s"
            % (manifest_root_value, root.resolve(), portable_root),
        )
    )
    checks.extend(_audit_generated_contract_files(root, manifest))
    checks.extend(_audit_layers(root, manifest))
    checks.extend(_audit_core_surfaces(root, manifest.get("core_surfaces", [])))
    checks.extend(_audit_required_files(root, manifest.get("required_docs", []), "doc"))
    checks.extend(_audit_required_files(root, manifest.get("required_scripts", []), "script"))
    checks.extend(_audit_compatibility_surfaces(root, manifest))
    checks.extend(
        _audit_surface_group(root, manifest.get("runtime_surfaces", []), "runtime")
    )
    checks.extend(
        _audit_surface_group(root, manifest.get("history_surfaces", []), "history")
    )
    checks.extend(_audit_project_namespaces(root, manifest))
    checks.extend(_audit_rule_surface(root, manifest))
    checks.extend(_audit_config(config_path, manifest["config_expectations"]))
    checks.extend(_audit_contract_registries(root, root_index_path, manifest))
    return checks


def _audit_generated_contract_files(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for relpath in manifest.get("generated_contract_files", []):
        path = root / relpath
        if not path.exists():
            checks.append(
                CheckResult(
                    "generated_contract:%s" % relpath,
                    False,
                    "missing generated contract: %s" % path,
                )
            )
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(
                CheckResult(
                    "generated_contract:%s" % relpath,
                    False,
                    "invalid json at %s: %s" % (path, exc),
                )
            )
            continue
        checks.append(
            _check_generated_layout_version(
                path,
                data,
                manifest,
                "generated_contract:%s" % relpath,
            )
        )
    return checks


def _audit_layers(root: Path, manifest: Dict[str, Any]) -> List[CheckResult]:
    return [
        _check_path(
            root / layer["path"],
            layer["kind"],
            layer.get("must_not_be_symlink", False),
            "layer:%s" % layer["id"],
        )
        for layer in manifest.get("layers", [])
    ]


def _audit_required_files(
    root: Path,
    relpaths: List[str],
    label: str,
) -> List[CheckResult]:
    return [
        _check_path(root / relpath, "file", True, "%s:%s" % (label, relpath))
        for relpath in relpaths
    ]


def _audit_compatibility_surfaces(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    return [
        _check_symlink(
            root / surface["path"],
            surface["expected_target"],
            "compat:%s" % surface["path"],
        )
        for surface in manifest.get("compatibility_surfaces", [])
    ]


def _audit_project_namespaces(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    for namespace in manifest.get("project_namespaces", []):
        checks.append(
            _check_path(
                root / namespace["path"],
                "dir",
                True,
                "namespace:%s" % namespace["id"],
            )
        )
        for required_path in namespace.get("required_paths", []):
            checks.append(
                _check_path(
                    root / required_path,
                    "dir",
                    True,
                    "namespace_path:%s" % required_path,
                )
            )
    return checks


def _audit_rule_surface(
    root: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    rule_surface = manifest.get("rule_surface", {})
    rule_path = root / rule_surface["path"]
    checks.append(_check_path(rule_path, "file", True, "rules:default_file"))
    if rule_path.exists():
        size = rule_path.stat().st_size
        if size == 0 and not rule_surface.get("allow_empty", False):
            checks.append(
                CheckResult("rules:default_contents", False, "default.rules is empty")
            )
        else:
            checks.append(
                CheckResult(
                    "rules:default_contents",
                    True,
                    "default.rules size=%d allow_empty=%s"
                    % (size, rule_surface.get("allow_empty", False)),
                )
            )
    return checks


def _audit_contract_registries(
    root: Path,
    root_index_path: Path,
    manifest: Dict[str, Any],
) -> List[CheckResult]:
    checks: List[CheckResult] = []
    checks.extend(_audit_root_surface_index(root, root_index_path, manifest))
    checks.extend(_audit_core_surface_registry(root, manifest))
    checks.extend(_audit_namespace_registry(root, manifest))
    checks.extend(_audit_namespace_standards(root, manifest))
    checks.extend(
        _audit_surface_registry(
            root,
            manifest,
            "runtime/runtime_surface_registry.json",
            "surfaces",
            "runtime_surfaces",
            "runtime",
        )
    )
    checks.extend(_audit_runtime_class_policy(root, manifest))
    checks.extend(
        _audit_surface_registry(
            root,
            manifest,
            "history/history_surface_registry.json",
            "surfaces",
            "history_surfaces",
            "history",
        )
    )
    checks.extend(_audit_history_snapshot_policy(root, manifest))
    checks.extend(_audit_migration_candidates(root, manifest))
    checks.extend(_audit_context_firewall(root, manifest))
    checks.extend(_audit_operations_policy(root, manifest))
    checks.extend(_audit_execution_mode_policy(root, manifest))
    return checks


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a Codex home layout against the layout manifest."
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root to audit.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Path to the layout manifest JSON. Defaults to <root>/core/control_plane/codex_home_layout_manifest.json.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Path to the config.toml file to audit. Defaults to <root>/config.toml.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of text.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else root / "core/control_plane/codex_home_layout_manifest.json"
    )
    config_path = Path(args.config) if args.config else root / "config.toml"

    if not manifest_path.exists():
        print("manifest missing: %s" % manifest_path, file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = audit_home(root, manifest, config_path)
    ok = all(check.ok for check in checks)

    if args.json:
        payload = {
            "ok": ok,
            "root": root.as_posix(),
            "manifest": manifest_path.as_posix(),
            "checks": [asdict(check) for check in checks],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        passed = sum(1 for check in checks if check.ok)
        total = len(checks)
        print("%s %d/%d checks passed" % ("PASS" if ok else "FAIL", passed, total))
        for check in checks:
            status = "PASS" if check.ok else "FAIL"
            print("%s %-40s %s" % (status, check.name, check.details))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
