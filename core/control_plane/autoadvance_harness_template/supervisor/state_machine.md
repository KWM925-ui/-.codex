# Mock State Machine

## Auto-Advance Rule

When a phase promotion rule is satisfied, do not stop by default. Update the
live supervisor files and continue in the same turn.

## Phase Label Invariant

Only these phase labels are valid in this harness:

- `S4: Patch Candidate Formation`
- `S5: Low-Pollution Validation`

Do not invent `Completed` or any other new phase label. After validation
passes, keep `Current Phase` at `S5`; record completion in the ledger instead.

### `S4: Patch Candidate Formation`

Goal:

- Apply one uniquely locked minimal patch candidate.

Promotion rule:

- The patch candidate is uniquely locked and proof plan is complete.

Default action once entered:

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
- Apply the unique patch
- Update the supervisor files
- Run the declared validation command after advancing to `S5`

Forbidden:

- Broad exploration
- Extra patch candidates
- Extra tests or commands not declared by the ledger
