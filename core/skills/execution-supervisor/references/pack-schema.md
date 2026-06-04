# Pack Schema

A supervisor pack is the external control surface for a long-running task.

Required files:

- `README.md`
  Purpose:
  - identify the project, workspace, objective, and primary child session
  - define read order and pack ownership
- `supervisor_ledger.md`
  Purpose:
  - live source of truth for the current frontier
  - records what was newly locked, demoted, and what remains
  Minimum sections:
  - `Locked Facts`
  - `Newly Locked This Round`
  - `Newly Demoted This Round`
  - `Current Frontier`
  - `Only Question Next Round`
  - `Forbidden Next Round`
  - `Promotion Gate`
- `state_machine.md`
  Purpose:
  - define phases and promotion rules
  - prevent premature runs or patches
- `child_execution_protocol.md`
  Purpose:
  - define per-round operating procedure
  - define output shape and what counts as real progress
- `round_self_checklist.md`
  Purpose:
  - force end-of-round self-audit before claiming progress
- `activate_supervisor_mode.md`
  Purpose:
  - hold the exact activation message used to switch a child session under pack
    control

Recommended design rules:

- Keep exactly one live ledger per active task stream.
- Make the ledger narrower than the state machine.
- Put timeless rules in `state_machine.md` and `child_execution_protocol.md`.
- Put current-task frontier and exclusions only in `supervisor_ledger.md`.
- When the task changes materially, either:
  - update the same pack if it is the same task stream
  - or start a new pack if the objective changed

What the ledger should not contain:

- broad project documentation
- old prompt dumps
- speculative branch sets that are no longer live
- prose-only summaries without a current frontier
