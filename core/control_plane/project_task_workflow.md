# Project Task Workflow

Purpose:

- Provide a lightweight project-local task lifecycle for Codex-assisted work.
- Keep global `.codex` controls generic while each repository stores its own
  task state, planning artifacts, validation evidence, and reusable lessons.
- Avoid direct dependency on Trellis or any generated multi-platform harness.

Canonical command:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py
```

## Storage Model

Project-local task files live under the target repository:

```text
.codex/
├── tasks/
│   ├── YYYYMMDD-task-slug/
│   │   ├── README.md
│   │   ├── task.json
│   │   ├── prd.md
│   │   ├── design.md
│   │   ├── implement.md
│   │   ├── implement.jsonl
│   │   ├── check.jsonl
│   │   ├── research/
│   │   └── lessons.md
│   └── archive/YYYY-MM/
└── task_runtime/
    └── sessions/<session-key>.json
```

The global Codex home provides the script, templates, and tests. The target
repository owns the generated task files.

## Required Behavior

- If the user intent, success criteria, safety boundary, or expected output is
  unclear, ask before creating or starting a task.
- Creating a task records planning state only. It is not permission to edit
  code.
- Starting implementation is a separate step and requires
  `--confirm-plan-reviewed`.
- `implement.jsonl` and `check.jsonl` contain stable context references only:
  repository instructions, specs, docs, or task research. They must not list
  source files that are about to be modified.
- Completion requires validation evidence unless the operator explicitly uses
  a force override.
- Archive is project-local bookkeeping; it must not mutate global sessions,
  memories, runtime databases, auth files, provider settings, or model config.

## Task Triage

When there is no active project task:

- Simple conversation: answer directly; do not create a task by default.
- Small contained edit: ask whether a project task is useful; if the user says
  no, work inline.
- Multi-file, ambiguous, risky, long-running, or acceptance-style work: ask
  whether to create a project task and enter planning.

User consent to create a task does not imply user consent to start implementation.

## Command Flow

Create planning state:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  create "Add login flow" --project-root /path/to/repo --json
```

Add stable context:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  add-context 20260608-add-login-flow implement docs/auth.md \
  "Authentication design constraints" --project-root /path/to/repo --json
```

Start only after plan review:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  start 20260608-add-login-flow --confirm-plan-reviewed \
  --project-root /path/to/repo --json
```

Validate project task packs:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  validate --project-root /path/to/repo --json
```

Complete with evidence, then archive:

```bash
python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  complete 20260608-add-login-flow --evidence "pytest passed" \
  --project-root /path/to/repo --json

python3 /home/example/.codex/core/control_plane/scripts/project_task_workflow.py \
  archive 20260608-add-login-flow --project-root /path/to/repo --json
```

## Relation To Existing Control Plane

- Use `project-bootstrap` when entering a repository that lacks project-local
  instructions.
- Use this project task workflow when a concrete task needs recoverable
  planning, implementation, checking, and knowledge capture.
- Use `execution-supervisor` when the task is long-running, debugging-heavy,
  acceptance-style, or vulnerable to drift.
- A project task can point to a supervisor pack, but it does not replace the
  supervisor ledger for hard debugging or certification work.
