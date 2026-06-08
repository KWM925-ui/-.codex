# Repeatability/Widening Auto-Advance Harness Template

This template exists to regression-test a later control-plane property than the
patch-and-run harnesses:

- from a minimal prompt such as `继续，不要停`
- attach to a live `S6` repeatability frontier after a prior patch/run success
- execute the declared repeatability validation immediately
- promote into `S7`
- execute the declared widening validation in the same turn
- keep code untouched and respect dirty-worktree boundaries

The template uses `__HARNESS_ROOT__` placeholders. Materialize a fresh runnable
case with:

```bash
/home/example/.codex/control_plane/scripts/materialize_repeatability_widening_harness.sh /tmp/my_case
```

Then run a one-shot regression manually:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C /tmp/my_case '继续，不要停'
```

Or run the batch regression:

```bash
/home/example/.codex/control_plane/scripts/run_repeatability_widening_regression.sh 3
```
