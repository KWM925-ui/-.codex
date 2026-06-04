# Repeatability/Widening Auto-Advance Harness

This repository is a control-plane regression harness, not a real project.

## Read Order

1. `__HARNESS_ROOT__/supervisor/supervisor_ledger.md`
2. `__HARNESS_ROOT__/supervisor/state_machine.md`
3. `__HARNESS_ROOT__/supervisor/child_execution_protocol.md`
4. `__HARNESS_ROOT__/supervisor/round_self_checklist.md`
5. `__HARNESS_ROOT__/WORK_RULES_MASTER.md`

## Minimal Continue Contract

If the user says only `continue` or `继续，不要停`:

1. Read the supervisor pack first.
2. Restate only:
   - current phase
   - current frontier
   - current forbidden actions
3. Execute the ledger's current question immediately.
4. If the promotion gate is satisfied, update the live pack and continue into
   the next phase in the same turn without waiting for another user prompt.

## Hard Rules

- Do not broaden to unrelated exploration.
- Do not ask for permission for routine actions.
- Do not stop after repeatability if widening is already unlocked.
- Do not write any code patch in this harness.
- Do not touch the stale dirty note or generated noise files.
- Do not replace execution with a status-only summary when the run gate is
  already open.
