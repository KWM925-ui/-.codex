# Codex Home Governance

This document turns the current `~/.codex` layout into an auditable product
surface instead of a README-only convention.

## Source Of Truth

The canonical machine-readable layout contract is:

- `~/.codex/core/control_plane/codex_home_layout_manifest.json`
- `~/.codex/core/control_plane/codex_home_surface_index.json`
- `~/.codex/core/core_surface_registry.json`
- `~/.codex/project_assets/namespace_registry.json`
- `~/.codex/project_assets/namespace_standards.json`
- `~/.codex/runtime/runtime_surface_registry.json`
- `~/.codex/runtime/runtime_class_policy.json`
- `~/.codex/history/history_surface_registry.json`
- `~/.codex/history/config_snapshot_policy.json`
- `~/.codex/core/control_plane/codex_home_lifecycle_operations.json`
- `~/.codex/core/control_plane/codex_home_execution_modes.json`
- `~/.codex/core/control_plane/codex_home_migration_candidates.json`
- `~/.codex/core/control_plane/context_ingress_policy.json`
- `~/.codex/core/control_plane/memory_admission_policy.json`
- `~/.codex/core/control_plane/context_compaction_policy.json`
- `~/.codex/core/control_plane/untrusted_content_policy.json`

The canonical validator is:

- `~/.codex/core/control_plane/scripts/audit_codex_home_layout.py`

Human-facing summaries remain useful, but they are downstream:

- `~/.codex/README.md`
- `~/.codex/core/README.md`
- `~/.codex/runtime/README.md`
- `~/.codex/history/README.md`
- `~/.codex/project_assets/README.md`
- `~/.codex/core/control_plane/codex_home_operations.md`
- `~/.codex/core/control_plane/scripts/review_migration_candidates.py`
- `~/.codex/core/control_plane/scripts/audit_context_firewall.py`
- `~/.codex/core/control_plane/scripts/review_context_firewall.py`
- `~/.codex/core/control_plane/scripts/probe_context_ingress.py`
- `~/.codex/core/control_plane/scripts/compare_context_profiles.py`
- `~/.codex/core/control_plane/scripts/evaluate_context_profiles.py`
- `~/.codex/core/control_plane/scripts/build_curated_context.py`

## Current Product Boundary

`~/.codex` is currently governed as four canonical layers:

1. `core/`
2. `runtime/`
3. `history/`
4. `project_assets/`

Root-level compatibility entrypoints are preserved on purpose. They are not
layout drift as long as they match the manifest and remain symlinks.

## Required Change Discipline

Any structural change to `~/.codex` should follow this order:

1. Update the manifest first.
2. Update the affected registries, docs, and compatibility notes.
   Generated contract files must also keep
   `generated_for_layout_version == layout_version`.
3. Update or add audit coverage.
4. Run the layout audit.
5. Run any touched script/unit tests.

Do not silently change structure and leave the manifest behind.

## Rules For Future Moves

- New reusable global assets belong under `core/`.
- New runtime/cache/temp/state mirrors belong under `runtime/`.
- New session/history/recall mirrors belong under `history/`.
- New project-specific packs, frozen evidence, or reference mirrors belong under
  `project_assets/<namespace>/`.
- New root-level intentional surfaces should also be recorded in
  `codex_home_surface_index.json`.
- New root-level entrypoints should normally be compatibility symlinks, not new
  physical top-level trees.

## Deferred Migrations

These surfaces remain intentionally authoritative at the root in the current
phase:

- `auth.json`
- `logs_2.sqlite*`
- `state_5.sqlite*`
- `sessions/`
- `sessions_archive/`
- `archived_sessions/`
- `session_index.jsonl`
- `memories/`
- `shell_snapshots/`
- `tmp/`
- `.tmp/`
- `cache/`

They are mirrored into `runtime/` or `history/` for product shape, but they are
not yet safe to move physically without another compatibility phase.

## Audit Command

Run:

```bash
python3 /home/example/.codex/core/control_plane/scripts/audit_codex_home_layout.py
```

Use `--json` if another tool needs structured output.

## What This Phase Buys

- one machine-readable source of truth for the layout
- one repeatable audit instead of ad hoc manual inspection
- stable rules for adding new namespaces and compatibility entrypoints
- a cleaner boundary between intentional legacy surfaces and accidental clutter
