# Context Manifest Rules

`implement.jsonl` and `check.jsonl` are narrow lists of stable files to read.

Allowed examples:

```jsonl
{"file": "AGENTS.md", "reason": "Repository instructions"}
{"file": "docs/auth.md", "reason": "Authentication constraints"}
{"file": ".codex/tasks/20260608-example/research/options.md", "reason": "Task research"}
```

Do not list source files that are about to be modified. The agent should read
source files just in time during implementation or review.
