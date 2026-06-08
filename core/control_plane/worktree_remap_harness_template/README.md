# Worktree Remap Harness Template

This template exists to regression-test a different control-plane property from
the basic auto-advance harness:

- the live frontier is anchored to a clean snapshot path and stale line map
- only the active worktree file may be edited
- Codex must remap the frontier to the active file before patching
- then it must continue through patch, phase advance, validation, and report in
  one uninterrupted turn

Materialize a fresh case with:

```bash
/home/example/.codex/control_plane/scripts/materialize_worktree_remap_harness.sh /tmp/my_remap_case
```

Run one regression manually with:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C /tmp/my_remap_case '继续，不要停'
```

Or run the batch regression:

```bash
/home/example/.codex/control_plane/scripts/run_worktree_remap_regression.sh 3
```
