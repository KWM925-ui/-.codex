import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

THIS_DIR = Path(__file__).resolve().parent
CONTROL_PLANE_DIR = THIS_DIR.parent
SCRIPTS_DIR = CONTROL_PLANE_DIR / "scripts"

SCRIPT = SCRIPTS_DIR / "audit_codex_home_layout.py"
EXPLAIN_SCRIPT = SCRIPTS_DIR / "explain_codex_home_policy.py"
DOCTOR_SCRIPT = SCRIPTS_DIR / "doctor_codex_home_policy.py"
REPORT_SCRIPT = SCRIPTS_DIR / "report_codex_home_policy.py"
RUNTIME_REVIEW_SCRIPT = SCRIPTS_DIR / "review_runtime_reversible_targets.py"
TOOL_OWNED_REVIEW_SCRIPT = SCRIPTS_DIR / "review_tool_owned_targets.py"
ARCHIVE_REVIEW_SCRIPT = SCRIPTS_DIR / "review_archive_governed_targets.py"
LIFECYCLE_REVIEW_SCRIPT = SCRIPTS_DIR / "review_lifecycle_candidates.py"
MIGRATION_REVIEW_SCRIPT = SCRIPTS_DIR / "review_migration_candidates.py"
FIREWALL_AUDIT_SCRIPT = SCRIPTS_DIR / "audit_context_firewall.py"
FIREWALL_REVIEW_SCRIPT = SCRIPTS_DIR / "review_context_firewall.py"
INGRESS_PROBE_SCRIPT = SCRIPTS_DIR / "probe_context_ingress.py"
PROFILE_COMPARE_SCRIPT = SCRIPTS_DIR / "compare_context_profiles.py"
PROFILE_EVALUATE_SCRIPT = SCRIPTS_DIR / "evaluate_context_profiles.py"
CURATED_SUGGEST_SCRIPT = SCRIPTS_DIR / "suggest_curated_context.py"
CURATED_CONTEXT_SCRIPT = SCRIPTS_DIR / "build_curated_context.py"
PROD_MANIFEST = CONTROL_PLANE_DIR / "codex_home_layout_manifest.json"


def _fresh_timestamp(offset_seconds: int = 0) -> str:
    """Return a timestamp that stays inside freshness TTLs as tests age."""
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat().replace("+00:00", "Z")


def _write_file(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_required_scripts(root: Path, manifest: dict) -> None:
    for script_path in manifest.get("required_scripts", []):
        _write_file(root / script_path, "#!/usr/bin/env python3\n")


def _write_supervisor_workflow_fixture(root: Path, manifest: dict) -> None:
    contract = manifest.get("supervisor_workflow_contract", {})
    if not contract:
        return

    _write_file(
        root / contract["skill_path"],
        (
            "---\n"
            "name: execution-supervisor\n"
            "description: live frontier or ledger with strict facts-vs-hypotheses separation.\n"
            "---\n"
            "Do not run formal experiments or write new patches unless the ledger and the phase gate both explicitly allow it.\n"
            "Treat the ledger as the live source of truth.\n"
        ),
    )
    for relpath in contract.get("required_skill_references", []):
        _write_file(root / relpath, "workflow reference\n")

    phases = "\n\n".join(
        "### `%s: Fixture Phase`\nGoal:\n- fixture\nPromotion rule:\n- fixture"
        % phase
        for phase in contract.get("required_state_phases", [])
    )
    for pack in contract.get("live_packs", []):
        pack_root = root / pack["path"]
        for filename in contract.get("required_pack_files", []):
            _write_file(pack_root / filename, "fixture\n")
        _write_file(
            pack_root / "supervisor_ledger.md",
            (
                "# Fixture Supervisor Ledger\n\n"
                "## Locked Facts\n\n"
                "- agent end-to-end workflow is the current objective.\n"
                "- minimal isolated Codex home is audited.\n\n"
                "## Newly Locked This Round\n\n"
                "- fixture\n\n"
                "## Newly Demoted This Round\n\n"
                "- fixture\n\n"
                "## Current Frontier\n\n"
                "- Harden the project-local task workflow through project_task_workflow.py with --confirm-plan-reviewed gating.\n\n"
                "## Only Question Next Round\n\n"
                "- Decide whether to pilot the workflow in a real target repo without copying Trellis.\n\n"
                "## Forbidden Next Round\n\n"
                "- No destructive changes.\n\n"
                "## Promotion Gate\n\n"
                "- project_task_workflow_smoke, layout audit, context-firewall audit, and default acceptance stay green.\n"
            ),
        )
        _write_file(
            pack_root / "state_machine.md",
            (
                "# Supervisor State Machine\n\n"
                "%s\n\n"
                "## Current Phase\n\n"
                "Current phase: `S4`\n"
            )
            % phases,
        )
        _write_file(
            pack_root / "child_execution_protocol.md",
            (
                "# Child Execution Protocol\n\n"
                "Solve only the ledger's current question.\n"
                "No formal run and no new patch unless both:\n"
                "- the phase allows it\n"
                "- and the ledger explicitly allows it\n"
            ),
        )
        _write_file(
            pack_root / "round_self_checklist.md",
            (
                "# Round Self-Checklist\n\n"
                "- Did I reopen a ruled-out chain?\n"
                "- Did I drift from the current frontier?\n"
                "- Did I write a hypothesis as a fact?\n"
                "- Promotion Gate\n"
            ),
        )


def _write_project_task_workflow_fixture(root: Path, manifest: dict) -> None:
    contract = manifest.get("project_task_workflow_contract", {})
    if not contract:
        return

    command_lines = "\n".join(
        'subparsers.add_parser("%s")' % command
        for command in contract.get("required_commands", [])
    )
    status_lines = "\n".join(contract.get("required_statuses", []))
    artifact_lines = "\n".join(contract.get("required_artifacts", []))
    _write_file(
        root / contract["script_path"],
        (
            "#!/usr/bin/env python3\n"
            "WORKFLOW_KIND = \"codex_project_task\"\n"
            "TASKS_DIR = \".codex/tasks\"\n"
            "SESSION_DIR = \".codex/task_runtime/sessions\"\n"
            "# --confirm-plan-reviewed\n"
            "# source-like file is not allowed in context manifests\n"
            "%s\n%s\n%s\n"
        )
        % (command_lines, status_lines, artifact_lines),
    )
    _write_file(
        root / contract["workflow_doc"],
        (
            "Creating a task records planning state only\n"
            "Starting implementation is a separate step\n"
            "User consent to create a task does not imply user consent to start implementation\n"
            "stable context references only\n"
            ".codex/tasks\n"
            ".codex/task_runtime/sessions\n"
            "%s\n"
        )
        % artifact_lines,
    )
    for relpath in contract.get("template_paths", []):
        _write_file(root / relpath, "project task workflow template\n")


def _write_root_index(root: Path) -> None:
    layout_version = "test"
    manifest_path = root / "core/control_plane/codex_home_layout_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layout_version = manifest.get("layout_version", layout_version)
    index = {
        "schema_version": 1,
        "generated_for_layout_version": layout_version,
        "root_surfaces": [],
    }
    ignored_paths = {"manifest.json"}
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name in ignored_paths:
            continue
        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "dir"
        else:
            kind = "file"
        index["root_surfaces"].append(
            {
                "path": child.name,
                "kind": kind,
                "layer": "test",
                "status": "fixture",
                "category": "fixture",
                "notes": "generated test fixture",
            }
        )
    _write_file(
        root / "core/control_plane/codex_home_surface_index.json",
        json.dumps(index, indent=2),
    )


def _write_namespace_registry(root: Path, manifest: dict) -> None:
    namespace_types = {
        "codex_home": "productization_workspace",
        "pandeng": "project_overlay",
        "system_cleanup": "project_overlay",
        "reference_mirrors": "reference_bundle",
        "shared_imports": "shared_asset_bundle",
    }
    compatibility_by_namespace = {}
    for surface in manifest["compatibility_surfaces"]:
        target = surface["expected_target"]
        for namespace in manifest["project_namespaces"]:
            namespace_path = namespace["path"]
            if target == namespace_path or target.startswith(namespace_path + "/"):
                compatibility_by_namespace.setdefault(namespace["id"], []).append(
                    surface["path"]
                )

    registry = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "namespaces": [],
    }
    for namespace in manifest["project_namespaces"]:
        registry["namespaces"].append(
            {
                "id": namespace["id"],
                "path": namespace["path"],
                "type": namespace_types[namespace["id"]],
                "compatibility_entrypoints": compatibility_by_namespace.get(
                    namespace["id"], []
                ),
                "subsurfaces": [
                    {
                        "path": required_path,
                        "role": "generated test fixture",
                    }
                    for required_path in namespace.get("required_paths", [])
                ],
            }
        )

    _write_file(
        root / "project_assets/namespace_registry.json",
        json.dumps(registry, indent=2),
    )


def _write_surface_registry(
    root: Path,
    manifest: dict,
    manifest_key: str,
    output_path: str,
) -> None:
    registry = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "surfaces": [],
    }
    for surface in manifest[manifest_key]:
        category = "fixture"
        if manifest_key == "runtime_surfaces":
            root_path = surface["root_path"]
            if root_path in {"cache", "models_cache.json"}:
                category = "cache"
            elif root_path in {".tmp", "tmp"}:
                category = "temp"
            elif root_path == ".personality_migration":
                category = "runtime_marker"
            else:
                category = "state"
        elif manifest_key == "history_surfaces":
            root_path = surface["root_path"]
            history_categories = {
                "sessions": "sessions",
                "sessions_archive": "sessions_archive",
                "archived_sessions": "archived_sessions",
                "session_index.jsonl": "index",
                "session_index.jsonl.bak_20260604_2109": "index",
                "state_5.sqlite.bak_20260604_2110": "config_snapshot",
                "state_5.sqlite.bak_ui_probe_20260605_054407": "config_snapshot",
                "memories": "memory",
                "attachments": "attachments",
                "shell_snapshots": "shell_snapshots",
                "config.toml.before-openai-login.20260428-134805": "config_snapshot",
            }
            history_retention_roles = {
                "sessions": "active rollout history",
                "sessions_archive": "archived rollout history",
                "archived_sessions": "legacy archive store",
                "session_index.jsonl": "lookup/index surface",
                "session_index.jsonl.bak_20260604_2109": "local session-index backup preserved as history evidence",
                "state_5.sqlite.bak_20260604_2110": "local runtime-state backup preserved as reversible evidence",
                "state_5.sqlite.bak_ui_probe_20260605_054407": "local UI probe runtime-state backup preserved as reversible evidence",
                "memories": "generated memory store",
                "attachments": "uploaded attachment evidence and pasted-text metadata",
                "shell_snapshots": "TTY/shell continuation evidence",
                "config.toml.before-openai-login.20260428-134805": "historical config snapshot preserved as evidence",
            }
            category = history_categories[root_path]

        entry = {
            "category": category,
            "root_path": surface["root_path"],
            "mirror_path": surface.get("mirror_path", ""),
            "authoritative_at_root": True,
        }
        if manifest_key == "history_surfaces":
            entry["retention_role"] = history_retention_roles[root_path]
        if "required" in surface:
            entry["required"] = surface["required"]
        registry["surfaces"].append(entry)

    _write_file(root / output_path, json.dumps(registry, indent=2))


def _write_core_surface_registry(root: Path, manifest: dict) -> None:
    core_categories = {
        "AGENTS.md": "global_map",
        "README.md": "home_summary",
        "config.toml": "config_live",
    }
    registry = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "surfaces": [],
    }
    for surface in manifest["core_surfaces"]:
        registry["surfaces"].append(
            {
                "category": core_categories[surface["root_path"]],
                "root_path": surface["root_path"],
                "canonical_path": surface["canonical_path"],
                "authoritative_at_root": True,
                "required": True,
            }
        )
    _write_file(root / "core/core_surface_registry.json", json.dumps(registry, indent=2))


def _write_namespace_standards(root: Path, manifest: dict) -> None:
    namespace_types = {}
    for namespace in manifest["project_namespaces"]:
        namespace_id = namespace["id"]
        if namespace_id == "codex_home":
            namespace_types[namespace_id] = {
                "type": "productization_workspace",
                "required_subsurface_prefixes": [
                    "project_assets/codex_home/supervisor"
                ],
                "allow_compatibility_entrypoints": False,
            }
        elif namespace_id in {"pandeng", "system_cleanup"}:
            namespace_types[namespace_id] = {
                "type": "project_overlay",
                "required_subsurface_prefixes": [
                    "supervisor"
                ],
                "allow_compatibility_entrypoints": True,
            }
        elif namespace_id == "reference_mirrors":
            namespace_types[namespace_id] = {
                "type": "reference_bundle",
                "required_subsurface_prefixes": [
                    "upstream_audit"
                ],
                "allow_compatibility_entrypoints": True,
            }
        elif namespace_id == "shared_imports":
            namespace_types[namespace_id] = {
                "type": "shared_asset_bundle",
                "required_subsurface_prefixes": [
                    "vendor_imports"
                ],
                "allow_compatibility_entrypoints": True,
            }

    standards = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "allowed_namespace_types": list(namespace_types.values()),
    }
    _write_file(
        root / "project_assets/namespace_standards.json",
        json.dumps(standards, indent=2),
    )


def _write_history_snapshot_policy(root: Path, manifest: dict) -> None:
    policy = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "surfaces": [],
    }
    for entry in manifest.get("history_snapshot_surfaces", []):
        policy["surfaces"].append(
            {
                "root_path": entry["root_path"],
                "snapshot_kind": entry["snapshot_kind"],
                "retention_role": entry["retention_role"],
                "authoritative_at_root": True,
                "mirror_path": entry.get("mirror_path", ""),
                "required": entry.get("required", True),
                "rewrite_policy": "do_not_modify_in_place",
            }
        )
    _write_file(
        root / "history/config_snapshot_policy.json",
        json.dumps(policy, indent=2),
    )


def _write_runtime_class_policy(root: Path, manifest: dict) -> None:
    policy = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "allowed_categories": [],
    }
    for entry in manifest.get("runtime_category_policy", []):
        policy["allowed_categories"].append(
            {
                "category": entry["category"],
                "mirror_required": entry["mirror_required"],
                "allow_optional_root": entry["allow_optional_root"],
                "retention_class": entry["retention_class"],
            }
        )
    _write_file(
        root / "runtime/runtime_class_policy.json",
        json.dumps(policy, indent=2),
    )


def _write_operations_policy(root: Path, manifest: dict) -> None:
    policy = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "global_rules": {
            "default_execution_mode": "compatibility_first",
            "allow_hard_delete": False,
            "allow_hot_path_physical_move": False,
            "require_compatibility_entrypoints_when_callers_exist": True,
            "preferred_reversible_action": "quarantine_or_trash",
        },
        "action_classes": [
            {"action": "preserve", "description": "fixture"},
            {"action": "archive", "description": "fixture"},
            {"action": "quarantine", "description": "fixture"},
            {"action": "rotate", "description": "fixture"},
            {"action": "tool_only", "description": "fixture"},
            {"action": "manual_review", "description": "fixture"},
        ],
        "surface_policies": [
            {"selector_type": "core_category", "selector": "global_map", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "core_category", "selector": "home_summary", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "core_category", "selector": "config_live", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "compatibility_category", "selector": "core", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "compatibility_category", "selector": "project_assets", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "runtime_category", "selector": "cache", "allowed_actions": ["preserve", "quarantine", "rotate", "manual_review"]},
            {"selector_type": "runtime_category", "selector": "state", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "runtime_category", "selector": "temp", "allowed_actions": ["preserve", "quarantine", "rotate", "manual_review"]},
            {"selector_type": "runtime_category", "selector": "runtime_marker", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "history_category", "selector": "sessions", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "history_category", "selector": "sessions_archive", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "history_category", "selector": "archived_sessions", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "history_category", "selector": "index", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "history_category", "selector": "memory", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "history_category", "selector": "attachments", "allowed_actions": ["preserve", "manual_review"]},
            {"selector_type": "history_category", "selector": "shell_snapshots", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "history_category", "selector": "config_snapshot", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "namespace_type", "selector": "productization_workspace", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "namespace_type", "selector": "project_overlay", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "namespace_type", "selector": "reference_bundle", "allowed_actions": ["preserve", "archive", "manual_review"]},
            {"selector_type": "namespace_type", "selector": "shared_asset_bundle", "allowed_actions": ["preserve", "quarantine", "tool_only", "manual_review"]},
        ],
    }
    _write_file(
        root / "core/control_plane/codex_home_lifecycle_operations.json",
        json.dumps(policy, indent=2),
    )


def _write_execution_mode_policy(root: Path, manifest: dict) -> None:
    policy = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "mode_classes": [
            {"mode": "preserve_only", "kind": "base", "description": "fixture"},
            {"mode": "reversible_only", "kind": "base", "description": "fixture"},
            {"mode": "archive_only", "kind": "base", "description": "fixture"},
            {"mode": "rotation_allowed", "kind": "modifier", "description": "fixture"},
            {"mode": "tool_only", "kind": "modifier", "description": "fixture"},
            {"mode": "manual_review_only", "kind": "modifier", "description": "fixture"},
        ],
        "selector_modes": [
            {"selector_type": "core_category", "selector": "global_map", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "core_category", "selector": "home_summary", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "core_category", "selector": "config_live", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "compatibility_category", "selector": "core", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "compatibility_category", "selector": "project_assets", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "runtime_category", "selector": "cache", "execution_modes": ["reversible_only", "rotation_allowed", "manual_review_only"]},
            {"selector_type": "runtime_category", "selector": "state", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "runtime_category", "selector": "temp", "execution_modes": ["reversible_only", "rotation_allowed", "manual_review_only"]},
            {"selector_type": "runtime_category", "selector": "runtime_marker", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "sessions", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "sessions_archive", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "archived_sessions", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "index", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "memory", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "attachments", "execution_modes": ["preserve_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "shell_snapshots", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "history_category", "selector": "config_snapshot", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "namespace_type", "selector": "productization_workspace", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "namespace_type", "selector": "project_overlay", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "namespace_type", "selector": "reference_bundle", "execution_modes": ["archive_only", "manual_review_only"]},
            {"selector_type": "namespace_type", "selector": "shared_asset_bundle", "execution_modes": ["reversible_only", "tool_only", "manual_review_only"]},
        ],
    }
    _write_file(
        root / "core/control_plane/codex_home_execution_modes.json",
        json.dumps(policy, indent=2),
    )


def _write_migration_candidate_policy(root: Path, manifest: dict) -> None:
    policy = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "candidates": [],
    }
    for entry in manifest.get("migration_candidates", []):
        policy["candidates"].append(
            {
                "id": entry["id"],
                "selector_type": entry["selector_type"],
                "selector": entry["selector"],
                "target": entry["target"],
                "candidate_kind": entry["candidate_kind"],
                "phase": entry["phase"],
                "scope_root": entry["scope_root"],
                "compatibility_entrypoints": list(
                    entry.get("compatibility_entrypoints", [])
                ),
                "protected_paths": list(entry.get("protected_paths", [])),
                "preconditions": list(entry.get("preconditions", [])),
                "planned_steps": list(entry.get("planned_steps", [])),
                "forbidden_actions": list(entry.get("forbidden_actions", [])),
                "validation_commands": list(entry.get("validation_commands", [])),
            }
        )
    _write_file(
        root / "core/control_plane/codex_home_migration_candidates.json",
        json.dumps(policy, indent=2),
    )


def _write_context_firewall_contracts(root: Path, manifest: dict) -> None:
    spec = manifest["context_firewall_policy"]
    ingress = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "stages": [
            {"id": stage, "required": True, "purpose": "fixture"}
            for stage in spec["required_stages"]
        ],
        "relevance_policy": {
            "default_source_action": "admit",
            "missing_score_action": "admit",
            "tiers": [
                {"id": "drop_low_signal", "max_score": 0.14, "action": "drop"},
                {"id": "demote_borderline", "max_score": 0.34, "action": "demote"},
                {"id": "admit_relevant", "max_score": 1.0, "action": "admit"},
            ],
            "source_overrides": [
                {"source_class": "repo_state", "below_threshold_action": "admit"},
                {
                    "source_class": "repo_instructions",
                    "below_threshold_action": "admit",
                },
                {"source_class": "user_message", "below_threshold_action": "admit"},
                {
                    "source_class": "operator_contract",
                    "below_threshold_action": "demote",
                },
                {
                    "source_class": "global_control",
                    "below_threshold_action": "demote",
                },
            ],
        },
        "source_classes": [
            {
                "source_class": source_class,
                "authority_rank": index + 1,
                "treatment": (
                    "authoritative_instruction"
                    if source_class in {
                        "repo_instructions",
                        "user_message",
                        "operator_contract",
                        "global_control",
                    }
                    else (
                        "untrusted_data"
                        if source_class == "untrusted_external"
                        else ("reference_only" if source_class in {"session_memory", "retrieved_web"} else "evidence")
                    )
                ),
                "freshness_policy": (
                    "session_local"
                    if source_class in {"user_message", "operator_contract"}
                    else (
                        "stable"
                        if source_class == "global_control"
                        else (
                            "stale_allowed"
                            if source_class == "session_memory"
                            else (
                                "freshness_scoped"
                                if source_class in {"retrieved_web", "untrusted_external"}
                                else "fresh_required"
                            )
                        )
                    )
                ),
                "max_age_days": (
                    365
                    if source_class == "global_control"
                    else (30 if source_class == "session_memory" else (1 if source_class == "user_message" else 14))
                ),
                "allows_memory_writeback": source_class
                in {
                    "repo_state",
                    "repo_instructions",
                    "user_message",
                    "operator_contract",
                },
            }
            for index, source_class in enumerate(spec["required_source_classes"])
        ],
        "conflict_rules": ["fixture"],
    }
    _write_file(
        root / "core/control_plane/context_ingress_policy.json",
        json.dumps(ingress, indent=2),
    )

    memory = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "default_action": "deny",
        "memory_kinds": [
            {"id": kind, "requires_repo_anchor": True, "ttl_days": 30}
            for kind in spec["required_memory_kinds"]
        ],
        "source_class_rules": [],
    }
    for source_class in spec["required_source_classes"]:
        if source_class in {"repo_state", "repo_instructions", "operator_contract"}:
            action = "allow"
            allowed = ["project_fact", "volatile_task_state"]
        elif source_class in {"user_message", "global_control", "tool_output"}:
            action = "review_only"
            allowed = ["stable_preference", "durable_workflow_rule"]
        else:
            action = "deny"
            allowed = []
        memory["source_class_rules"].append(
            {
                "source_class": source_class,
                "memory_action": action,
                "allowed_memory_kinds": allowed,
                "requires_fresh_anchor": source_class != "session_memory",
            }
        )
    _write_file(
        root / "core/control_plane/memory_admission_policy.json",
        json.dumps(memory, indent=2),
    )

    compaction = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "profiles": [
            {
                "id": "strict",
                "max_total_chars": 9000,
                "max_items": 10,
                "max_chars_per_item": 2000,
                "min_chars_per_item": 180,
                "reserved_source_classes": [
                    "repo_state",
                    "repo_instructions",
                    "user_message",
                ],
                "drop_order": [
                    "session_memory",
                    "untrusted_external",
                    "retrieved_web",
                    "tool_output",
                    "global_control",
                    "operator_contract",
                    "user_message",
                    "repo_state",
                    "repo_instructions",
                ],
                "source_class_char_limits": [
                    {
                        "source_class": source_class,
                        "max_chars": (
                            600
                            if source_class in {"session_memory", "untrusted_external"}
                            else (900 if source_class == "retrieved_web" else 1200)
                        ),
                    }
                    for source_class in spec["required_source_classes"]
                ],
            },
            {
                "id": "balanced",
                "max_total_chars": 12000,
                "max_items": 12,
                "max_chars_per_item": 2400,
                "min_chars_per_item": 200,
                "reserved_source_classes": [
                    "repo_state",
                    "repo_instructions",
                    "user_message",
                ],
                "drop_order": list(spec["required_source_classes"]),
                "source_class_char_limits": [
                    {
                        "source_class": source_class,
                        "max_chars": 800 if source_class in {"session_memory", "untrusted_external"} else 1800,
                    }
                    for source_class in spec["required_source_classes"]
                ],
            },
            {
                "id": "exploratory",
                "max_total_chars": 15000,
                "max_items": 16,
                "max_chars_per_item": 2800,
                "min_chars_per_item": 220,
                "reserved_source_classes": [
                    "repo_state",
                    "repo_instructions",
                    "user_message",
                ],
                "drop_order": [
                    "untrusted_external",
                    "session_memory",
                    "retrieved_web",
                    "tool_output",
                    "global_control",
                    "operator_contract",
                    "user_message",
                    "repo_state",
                    "repo_instructions",
                ],
                "source_class_char_limits": [
                    {
                        "source_class": source_class,
                        "max_chars": (
                            1000
                            if source_class in {"session_memory", "untrusted_external"}
                            else (1800 if source_class == "retrieved_web" else 2200)
                        ),
                    }
                    for source_class in spec["required_source_classes"]
                ],
            }
        ],
    }
    _write_file(
        root / "core/control_plane/context_compaction_policy.json",
        json.dumps(compaction, indent=2),
    )

    untrusted = {
        "schema_version": 1,
        "generated_for_layout_version": manifest.get("layout_version", "test"),
        "default_action_for_flagged": "downgrade_to_data",
        "source_class_rules": [
            {
                "source_class": source_class,
                "strip_instruction_authority": True,
                "quoted_only": True,
            }
            for source_class in spec["required_untrusted_source_classes"]
        ],
        "marker_categories": [
            {
                "id": "instruction_override",
                "action": "downgrade_to_data",
                "patterns": ["(?i)\\bignore (all )?(previous|earlier) instructions\\b"],
            },
            {
                "id": "credential_request",
                "action": "flag",
                "patterns": ["(?i)\\b(api key|password|secret token|ssh private key)\\b"],
            },
            {
                "id": "tool_escalation",
                "action": "flag",
                "patterns": [
                    "(?i)\\b(run|execute) (this|the following) command\\b",
                    "(?i)\\bcurl\\s+[^|]+\\|\\s*(sh|bash)\\b",
                ],
            },
            {
                "id": "exfiltration_request",
                "action": "flag",
                "patterns": ["(?i)\\b(upload|send|exfiltrat\\w*)\\b.{0,40}\\b(files?|data|secrets?)\\b"],
            },
            {
                "id": "hidden_payload",
                "action": "flag",
                "patterns": ["(?i)<script\\b", "(?i)begin prompt", "(?i)base64,"],
            },
        ],
    }
    _write_file(
        root / "core/control_plane/untrusted_content_policy.json",
        json.dumps(untrusted, indent=2),
    )


def _write_contract_files(root: Path, manifest: dict) -> None:
    _write_file(
        root / "core/control_plane/codex_home_layout_manifest.json",
        json.dumps(manifest, indent=2),
    )
    _write_core_surface_registry(root, manifest)
    _write_namespace_registry(root, manifest)
    _write_namespace_standards(root, manifest)
    _write_surface_registry(
        root,
        manifest,
        "runtime_surfaces",
        "runtime/runtime_surface_registry.json",
    )
    _write_runtime_class_policy(root, manifest)
    _write_surface_registry(
        root,
        manifest,
        "history_surfaces",
        "history/history_surface_registry.json",
    )
    _write_history_snapshot_policy(root, manifest)
    _write_migration_candidate_policy(root, manifest)
    _write_context_firewall_contracts(root, manifest)
    _write_operations_policy(root, manifest)
    _write_execution_mode_policy(root, manifest)


def _materialize_layout(root: Path, manifest: dict) -> None:
    for layer in manifest["layers"]:
        (root / layer["path"]).mkdir(parents=True, exist_ok=True)

    for doc_path in manifest["required_docs"]:
        _write_file(root / doc_path, "doc\n")
    _write_required_scripts(root, manifest)
    _write_supervisor_workflow_fixture(root, manifest)
    _write_project_task_workflow_fixture(root, manifest)

    for namespace in manifest["project_namespaces"]:
        (root / namespace["path"]).mkdir(parents=True, exist_ok=True)
        for required_path in namespace.get("required_paths", []):
            (root / required_path).mkdir(parents=True, exist_ok=True)

    for surface in manifest["compatibility_surfaces"]:
        target = root / surface["expected_target"]
        target.mkdir(parents=True, exist_ok=True)
        link = root / surface["path"]
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(surface["expected_target"])

    for surface in manifest["runtime_surfaces"] + manifest["history_surfaces"]:
        root_path = root / surface["root_path"]
        root_path.parent.mkdir(parents=True, exist_ok=True)
        if surface.get("required", True) or surface["root_path"] != "auth.json":
            if surface["root_kind"] == "dir":
                root_path.mkdir(parents=True, exist_ok=True)
            else:
                _write_file(root_path, "data\n")

        if surface.get("mirror_path"):
            mirror = root / surface["mirror_path"]
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.symlink_to(surface["expected_mirror_target"])

    rule_path = root / manifest["rule_surface"]["path"]
    _write_file(rule_path, "")
    for surface in manifest["core_surfaces"]:
        _write_file(root / surface["root_path"], "core\n")
    _write_contract_files(root, manifest)


def _write_config(path: Path, extra_project_key: str = "") -> None:
    projects = [
        "/home/example",
        "/home/example/.codex",
        "/home/example/codex_autoadvance_harness",
        "/home/example/ego-fast_ws",
        "/home/example/follwer_ws",
        "/home/example/pandeng_ws",
        "/home/example/sim_plane",
    ]
    if extra_project_key:
        projects.append(extra_project_key)

    lines = [
        'developer_instructions = """',
        "Ask concise clarifying questions before substantive work when the user's goal, constraints, success criteria, or risk tolerance are materially unclear; do not guess the user's intent from habit, prior projects, or agent experience.",
        "When a user request is vague, stop and ask; do not replace clarification with safe cleanup, documentation polish, tests, type hints, low-risk refactor, or other seemingly harmless work.",
        "When stopping to clarify, explicitly say that no files were changed and no substantive action was taken, unless a prior action in the same turn already changed something.",
        "Do not present memory, experience, or plausibility as fact. If a conclusion is not backed by fresh evidence or a clearly cited source, label it as an inference, assumption, or uncertainty.",
        'User-facing replies must default to clear Chinese "说人话": explain the concrete result, cause/effect, blocker, and next useful action. Keep exact technical identifiers verbatim, but do not make the user read English process labels or control-plane jargon when plain Chinese is clearer.',
        '"""',
        "",
    ]
    for project in projects:
        lines.append('[projects."%s"]' % project)
        lines.append('trust_level = "trusted"')
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
