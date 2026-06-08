# Auto-Advance Harness Template

This template exists to regression-test one specific property of the Codex
control plane:

- from a minimal prompt such as `继续，不要停`
- read the live supervisor pack first
- execute the already-unlocked patch action
- advance the phase
- run the declared validation command
- report the result
- all in one uninterrupted turn

The template uses `__HARNESS_ROOT__` placeholders. Materialize a fresh runnable
case with:

```bash
/home/example/.codex/control_plane/scripts/materialize_autoadvance_harness.sh /tmp/my_case
```

Then run a one-shot regression manually:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C /tmp/my_case '继续，不要停'
```

Or run the batch regression:

```bash
/home/example/.codex/control_plane/scripts/run_autoadvance_regression.sh 3
```
