# Project Bootstrap

Use this when entering a new repository, resuming a large project after context
loss, or trying to make future sessions continue from a minimal user prompt.

## Goal

Build enough project-local control that the session can keep moving with little
manual steering, without polluting the global layer with repo-specific rules.

## Step 1: Establish Boundaries

- Identify workspace root, branch, HEAD, and dirty-tree boundaries.
- Separate code edits from generated artifacts and logs.
- Determine whether the task is simple, bounded implementation or long-running
  debugging/acceptance work.

## Step 2: Load Project Instructions

Read in this order when present:

1. Repository `AGENTS.md`
2. Project fallback docs such as `PROJECT_CONTEXT.md`, `PROJECT_HANDOFF.md`,
   `WORK_RULES_MASTER.md`, or `EXECUTION_REQUIREMENTS.md`
3. Current run logs or acceptance artifacts
4. Session history only as recall support

Do not let old session memory outrank the current repository.

## Step 3: Build A First Project Map

Before changing code or running formal validation, map:

- major packages or modules
- entrypoints and launchers
- tests and acceptance scripts
- key data flow and critical interfaces
- where official upstream contract ends and local integration begins

## Step 4: Choose The Right Control Surface

Use a simple bounded workflow when the task is small and local.

Use `execution-supervisor` when the task is:

- acceptance-style
- multi-round or multi-session
- expensive to validate
- likely to drift
- supervising another Codex session

If the repository has no durable control documents yet and the work will last,
add the minimum necessary project-local assets:

- repository `AGENTS.md`
- optional plan file such as `.agent/PLANS.md`
- optional supervisor pack or ledger for the current failing frontier

## Step 5: Create A First Truth Ledger

Before deeper diagnosis, record:

- what is already proven
- what has partial evidence only
- what is explicitly failing
- what remains unknown

Then lock the current frontier and phase gate before patching or running.

## Step 6: Only Then Patch Or Run

Patch only after one minimal candidate exists.
Run only after the run can discriminate between plausible branches.

## Bootstrap Success Criteria

Bootstrap is complete only when:

- project-specific rules are externalized in the repository or a live supervisor
  pack
- the current frontier is explicit
- the next session could continue from a short prompt without rediscovering the
  whole state
