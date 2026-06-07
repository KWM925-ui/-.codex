# Portable Codex Control Plane

This repository contains the reusable part of a Codex control system:

- global instruction map in `AGENTS.md`
- control-plane policies, audits, and evaluation scripts under `core/control_plane`
- lightweight project-local task workflow under `core/control_plane/scripts/project_task_workflow.py`
- reusable skills under `core/skills`
- empty global rules surface under `core/rules/default.rules`

It intentionally does not contain local runtime state, sessions, logs, private
project evidence, real `config.toml`, auth material, or cache directories.

## What To Install

Set `CODEX_HOME` to the target Codex home, normally `~/.codex`, then copy the
portable surfaces:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rsync -a AGENTS.md core "$CODEX_HOME"/
```

Use `config.example.toml` as a reference only. Do not overwrite a real
`config.toml` without reviewing local providers, auth, models, and trusted
projects.

## Validation

Run the deterministic checks after install:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B core/control_plane/scripts/audit_context_firewall.py --root "$CODEX_HOME" --json
PYTHONDONTWRITEBYTECODE=1 python3 -B core/control_plane/scripts/run_agent_e2e_evals.py --root "$CODEX_HOME" --json
PYTHONDONTWRITEBYTECODE=1 python3 -B core/control_plane/scripts/run_codex_home_acceptance.py --root "$CODEX_HOME" --json
```

The full layout audit expects a materialized Codex home with runtime/history
mirror registries. It is useful for an installed home, not for publishing local
state into this repository.

## Export Boundary

Do not commit:

- `config.toml`
- `auth.json`
- `*.sqlite*`
- `*.jsonl`
- `sessions/`, `sessions_archive/`, `archived_sessions/`
- `runtime/`, `history/`, `project_assets/`
- `cache/`, `tmp/`, `.tmp/`
- private project markdown, evidence, or supervisor packs

The public repository should stay generic: project-specific rules belong in the
project repo or a private project overlay.

## Project Task Workflow

Use the task workflow only inside a target repository, not in the global home
by default:

```bash
python3 "$CODEX_HOME/core/control_plane/scripts/project_task_workflow.py" \
  create "Clarify and implement feature" --project-root /path/to/repo --json
```

Creating a task records planning state only. Implementation still requires the
separate `start --confirm-plan-reviewed` step.
