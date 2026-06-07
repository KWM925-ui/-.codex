#!/usr/bin/env python3
"""Manage project-local task workflow packs for Codex-assisted work.

The workflow files are written into the target repository, not into the global
Codex home unless that repository is explicitly selected as the project root.
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = 1
WORKFLOW_KIND = "codex_project_task"
TASKS_DIR = ".codex/tasks"
SESSION_DIR = ".codex/task_runtime/sessions"
VALID_STATUSES = {"planning", "in_progress", "completed", "archived"}
CONTEXT_TARGETS = {"implement": "implement.jsonl", "check": "check.jsonl"}
BLOCKED_CONTEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".lua",
    ".m",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}
ALLOWED_CONTEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".md",
    ".rst",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _today_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "task"


def _project_root(raw_root: str) -> Path:
    root = Path(raw_root).expanduser().resolve()
    if not root.exists():
        raise ValueError("project root does not exist: %s" % root)
    if not root.is_dir():
        raise ValueError("project root must be a directory: %s" % root)
    return root


def _tasks_root(project_root: Path) -> Path:
    return project_root / TASKS_DIR


def _session_root(project_root: Path) -> Path:
    return project_root / SESSION_DIR


def _session_key(explicit: str = "") -> str:
    key = explicit or os.environ.get("CODEX_SESSION_ID") or os.environ.get("TERM_SESSION_ID")
    if not key:
        key = "default"
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", key)[:120] or "default"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_path(project_root: Path, task_id_or_path: str) -> Path:
    candidate = Path(task_id_or_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    direct = (project_root / candidate).resolve()
    if direct.exists() and direct.is_dir():
        return direct
    return (_tasks_root(project_root) / task_id_or_path).resolve()


def _ensure_inside_project(project_root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(project_root)
    except ValueError as exc:
        raise ValueError("path escapes project root: %s" % path) from exc


def _task_json_path(task_dir: Path) -> Path:
    return task_dir / "task.json"


def _load_task(task_dir: Path) -> Dict[str, Any]:
    path = _task_json_path(task_dir)
    if not path.is_file():
        raise ValueError("missing task.json: %s" % path)
    data = _load_json(path)
    if data.get("workflow_kind") != WORKFLOW_KIND:
        raise ValueError("not a Codex project task: %s" % path)
    return data


def _store_task(task_dir: Path, data: Dict[str, Any]) -> None:
    data["updated_at"] = _utc_now()
    _write_json(_task_json_path(task_dir), data)


def _task_readme(task_id: str, title: str) -> str:
    return """# Project Task

Task: `{task_id}`

Title: {title}

Read order:

1. `task.json`
2. `prd.md`
3. `design.md` if the task is not trivial
4. `implement.md` before code changes
5. `implement.jsonl` and `check.jsonl` for stable context references
6. `research/` and `lessons.md` when present

Rules:

- Creating this task records planning state only.
- Starting implementation requires an explicit plan-review confirmation.
- Context manifests point to stable instructions, specs, docs, or research;
  they do not list source files that are about to be modified.
""".format(task_id=task_id, title=title)


def _prd_template(title: str, description: str) -> str:
    return """# PRD

## User Request

{title}

## Description

{description}

## Must Ask Before Work

- If the goal, success criteria, safety boundary, or expected output is unclear,
  ask the user before implementation.

## Acceptance Criteria

- TODO: replace with concrete checks before implementation starts.

## Out Of Scope

- TODO: list what this task must not touch.
""".format(title=title, description=description or "TODO: fill in the user-visible goal.")


def _design_template() -> str:
    return """# Design

Use this file for non-trivial tasks.

## Boundaries

- TODO: affected modules, files, APIs, and protected paths.

## Approach

- TODO: chosen approach and why it is safer than alternatives.

## Risks

- TODO: expected blast radius and rollback point.
"""


def _implement_template() -> str:
    return """# Implementation Plan

Do not start code changes until the user has reviewed the plan and the task has
been started with `project_task_workflow.py start --confirm-plan-reviewed`.

## Steps

1. TODO: first bounded change.
2. TODO: validation command.

## Validation

- TODO: exact command or manual check proving success.
"""


def _lessons_template() -> str:
    return """# Lessons

Capture only reusable knowledge here.

Do not copy raw session logs, secrets, or one-off run noise. If a lesson should
survive future tasks, promote it into the repository's project instructions or
spec docs after user review.
"""


def _set_active_task(project_root: Path, task_dir: Path, session_key: str) -> None:
    session_path = _session_root(project_root) / ("%s.json" % session_key)
    rel_task_dir = task_dir.relative_to(project_root).as_posix()
    _write_json(
        session_path,
        {
            "schema_version": SCHEMA_VERSION,
            "workflow_kind": WORKFLOW_KIND,
            "session_key": session_key,
            "active_task": rel_task_dir,
            "updated_at": _utc_now(),
        },
    )


def _active_task(project_root: Path, session_key: str) -> Optional[Path]:
    path = _session_root(project_root) / ("%s.json" % session_key)
    if not path.exists():
        return None
    try:
        data = _load_json(path)
        return _resolve_active_task_path(project_root, data.get("active_task"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _resolve_active_task_path(project_root: Path, active_task: Any) -> Optional[Path]:
    if not isinstance(active_task, str) or not active_task.strip():
        return None
    active_path = (project_root / active_task).resolve()
    _ensure_inside_project(project_root, active_path)
    return active_path


def _clear_active_task(project_root: Path, task_dir: Path) -> None:
    sessions = _session_root(project_root)
    if not sessions.exists():
        return
    task_dir = task_dir.resolve()
    for session_path in sessions.glob("*.json"):
        try:
            data = _load_json(session_path)
        except (OSError, json.JSONDecodeError):
            continue
        try:
            active_path = _resolve_active_task_path(project_root, data.get("active_task"))
        except ValueError:
            continue
        if active_path == task_dir:
            session_path.unlink()


def _context_relpath(project_root: Path, raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = project_root / path
    path = path.resolve()
    _ensure_inside_project(project_root, path)
    if not path.exists():
        raise ValueError("context file does not exist: %s" % path)
    if not path.is_file():
        raise ValueError("context path must be a file: %s" % path)
    return path.relative_to(project_root).as_posix()


def _context_path_is_allowed(relpath: str) -> Tuple[bool, str]:
    path = Path(relpath)
    suffix = path.suffix.lower()
    if suffix in BLOCKED_CONTEXT_SUFFIXES:
        return False, "source-like file is not allowed in context manifests"
    if suffix in ALLOWED_CONTEXT_SUFFIXES:
        return True, "allowed stable context file"
    if relpath in {"AGENTS.md", "README.md"}:
        return True, "allowed repository instruction file"
    return False, "unsupported context file type"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid jsonl at %s:%d: %s" % (path, index, exc)) from exc
    return rows


def _validate_task(project_root: Path, task_dir: Path) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    required_files = [
        "README.md",
        "task.json",
        "prd.md",
        "design.md",
        "implement.md",
        "implement.jsonl",
        "check.jsonl",
        "lessons.md",
    ]
    required_dirs = ["research"]
    for filename in required_files:
        if not (task_dir / filename).is_file():
            issues.append({"path": (task_dir / filename).as_posix(), "problem": "missing file"})
    for dirname in required_dirs:
        if not (task_dir / dirname).is_dir():
            issues.append({"path": (task_dir / dirname).as_posix(), "problem": "missing directory"})

    try:
        data = _load_task(task_dir)
    except Exception as exc:  # noqa: BLE001 - surface validation issue in JSON output
        issues.append({"path": _task_json_path(task_dir).as_posix(), "problem": str(exc)})
        return issues

    status = data.get("status")
    if status not in VALID_STATUSES:
        issues.append({"path": _task_json_path(task_dir).as_posix(), "problem": "invalid status"})
    if status == "in_progress" and not data.get("implementation_confirmed"):
        issues.append(
            {
                "path": _task_json_path(task_dir).as_posix(),
                "problem": "in_progress without plan-review confirmation",
            }
        )

    for target, filename in CONTEXT_TARGETS.items():
        manifest_path = task_dir / filename
        try:
            rows = _read_jsonl(manifest_path)
        except ValueError as exc:
            issues.append({"path": manifest_path.as_posix(), "problem": str(exc)})
            continue
        for row in rows:
            relpath = row.get("file")
            reason = row.get("reason")
            if not relpath or not reason:
                issues.append(
                    {
                        "path": manifest_path.as_posix(),
                        "problem": "%s context row must include file and reason" % target,
                    }
                )
                continue
            context_path = (project_root / relpath).resolve()
            try:
                _ensure_inside_project(project_root, context_path)
            except ValueError as exc:
                issues.append({"path": manifest_path.as_posix(), "problem": str(exc)})
                continue
            if not context_path.exists():
                issues.append({"path": relpath, "problem": "context file missing"})
            allowed, message = _context_path_is_allowed(relpath)
            if not allowed:
                issues.append({"path": relpath, "problem": message})
    return issues


def _validate_session_pointers(project_root: Path) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    sessions = _session_root(project_root)
    if not sessions.exists():
        return issues
    for session_path in sorted(sessions.glob("*.json")):
        try:
            data = _load_json(session_path)
        except Exception as exc:  # noqa: BLE001 - report bad session metadata
            issues.append({"path": session_path.as_posix(), "problem": str(exc)})
            continue
        if data.get("workflow_kind") != WORKFLOW_KIND:
            issues.append({"path": session_path.as_posix(), "problem": "invalid workflow_kind"})
            continue
        try:
            active_path = _resolve_active_task_path(project_root, data.get("active_task"))
        except ValueError as exc:
            issues.append({"path": session_path.as_posix(), "problem": str(exc)})
            continue
        if active_path is None:
            issues.append({"path": session_path.as_posix(), "problem": "missing active_task"})
            continue
        if not active_path.exists():
            issues.append({"path": session_path.as_posix(), "problem": "active task missing"})
            continue
        try:
            task_data = _load_task(active_path)
        except Exception as exc:  # noqa: BLE001 - report bad task target
            issues.append({"path": session_path.as_posix(), "problem": str(exc)})
            continue
        if task_data.get("status") not in {"planning", "in_progress"}:
            issues.append(
                {
                    "path": session_path.as_posix(),
                    "problem": "active task must be planning or in_progress",
                }
            )
    return issues


def _iter_task_dirs(project_root: Path, include_archive: bool = False) -> Iterable[Path]:
    root = _tasks_root(project_root)
    if not root.exists():
        return []
    paths = [path for path in root.iterdir() if path.is_dir() and path.name != "archive"]
    if include_archive:
        archive = root / "archive"
        if archive.exists():
            paths.extend(path for path in archive.glob("*/*") if path.is_dir())
    return sorted(paths, key=lambda item: item.as_posix())


def command_create(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    if not args.title.strip():
        raise ValueError("task title is required")
    slug = _slugify(args.slug or args.title)
    task_id = "%s-%s" % (_today_id(), slug)
    task_dir = _tasks_root(project_root) / task_id
    if task_dir.exists():
        raise ValueError("task already exists: %s" % task_dir)

    now = _utc_now()
    task_dir.mkdir(parents=True)
    (task_dir / "research").mkdir()
    data = {
        "schema_version": SCHEMA_VERSION,
        "workflow_kind": WORKFLOW_KIND,
        "id": task_id,
        "title": args.title,
        "description": args.description or "",
        "status": "planning",
        "priority": args.priority,
        "creator": args.creator or "",
        "assignee": args.assignee or args.creator or "",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "archived_at": None,
        "implementation_confirmed": False,
        "plan_reviewed_by": None,
        "session_key": _session_key(args.session_key),
        "artifacts": {
            "prd": "prd.md",
            "design": "design.md",
            "implement": "implement.md",
            "implement_context": "implement.jsonl",
            "check_context": "check.jsonl",
            "research": "research/",
            "lessons": "lessons.md",
        },
        "meta": {},
    }
    _write_json(_task_json_path(task_dir), data)
    _write_text(task_dir / "README.md", _task_readme(task_id, args.title))
    _write_text(task_dir / "prd.md", _prd_template(args.title, args.description or ""))
    _write_text(task_dir / "design.md", _design_template())
    _write_text(task_dir / "implement.md", _implement_template())
    _write_text(task_dir / "implement.jsonl", "")
    _write_text(task_dir / "check.jsonl", "")
    _write_text(task_dir / "lessons.md", _lessons_template())
    if not args.no_set_active:
        _set_active_task(project_root, task_dir, _session_key(args.session_key))
    return {
        "ok": True,
        "action": "create",
        "task_id": task_id,
        "task_dir": task_dir.as_posix(),
        "status": "planning",
        "implementation_allowed": False,
        "plain_result": "任务包已创建，但只处于计划状态；还不能开始改代码。",
    }


def command_start(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    task_dir = _task_path(project_root, args.task)
    _ensure_inside_project(project_root, task_dir)
    data = _load_task(task_dir)
    if not args.confirm_plan_reviewed:
        raise ValueError("starting implementation requires --confirm-plan-reviewed")
    if data["status"] not in {"planning", "in_progress"}:
        raise ValueError("task cannot start from status: %s" % data["status"])
    data["status"] = "in_progress"
    data["started_at"] = data.get("started_at") or _utc_now()
    data["implementation_confirmed"] = True
    data["plan_reviewed_by"] = args.reviewed_by or "user"
    _store_task(task_dir, data)
    _set_active_task(project_root, task_dir, _session_key(args.session_key))
    return {
        "ok": True,
        "action": "start",
        "task_id": data["id"],
        "status": "in_progress",
        "plain_result": "计划已确认，任务进入实施状态。",
    }


def command_add_context(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    task_dir = _task_path(project_root, args.task)
    _ensure_inside_project(project_root, task_dir)
    _load_task(task_dir)
    relpath = _context_relpath(project_root, args.file)
    allowed, message = _context_path_is_allowed(relpath)
    if not allowed:
        raise ValueError(message + ": " + relpath)
    reason = args.reason.strip()
    if not reason:
        raise ValueError("context reason is required")
    row = {"file": relpath, "reason": reason}
    manifest_path = task_dir / CONTEXT_TARGETS[args.target]
    _append_jsonl(manifest_path, row)
    return {
        "ok": True,
        "action": "add-context",
        "target": args.target,
        "file": relpath,
        "plain_result": "已把稳定上下文引用加入 %s，不会把源码整包塞进上下文。" % manifest_path.name,
    }


def command_complete(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    task_dir = _task_path(project_root, args.task)
    _ensure_inside_project(project_root, task_dir)
    data = _load_task(task_dir)
    if data["status"] != "in_progress" and not args.force:
        raise ValueError("complete requires in_progress status unless --force is used")
    if not args.evidence and not args.force:
        raise ValueError("complete requires --evidence unless --force is used")
    data["status"] = "completed"
    data["completed_at"] = _utc_now()
    if args.evidence:
        data.setdefault("meta", {})["completion_evidence"] = args.evidence
    _store_task(task_dir, data)
    _clear_active_task(project_root, task_dir)
    return {
        "ok": True,
        "action": "complete",
        "task_id": data["id"],
        "status": "completed",
        "plain_result": "任务已标记完成，并清除了会话当前任务指针。",
    }


def command_archive(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    task_dir = _task_path(project_root, args.task)
    _ensure_inside_project(project_root, task_dir)
    data = _load_task(task_dir)
    if data["status"] != "completed" and not args.force:
        raise ValueError("archive requires completed status unless --force is used")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    archive_dir = _tasks_root(project_root) / "archive" / month / task_dir.name
    if archive_dir.exists():
        raise ValueError("archive target already exists: %s" % archive_dir)
    data["status"] = "archived"
    data["archived_at"] = _utc_now()
    _store_task(task_dir, data)
    _clear_active_task(project_root, task_dir)
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(task_dir.as_posix(), archive_dir.as_posix())
    _clear_active_task(project_root, archive_dir)
    return {
        "ok": True,
        "action": "archive",
        "task_id": data["id"],
        "archive_dir": archive_dir.as_posix(),
        "plain_result": "任务已归档到项目本地 archive，不影响全局会话历史。",
    }


def command_status(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    session_key = _session_key(args.session_key)
    active = _active_task(project_root, session_key)
    tasks = []
    for task_dir in _iter_task_dirs(project_root, include_archive=args.include_archive):
        try:
            data = _load_task(task_dir)
        except Exception:  # noqa: BLE001 - status should keep going
            continue
        tasks.append(
            {
                "id": data["id"],
                "title": data["title"],
                "status": data["status"],
                "task_dir": task_dir.as_posix(),
            }
        )
    return {
        "ok": True,
        "action": "status",
        "session_key": session_key,
        "active_task": active.as_posix() if active else None,
        "tasks": tasks,
    }


def command_validate(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = _project_root(args.project_root)
    issues: List[Dict[str, str]] = []
    for task_dir in _iter_task_dirs(project_root, include_archive=args.include_archive):
        issues.extend(_validate_task(project_root, task_dir))
    issues.extend(_validate_session_pointers(project_root))
    return {
        "ok": not issues,
        "action": "validate",
        "issue_count": len(issues),
        "issues": issues,
        "plain_result": (
            "项目任务包结构有效。"
            if not issues
            else "项目任务包存在结构或上下文清单问题。"
        ),
    }


def _add_common_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        default=".",
        help="Target repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and validate lightweight project-local Codex task packs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a planning-only task pack.")
    _add_common_project_args(create)
    create.add_argument("title")
    create.add_argument("--slug", default="")
    create.add_argument("--description", default="")
    create.add_argument("--priority", default="P2", choices=["P0", "P1", "P2", "P3"])
    create.add_argument("--creator", default="")
    create.add_argument("--assignee", default="")
    create.add_argument("--session-key", default="")
    create.add_argument("--no-set-active", action="store_true")
    create.set_defaults(func=command_create)

    start = subparsers.add_parser("start", help="Start implementation after plan review.")
    _add_common_project_args(start)
    start.add_argument("task")
    start.add_argument("--session-key", default="")
    start.add_argument("--confirm-plan-reviewed", action="store_true")
    start.add_argument("--reviewed-by", default="")
    start.set_defaults(func=command_start)

    add_context = subparsers.add_parser("add-context", help="Add stable context to a manifest.")
    _add_common_project_args(add_context)
    add_context.add_argument("task")
    add_context.add_argument("target", choices=sorted(CONTEXT_TARGETS))
    add_context.add_argument("file")
    add_context.add_argument("reason")
    add_context.set_defaults(func=command_add_context)

    complete = subparsers.add_parser("complete", help="Mark a task completed.")
    _add_common_project_args(complete)
    complete.add_argument("task")
    complete.add_argument("--evidence", default="")
    complete.add_argument("--force", action="store_true")
    complete.set_defaults(func=command_complete)

    archive = subparsers.add_parser("archive", help="Archive a completed task.")
    _add_common_project_args(archive)
    archive.add_argument("task")
    archive.add_argument("--force", action="store_true")
    archive.set_defaults(func=command_archive)

    status = subparsers.add_parser("status", help="Show active task and task list.")
    _add_common_project_args(status)
    status.add_argument("--session-key", default="")
    status.add_argument("--include-archive", action="store_true")
    status.set_defaults(func=command_status)

    validate = subparsers.add_parser("validate", help="Validate project-local task packs.")
    _add_common_project_args(validate)
    validate.add_argument("--include-archive", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("失败：%s" % exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        plain = payload.get("plain_result")
        if plain:
            print(plain)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
