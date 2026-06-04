# Child Execution Protocol

## Round Start

1. Read `supervisor_ledger.md`.
2. Restate only:
   - current locked facts
   - current frontier
   - current forbidden actions

## During The Round

1. Solve only the ledger's `Only Question This Round`.
2. Do not broaden the search space.
3. Do not re-prove already locked facts.
4. If `Current Action Now` exists in the ledger, execute it instead of writing a
   status-only answer.

## Same-Turn Continuation Rule

If the current phase promotion gate is satisfied, you must:

1. update `supervisor_ledger.md`
2. update `state_machine.md` if the phase changes
3. continue into the next allowed phase action in the same turn

Do not stop merely because one intermediate report could be written.

## Run/Patch Gate

- No code patch is allowed in this harness.
- No run unless the current phase allows it.
- When the phase explicitly allows the next action, execute it without waiting
  for another user prompt.

## Round End

Before ending the round:

1. Run the checklist in `round_self_checklist.md`.
2. Ensure the live pack matches the actual executed state.
3. Emit only the required output shape from the ledger.
