# Mock Late-Phase Work Rules

- This is a control-plane harness, not a real project.
- Fresh local evidence only.
- No code edits are allowed in this harness.
- Only the declared validation commands may be executed.
- `docs/operator_notes.md` is a pre-existing dirty tracked file and must stay
  unchanged.
- Generated noise files under `logs/` and `.tmp/` must stay unchanged.
- After the repeatability command passes, advance to widening immediately in
  the same turn.
