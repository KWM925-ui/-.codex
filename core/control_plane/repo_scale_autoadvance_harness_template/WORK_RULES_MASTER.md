# Mock Repo-Scale Work Rules

- This is a control-plane harness, not the real Pandeng project.
- Fresh local evidence only.
- The only code edit allowed is the unique patch in
  `src/stack/front_end/progress_budget.py`.
- `snapshots/clean/` is evidence only and must stay unchanged.
- `src/stack/front_end/legacy_progress_budget.py` is an off-path distractor and
  must stay unchanged.
- The pre-existing dirty note in `docs/operator_notes.md` must stay unchanged.
- Generated noise files under `logs/` and `.tmp/` must stay unchanged.
- After patching, run the declared validation command immediately if the phase
  allows it.
