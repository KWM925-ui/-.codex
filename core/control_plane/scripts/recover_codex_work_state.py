#!/usr/bin/env python3
"""Build a read-only recovery card for interrupted Codex-home work."""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from run_codex_home_acceptance import _check_hygiene
from summarize_supervisor_current_state import (
    DEFAULT_PACK_ROOT,
    summarize_supervisor_current_state,
)


DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
TASK_RUNTIME_SESSIONS = ".codex/task_runtime/sessions"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print a read-only recovery card for resuming interrupted work. "
            "It does not read or emit raw session transcripts."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--pack-root",
        default=str(DEFAULT_PACK_ROOT),
        help="Supervisor pack root.",
    )
    parser.add_argument(
        "--project-root",
        default="",
        help="Optional target project root for project-local task pointers.",
    )
    parser.add_argument(
        "--session-key",
        default=os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("TERM_SESSION_ID")
        or "default",
        help="Project-local task session key. Defaults to CODEX_SESSION_ID, TERM_SESSION_ID, or default.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _project_task_pointer(project_root: Optional[Path], session_key: str) -> Dict[str, Any]:
    if project_root is None:
        return {
            "enabled": False,
            "plain_result": "没有指定项目目录；恢复卡只检查全局 supervisor 状态。",
        }
    session_path = project_root / TASK_RUNTIME_SESSIONS / ("%s.json" % session_key)
    if not session_path.exists():
        return {
            "enabled": True,
            "session_key": session_key,
            "active_task": None,
            "task_status": None,
            "ok": True,
            "plain_result": "该项目会话没有 active task 指针。",
        }
    session_data = _read_json(session_path)
    if not session_data:
        return {
            "enabled": True,
            "session_key": session_key,
            "active_task": None,
            "task_status": None,
            "ok": False,
            "plain_result": "项目会话指针不是有效 JSON，恢复前需要人工检查。",
        }
    active_task = session_data.get("active_task")
    if not isinstance(active_task, str) or not active_task:
        return {
            "enabled": True,
            "session_key": session_key,
            "active_task": active_task,
            "task_status": None,
            "ok": False,
            "plain_result": "项目会话指针缺少 active_task，恢复前需要人工检查。",
        }
    task_dir = (project_root / active_task).resolve()
    try:
        task_dir.relative_to(project_root.resolve())
    except ValueError:
        return {
            "enabled": True,
            "session_key": session_key,
            "active_task": active_task,
            "task_status": None,
            "ok": False,
            "plain_result": "项目会话指针逃逸项目目录，不能自动恢复。",
        }
    task_data = _read_json(task_dir / "task.json")
    if not task_data:
        return {
            "enabled": True,
            "session_key": session_key,
            "active_task": active_task,
            "task_status": None,
            "ok": False,
            "plain_result": "active task 缺少有效 task.json，恢复前需要人工检查。",
        }
    status = task_data.get("status")
    return {
        "enabled": True,
        "session_key": session_key,
        "active_task": active_task,
        "task_status": status,
        "implementation_confirmed": bool(task_data.get("implementation_confirmed")),
        "ok": status in {"planning", "in_progress"},
        "plain_result": (
            "项目会话有 active task：%s，状态是 %s。"
            % (active_task, status or "未知")
        ),
    }


def _next_action(supervisor: Dict[str, Any], project_task: Dict[str, Any]) -> str:
    state = supervisor.get("frontier_status", {}).get("state")
    if state == "blocked":
        return "先解决 supervisor 记录的阻塞点，必要时问用户。"
    if state == "active":
        return "继续 supervisor 当前唯一边界，不要扩大范围。"
    if project_task.get("enabled") and project_task.get("active_task"):
        return "先核对项目 active task，再决定是否继续实施。"
    if state == "complete":
        return "当前边界已完成；继续前先开新的单一优化面。"
    return "状态不可靠；先人工核对 supervisor ledger。"


def build_recovery_card(
    root: Path,
    pack_root: Path,
    project_root: Optional[Path],
    session_key: str,
) -> Dict[str, Any]:
    supervisor = summarize_supervisor_current_state(pack_root)
    hygiene = _check_hygiene(root)
    project_task = _project_task_pointer(project_root, session_key)
    blocking_reasons: List[str] = []
    if supervisor.get("frontier_status", {}).get("state") == "unknown":
        blocking_reasons.append("supervisor frontier state is unknown")
    if not hygiene.ok:
        blocking_reasons.append("hygiene check found residue")
    if project_task.get("enabled") and not project_task.get("ok", True):
        blocking_reasons.append("project task pointer is invalid")
    ok = not blocking_reasons
    return {
        "ok": ok,
        "root": root.as_posix(),
        "pack_root": pack_root.as_posix(),
        "project_root": project_root.as_posix() if project_root else "",
        "supervisor": supervisor,
        "project_task": project_task,
        "hygiene": {
            "ok": hygiene.ok,
            "summary": hygiene.summary,
            "details": hygiene.details,
        },
        "next_action": _next_action(supervisor, project_task),
        "blocking_reasons": blocking_reasons,
        "privacy": {
            "read_only": True,
            "raw_session_text_read": False,
            "raw_session_text_emitted": False,
            "mutated_files": False,
            "persistent_report_files": False,
        },
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("恢复结论：%s" % ("可以继续" if payload["ok"] else "需要先处理阻塞"))
    print("下一步：%s" % payload["next_action"])
    supervisor = payload.get("supervisor", {})
    print("最新轮次：%s" % (supervisor.get("latest_round_heading") or "未识别"))
    print("当前状态：%s" % supervisor.get("frontier_status", {}).get("plain_result", "未识别"))
    project_task = payload.get("project_task", {})
    print("项目任务：%s" % project_task.get("plain_result", "未检查"))
    print("卫生状态：%s" % payload.get("hygiene", {}).get("summary", "未检查"))
    blockers = payload.get("blocking_reasons") or []
    if blockers:
        print("阻塞原因：")
        for blocker in blockers:
            print("- %s" % blocker)


def main() -> int:
    args = _build_parser().parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else None
    payload = build_recovery_card(
        Path(args.root).resolve(),
        Path(args.pack_root).resolve(),
        project_root,
        args.session_key,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
