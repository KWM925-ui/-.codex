# Codex Home Operations Policy

This document turns the productized layout into an execution policy rather than
just a structural description.

## Phase Goal

The current phase is still compatibility-first.

That means:

- no hard delete
- no hot-path physical moves
- no silent path replacement where callers still expect a legacy entrypoint

## Default Action Bias

When a future operation needs to touch governed surfaces, the preferred order is:

1. `preserve`
2. `archive`
3. `quarantine`
4. anything stronger only in a later migration phase

## Current Operational Meaning

- `preserve`
  - do not move or clean in the current phase
- `archive`
  - continuity-preserving move into an explicit archive/evidence location
- `quarantine`
  - reversible trash/quarantine flow only
- `manual_review`
  - no unattended execution
- `tool_only`
  - use the owning toolchain, not ad hoc filesystem mutation

## Why This Exists

The structural contracts answer "what is this surface?"

This operations contract answers:

- what kind of action is even allowed
- whether reversibility is required
- whether the user or operator must review it first

## Machine-Readable Source

The canonical operations contract is:

- `core/control_plane/codex_home_lifecycle_operations.json`
- `core/control_plane/codex_home_execution_modes.json`
- `core/control_plane/scripts/explain_codex_home_policy.py`
- `core/control_plane/scripts/doctor_codex_home_policy.py`
- `core/control_plane/scripts/report_codex_home_policy.py`
- `core/control_plane/scripts/review_runtime_reversible_targets.py`
- `core/control_plane/scripts/review_tool_owned_targets.py`
- `core/control_plane/scripts/review_archive_governed_targets.py`
- `core/control_plane/scripts/review_migration_candidates.py`
- `core/control_plane/scripts/audit_context_firewall.py`
- `core/control_plane/scripts/review_context_firewall.py`
- `core/control_plane/scripts/probe_context_ingress.py`
- `core/control_plane/scripts/compare_context_profiles.py`
- `core/control_plane/scripts/evaluate_context_profiles.py`
- `core/control_plane/scripts/build_curated_context.py`

## Batch Operator Report

When the operator needs a whole-home posture summary instead of one surface at a
time, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/report_codex_home_policy.py
```

That report batches all governed root surfaces plus registered namespace roots
and summarizes:

- health class by governed surface
- recommended action by governed surface
- aggregate counts by health class and action
- an `attention_targets` list for surfaces not in simple preserve/archive
- grouped operator work buckets under `action_groups` so reversible runtime
  targets and tool-owned targets can be handled as a small number of decisions
  posture

## Focused Runtime Reversible Review

When the next action is specifically about the reversible runtime batch from the
governance report, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/review_runtime_reversible_targets.py
```

That focused review keeps the operator inside the bounded reversible runtime
scope and adds:

- runtime category breakdown for the current batch
- retention-class detail from `runtime/runtime_class_policy.json`
- mirror continuity detail from `runtime/runtime_surface_registry.json`
- an explicit out-of-scope list for stable runtime state surfaces
- a small operator sequence that preserves compatibility-first constraints

## Focused Tool-Owned Review

When the next action is specifically about the tool-owned target batch from the
governance report, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/review_tool_owned_targets.py
```

That focused review keeps the operator inside the bounded tool-owned scope and
adds:

- namespace metadata from `project_assets/namespace_registry.json`
- compatibility-entrypoint status for each tool-owned namespace target
- registered subsurface inventory state such as placeholder-only vs materialized
- local workflow artifact detection without widening into bundle mutation
- a scoped view of the other non-stable attention groups that remain out of scope

## Archive Planning Review

When the next action is specifically about the archive-governed surfaces, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/review_archive_governed_targets.py
```

That focused review keeps the operator inside the bounded archive-governed
scope and adds:

- one continuity-safe planning batch for archive-governed history and namespace targets
- history continuity detail from `history/history_surface_registry.json`
- typed config-evidence rewrite and move-gate detail from `history/config_snapshot_policy.json`
- namespace anchor, registered-subsurface, and compatibility-entrypoint detail
- explicit preserve-only history surfaces that must remain stable while archive planning stays in scope

## Migration Candidate Review

When the next action is specifically about proposal-grade migration candidates,
use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/review_migration_candidates.py
```

That review surfaces the currently governed migration candidates and verifies
that their required compatibility entrypoints still resolve correctly under the
present layout contracts.

## Context Firewall Audit

When the next action is specifically about ingress noise, untrusted content,
or context-budget discipline, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/audit_context_firewall.py
```

That audit verifies the governed context-firewall contracts for:

- source authority and freshness classes
- memory admission boundaries
- compaction budgets and source drop order
- untrusted-content stripping, flagging, and marker coverage

To inspect source posture, relevance demotion/drop behavior, profile budgets,
and current runtime-integration status, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/review_context_firewall.py
```

That review is intentionally report-only. It does not mutate sessions,
memories, runtime databases, or tool ingress paths.

To probe real session/tool ingress through the same firewall in report-only
mode, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/probe_context_ingress.py
```

That probe selects the newest session by default, emits no raw session content,
emits no rendered curated context, and does not mutate sessions, memories,
runtime databases, or tool ingress paths.

To compare strict, balanced, and exploratory filtering against the same real
session candidates before changing policy strength, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/compare_context_profiles.py
```

That comparison is intentionally report-only. It emits profile-level deltas and
redacted item metadata only; it does not emit raw session content or rendered
curated context.

To evaluate profile behavior across multiple representative session probes
before changing thresholds or attaching runtime hooks, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/evaluate_context_profiles.py
```

That evaluation aggregates only redacted metadata across selected sessions and
emits a deterministic recommendation. It does not require raw-content review and
does not mutate sessions, memories, runtime databases, or tool ingress paths.

To build a deterministic curated context bundle from heterogeneous inputs, use:

```bash
python3 $CODEX_HOME/core/control_plane/scripts/build_curated_context.py \
  --input /path/to/context_items.json \
  --profile balanced \
  --json
```

## Execution Mode Overlay

The action contract answers "what is allowed?"

The execution-mode contract answers "what is the default operational track for
this surface class?"

- `preserve_only`
  - stay in place in the current phase
- `reversible_only`
  - cleanup must remain reversible
- `archive_only`
  - cleanup may only flow into an explicit archive/evidence target
- `rotation_allowed`
  - bounded retention rotation is allowed
- `tool_only`
  - use an owning toolchain instead of ad hoc edits
- `manual_review_only`
  - unattended execution is not allowed
