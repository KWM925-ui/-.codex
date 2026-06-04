---
name: project-bootstrap
description: Use when starting a new repository, resuming a long-running project after context loss, or installing durable project-local control so future sessions can continue with minimal user prompting. Do not use for small one-shot fixes that do not need repo-level control assets.
---

# Project Bootstrap

Use this skill to turn a drifting or under-instrumented repository into one with
clear project-local control surfaces.

## What This Skill Is For

- entering a new repo
- resuming a repo after a long gap or compressed context
- converting a prompt-only workflow into repo-local docs plus durable control
- making future sessions continue from a short prompt such as "continue"

## What This Skill Is Not For

- small local bug fixes
- single-file implementation tasks with no continuity risk
- project-specific diagnosis that already has a healthy ledger and repo docs

## Required Read Order

1. `$CODEX_HOME/core/control_plane/project_bootstrap.md`
2. `$CODEX_HOME/core/control_plane/global_execution_contract.md`
3. `$CODEX_HOME/core/control_plane/stable_user_preferences.md`
4. Repository `AGENTS.md` or fallback project docs if they exist

## Workflow

1. Establish boundaries:
   - repo root
   - branch and HEAD
   - dirty-tree boundary
   - generated artifacts vs real edits
2. Decide whether the task needs only a small local workflow or supervisor mode.
3. If repo-local control assets are missing and the work will last:
   - create or tighten repository `AGENTS.md`
   - create or tighten a plan/ledger if continuity is required
   - if the task is acceptance-style or debugging-heavy, switch to
     `execution-supervisor`
4. Keep global rules generic; move project-specific acceptance, architecture,
   and contracts into the repository.
5. End bootstrap with a first truth ledger and a bounded next action.

## Templates

Use these when scaffolding project-local assets:

- `$CODEX_HOME/core/control_plane/templates/repo_AGENTS.template.md`
- `$CODEX_HOME/core/control_plane/templates/PLANS.template.md`

## Output Standard

When bootstrap is the main task, report:

- what global assets were applied
- what project-local assets were created or tightened
- what remains project-specific and intentionally not globalized
- what the next bounded action is
