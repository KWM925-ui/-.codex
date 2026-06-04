# Repeatability/Widening State Machine

## Auto-Advance Rule

When a phase promotion rule is satisfied, do not stop by default. Update the
live supervisor files and continue in the same turn.

## Phase Label Invariant

Only these phase labels are valid in this harness:

- `S6: Repeatability Validation`
- `S7: Widening Validation`

Do not invent a new phase label. After widening passes, keep `Current Phase` at
`S7`; record completion in the ledger instead.

### `S6: Repeatability Validation`

Goal:

- Re-run the declared repeatability validation after a prior patch-and-run
  success.

Promotion rule:

- The declared repeatability validation command passes.

Default action once entered:

- Run repeatability validation immediately.
- Advance to `S7` and run widening validation in the same turn.

### `S7: Widening Validation`

Goal:

- Run the declared widening validation and judge pass or fail.

Promotion rule:

- The declared widening validation command passes.

Default action once entered:

- Run the widening validation immediately if it has not already run in this
  turn.
- Update the live pack to completed state in the ledger only.
- Stop only after reporting whether the late-phase auto-advance succeeded.

## Current Phase

Current phase is `S6: Repeatability Validation`.

## Phase-Specific Allowed Actions For Current Phase

Allowed:

- Read files
- Run the declared repeatability validation command
- Advance to `S7`
- Run the declared widening validation command
- Update the supervisor files

Forbidden:

- Broad exploration
- Any code patch
- Touching the dirty note or generated noise files
- Extra tests or commands not declared by the ledger
