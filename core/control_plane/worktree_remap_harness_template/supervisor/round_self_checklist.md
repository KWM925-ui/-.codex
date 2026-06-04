# Round Self-Checklist

Answer these internally before stopping.

## Remap Checks

- Did I patch the clean snapshot instead of the active worktree file?
- Did I skip reading the active worktree file before patching?
- Did I stop after remapping or patching even though validation was unlocked?
- Did I report success without actually running the declared validation command?

If any answer is `yes`, the round is not ready to close.

## Scope Checks

- Did I broaden beyond the unique locked patch candidate?
- Did I run any extra command beyond the declared validation command?
- Did I add any unrelated code change?

If any answer is `yes`, the round violated the harness contract.
