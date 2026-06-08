# Context Firewall

This layer turns context filtering into an explicit product contract instead of
an informal prompt habit.

## Goal

Before context reaches the main model, apply a deterministic ingress policy
that:

- separates authority from mere availability
- strips instruction power from untrusted content
- limits stale or low-signal context
- bounds verbosity with a declared compaction budget
- keeps memory admission separate from transient context admission

## Canonical Contracts

- `context_ingress_policy.json`
- `memory_admission_policy.json`
- `context_compaction_policy.json`
- `untrusted_content_policy.json`

## Canonical Scripts

- `scripts/audit_context_firewall.py`
- `scripts/review_context_firewall.py`
- `scripts/probe_context_ingress.py`
- `scripts/compare_context_profiles.py`
- `scripts/evaluate_context_profiles.py`
- `scripts/suggest_curated_context.py`
- `scripts/build_curated_context.py`

## Design Rules

- Deterministic filter first.
- Optional scoring or judging may happen upstream, but this layer must still
  be auditable without another opaque model in the middle.
- Retrieved or tool-produced text is data by default, not executable
  instruction authority.
- Memory writeback is stricter than same-turn context admission.
- Compaction should prefer dropping low-priority sources before trimming
  authoritative or fresh repo-local context.

## Boundaries

- This phase does not mutate live sessions, memory stores, or retrieval stores.
- This phase does not auto-admit external claims into memory.
- This phase does not override repository-local instructions or current repo
  state.

## External Basis

- Anthropic: effective context engineering, contextual retrieval, and
  long-running harness discipline
- OpenAI: reasoning, eval, deep-research, and agent-safety guidance
- OWASP: prompt-injection prevention patterns
- Context-window research such as Lost in the Middle, RULER, and context-rot
  work on long-context degradation

## Commands

Audit the contracts:

```bash
python3 /home/example/.codex/core/control_plane/scripts/audit_context_firewall.py
```

Review the governed posture without reading session contents:

```bash
python3 /home/example/.codex/core/control_plane/scripts/review_context_firewall.py
```

Probe the newest session in report-only mode:

```bash
python3 /home/example/.codex/core/control_plane/scripts/probe_context_ingress.py
```

Compare strict, balanced, and exploratory behavior on the same redacted probe:

```bash
python3 /home/example/.codex/core/control_plane/scripts/compare_context_profiles.py
```

Evaluate multiple redacted probes before changing policy strength:

```bash
python3 /home/example/.codex/core/control_plane/scripts/evaluate_context_profiles.py
```

Suggest a redacted curated-context plan without emitting raw content:

```bash
python3 /home/example/.codex/core/control_plane/scripts/suggest_curated_context.py \
  --input /path/to/context_items.json \
  --profile balanced \
  --json
```

Build a curated context bundle from a JSON payload:

```bash
python3 /home/example/.codex/core/control_plane/scripts/build_curated_context.py \
  --input /path/to/context_items.json \
  --profile balanced \
  --json
```

Profiles:

- `strict`: tighter execution-mode budget, favors authoritative local context
- `balanced`: default mixed mode for normal engineering work
- `exploratory`: wider research-mode budget for browsing, retrieval, and tools
