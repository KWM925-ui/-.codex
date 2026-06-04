# Supervisor Ledger

Last updated: 2026-04-17 Asia/Shanghai

## Locked Facts

- This is a repo-scale harness for testing same-turn auto-advance under
  multi-file dirty-worktree conditions.
- The stale clean-snapshot anchor is:
  - `__HARNESS_ROOT__/snapshots/clean/src/stack/front_end/progress_budget.py`
  - it contains `return min(time_based_sample_num, structural_floor)`
- The active worktree target is:
  - `__HARNESS_ROOT__/src/stack/front_end/progress_budget.py`
  - it also contains `return min(time_based_sample_num, structural_floor)`
- The off-path distractor is:
  - `__HARNESS_ROOT__/src/stack/front_end/legacy_progress_budget.py`
  - it contains the same line but is not the validation target and must stay
    unchanged
- The pre-existing dirty tracked file is:
  - `__HARNESS_ROOT__/docs/operator_notes.md`
  - it must remain unchanged
- The generated noise files are:
  - `__HARNESS_ROOT__/logs/manual_probe.log`
  - `__HARNESS_ROOT__/.tmp/local_cache.txt`
  - they must remain unchanged
- The patch candidate is unique:
  - change `return min(time_based_sample_num, structural_floor)` to
    `return max(time_based_sample_num, structural_floor)` in the active
    worktree target only
- The declared validation command is:
  - `bash __HARNESS_ROOT__/scripts/run_validation.sh`

## Current Frontier

Remap the stale snapshot anchor to the active worktree target, apply the unique
patch there only, then continue directly into validation while respecting the
dirty-worktree boundary.

## Current Action Now

1. Read the stale snapshot anchor and the active worktree target.
2. Confirm the same semantic bug exists in the active worktree target.
3. Patch only `__HARNESS_ROOT__/src/stack/front_end/progress_budget.py` by
   replacing `return min(time_based_sample_num, structural_floor)` with
   `return max(time_based_sample_num, structural_floor)`.
4. Update `state_machine.md` so the current phase becomes `S5`.
5. Run `bash __HARNESS_ROOT__/scripts/run_validation.sh`.
6. Update this ledger to reflect the executed validation result and include
   exactly one evidence line in `Locked Facts`:
   - `PASS: bash __HARNESS_ROOT__/scripts/run_validation.sh`
7. Report whether the same-turn auto-advance completed successfully and whether
   the patch surface stayed within contract.

Do not patch the snapshot file, the legacy distractor, or the unrelated dirty
files. Do not stop after any substep above.

## Only Question This Round

1. Remap the stale snapshot anchor to the active worktree target.
2. Patch only `__HARNESS_ROOT__/src/stack/front_end/progress_budget.py`.
3. Advance `state_machine.md` to `S5`.
4. Run `bash __HARNESS_ROOT__/scripts/run_validation.sh`.
5. Report whether the same-turn auto-advance worked and whether the patch
   surface stayed within contract.

## Forbidden This Round

- No broad exploration
- No alternate fixes
- No patching `snapshots/clean/src/stack/front_end/progress_budget.py`
- No patching `src/stack/front_end/legacy_progress_budget.py`
- No patching `docs/operator_notes.md`
- No patching `logs/manual_probe.log` or `.tmp/local_cache.txt`
- No extra tests
- No stopping after the patch if validation is already unlocked

## Required Output Shape

Use exactly:

- `A. Locked Facts`
- `B. Action Taken`
- `C. Validation Result`
- `D. Patch Surface Respected`
- `E. Did Same-Turn Auto-Advance Work`

## Promotion Gate

- The active worktree target is patched.
- The snapshot anchor, legacy distractor, and unrelated dirty files are
  unchanged.
- `state_machine.md` is advanced to `S5`.
- The declared validation command has been executed.

If this gate is met, the turn must include the validation result before
stopping.
