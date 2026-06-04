# Supervisor Ledger

Last updated: 2026-04-17 Asia/Shanghai

## Locked Facts

- This is a toy harness for testing same-turn phase auto-advance.
- File `__HARNESS_ROOT__/math_bug.py` currently contains:
  - `return a - b`
- File `__HARNESS_ROOT__/test_math.py` expects:
  - `add(2, 3) == 5`
- The patch candidate is unique:
  - change `return a - b` to `return a + b`
- No other files require edits.

## Current Frontier

Apply the unique patch candidate in `math_bug.py`, then continue directly into
validation.

## Current Action Now

1. Patch `__HARNESS_ROOT__/math_bug.py` by replacing `return a - b` with
   `return a + b`.
2. Update `state_machine.md` so the current phase becomes `S5`.
3. Run `python3 __HARNESS_ROOT__/test_math.py`.
4. Update this ledger to reflect the executed validation result.
   Keep `state_machine.md` at `S5`; do not invent a `Completed` phase.
5. Report whether the same-turn auto-advance completed successfully.

Do not stop after any substep above.

## Only Question This Round

1. Patch `__HARNESS_ROOT__/math_bug.py` by replacing `return a - b` with
   `return a + b`.
2. Update `state_machine.md` so the current phase becomes `S5`.
3. Run `python3 __HARNESS_ROOT__/test_math.py`.
4. Report whether the same-turn auto-advance completed successfully.

## Forbidden This Round

- No broad exploration
- No alternate fixes
- No extra tests
- No stopping after the patch if validation is already unlocked

## Required Output Shape

Use exactly:

- `A. Locked Facts`
- `B. Action Taken`
- `C. Validation Result`
- `D. Did Same-Turn Auto-Advance Work`

## Promotion Gate

- The unique patch is applied.
- `state_machine.md` is advanced to `S5`.
- The declared validation command has been executed.

If this gate is met, the turn must include the validation result before
stopping.
