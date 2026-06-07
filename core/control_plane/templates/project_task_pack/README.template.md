# Project Task Pack Template

This template describes the files created under a target repository's
`.codex/tasks/<task-id>/` directory.

Required files:

- `task.json`: machine-readable task state.
- `prd.md`: user request, acceptance criteria, out-of-scope boundaries.
- `design.md`: technical design for non-trivial work.
- `implement.md`: ordered implementation and validation plan.
- `implement.jsonl`: stable context references for implementation.
- `check.jsonl`: stable context references for verification.
- `research/`: task-local evidence gathered during planning.
- `lessons.md`: reusable knowledge to consider promoting into project docs.

Hard boundary:

- Creating the task is not permission to edit code.
- Implementation starts only after explicit plan-review confirmation.
