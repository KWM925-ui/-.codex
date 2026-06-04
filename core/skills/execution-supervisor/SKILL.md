---
name: execution-supervisor
description: Use when a coding, debugging, research, or acceptance task spans multiple rounds and needs a live frontier or ledger, strict facts-vs-hypotheses separation, anti-drift controls, or supervision of another Codex session. Use to scaffold or run an externalized supervisor pack, keep one current frontier, prevent reopening ruled-out branches, and decide when runs or patches are allowed.
---

# Execution Supervisor

Use this skill when the task is long-running enough that "remembering the state in the chat" is no longer reliable.

Typical triggers:

- strict acceptance or certification-style work
- repeated debugging where the same branches keep getting reopened
- multi-session project continuation
- supervising another Codex session
- situations where wasted runs or patch sprawl are costly

## Core Workflow

1. If a supervisor pack does not exist yet, scaffold one with:

```bash
python "$CODEX_HOME/core/skills/execution-supervisor/scripts/init_supervisor_pack.py" \
  --root <pack_dir> \
  --project <project_name> \
  --workspace <workspace_path> \
  --session <child_session_jsonl_or_empty>
```

2. Read the pack in this order:
   - `supervisor_ledger.md`
   - `state_machine.md`
   - `child_execution_protocol.md`
   - `round_self_checklist.md`

3. At the start of each round, restate only:
   - locked facts
   - current frontier
   - forbidden actions
   - required output shape

   For Chinese-language work, make those visible labels Chinese and plain:
   `已锁定事实`, `当前要解的问题`, `本轮不能做的事`, and `本轮输出方式`.
   Keep exact technical identifiers verbatim, but explain cause/effect in
   Chinese instead of dumping English process labels.

4. Solve only the ledger's current question.

5. Before ending the round:
   - run the checklist mentally
   - update the ledger
   - then emit the final structured answer

6. Do not run formal experiments or write new patches unless the ledger and the
   phase gate both explicitly allow it.

## For Child-Session Supervision

- Use `scripts/extract_session_latest_round.py` to inspect a child session's
  latest completed round instead of manually tailing raw JSONL every time.
- Use the activation message template generated in the pack to put the child
  under supervisor control.
- Treat the ledger as the live source of truth. Do not summarize it loosely and
  then improvise.

## References

- Read [references/pack-schema.md](references/pack-schema.md) when defining or
  tightening the pack structure.
- Read [references/operating-rules.md](references/operating-rules.md) for
  anti-drift and progress rules.
- Read [references/activation-patterns.md](references/activation-patterns.md)
  when switching an existing child session into supervisor mode or handing work
  to a new session.
