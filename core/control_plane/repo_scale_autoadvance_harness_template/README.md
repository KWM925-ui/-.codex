# Repo-Scale Auto-Advance Harness Template

This template exists to regression-test a higher-fidelity control-plane
property than the toy harnesses:

- from a minimal prompt such as `继续，不要停`
- attach to a live `S4` patch frontier
- remap a stale clean-snapshot anchor to the active worktree target
- respect a dirty multi-file worktree boundary
- apply the one unique minimal patch
- advance to `S5`
- run the declared validation command in the same turn
- keep unrelated dirty or off-path files unchanged

The template uses `__HARNESS_ROOT__` placeholders. Materialize a fresh runnable
case with:

```bash
/home/example/.codex/control_plane/scripts/materialize_repo_scale_autoadvance_harness.sh /tmp/my_case
```

Then run a one-shot regression manually:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C /tmp/my_case '继续，不要停'
```

Or run the batch regression:

```bash
/home/example/.codex/control_plane/scripts/run_repo_scale_autoadvance_regression.sh 3
```
