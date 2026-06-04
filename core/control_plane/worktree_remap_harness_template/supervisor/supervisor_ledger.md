# Supervisor Ledger

Last updated: 2026-04-17 Asia/Shanghai

## Locked Facts

- This is a toy harness for testing worktree-anchor remap plus same-turn
  auto-advance.
- The clean snapshot anchor is:
  - `__HARNESS_ROOT__/snapshots/clean/math_bug.py`
  - it contains `return a - b`
- The active worktree target is:
  - `__HARNESS_ROOT__/math_bug.py`
  - it also contains `return a - b`
- Only the active worktree file may be edited.
- The snapshot file under `snapshots/clean/` must remain unchanged.
- The patch candidate is unique:
  - change `return a - b` to `return a + b` in the active worktree file
- No other files require code edits.

## Current Frontier

Remap the clean-snapshot anchor to the active worktree file, then apply the
unique patch candidate there and continue directly into validation.

## Current Action Now

1. Read `__HARNESS_ROOT__/snapshots/clean/math_bug.py` as the stale anchor.
2. Read `__HARNESS_ROOT__/math_bug.py` as the active worktree file.
3. Confirm the same semantic bug exists in the active worktree file.
4. Patch only `__HARNESS_ROOT__/math_bug.py` by replacing `return a - b` with
   `return a + b`.
5. Update `state_machine.md` so the current phase becomes `S5`.
6. Run `python3 __HARNESS_ROOT__/test_math.py`.
7. Update this ledger to reflect the executed validation result.
8. Report whether the same-turn auto-advance completed successfully.

Do not patch the snapshot file. Do not stop after any substep above.

## Only Question This Round

1. Remap the clean-snapshot anchor to the active worktree file.
2. Patch only `__HARNESS_ROOT__/math_bug.py` by replacing `return a - b` with
   `return a + b`.
3. Update `state_machine.md` so the current phase becomes `S5`.
4. Run `python3 __HARNESS_ROOT__/test_math.py`.
5. Report whether the same-turn auto-advance completed successfully.

## Forbidden This Round

- No broad exploration
- No alternate fixes
- No patching `snapshots/clean/math_bug.py`
- No extra tests
- No stopping after the patch if validation is already unlocked

## Required Output Shape

Use exactly:

- `A. Locked Facts`
- `B. Action Taken`
- `C. Validation Result`
- `D. Did Same-Turn Auto-Advance Work`

## Promotion Gate

- The active worktree file is patched.
- The clean snapshot file is unchanged.
- `state_machine.md` is advanced to `S5`.
- The declared validation command has been executed.

If this gate is met, the turn must include the validation result before
stopping.
