# Repo-Scale Auto-Advance State Machine

## Auto-Advance Rule

When a phase promotion rule is satisfied, do not stop by default. Update the
live supervisor files and continue in the same turn.

## Phase Label Invariant

Only these phase labels are valid in this harness:

- `S4: Patch Candidate Formation`
- `S5: Low-Pollution Validation`

Do not invent a new phase label. After validation passes, keep `Current Phase`
at `S5`; record completion in the ledger instead.

### `S4: Patch Candidate Formation`

Goal:

- Remap the stale snapshot anchor to the active worktree target and apply one
  uniquely locked patch while respecting dirty-worktree boundaries.

Promotion rule:

- The patch candidate is uniquely locked and proof plan is complete.

Default action once entered:

- Remap the snapshot anchor to the active worktree immediately.
- Apply the patch immediately.
- Advance to `S5` and run validation in the same turn.

### `S5: Low-Pollution Validation`

Goal:

- Run the one declared validation command and judge pass or fail.

Promotion rule:

- Validation passes.

Default action once entered:

- Run the validation command immediately.
- Update the live pack to completed state in the ledger only.
- Stop only after reporting whether the same-turn auto-advance succeeded.

## Current Phase

Current phase is `S4: Patch Candidate Formation`.

## Phase-Specific Allowed Actions For Current Phase

Allowed:

- Read files
- Remap the snapshot anchor to the active worktree target
- Apply the unique patch to the active worktree file
- Update the supervisor files
- Run the declared validation command after advancing to `S5`

Forbidden:

- Broad exploration
- Patching the snapshot file
- Patching the legacy distractor
- Patching unrelated dirty files
- Extra patch candidates
- Extra tests or commands not declared by the ledger
