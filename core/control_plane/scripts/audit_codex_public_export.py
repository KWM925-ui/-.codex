#!/usr/bin/env python3
"""Audit a portable public export of the Codex-home functional surfaces."""

import argparse
import fnmatch
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


MISSING_EXPORT_ROOT = "__missing_export_root__"

REQUIRED_PATHS = [
    "core/control_plane",
    "core/control_plane/scripts",
    "core/control_plane/tests",
    "core/control_plane/templates",
    "core/control_plane/scripts/run_codex_home_acceptance.py",
    "core/control_plane/scripts/project_task_workflow.py",
    "core/skills",
]

FORBIDDEN_ROOT_ENTRIES = {
    ".tmp",
    "auth.json",
    "cache",
    "config.toml",
    "history",
    "logs_2.sqlite",
    "memories",
    "models_cache.json",
    "project_assets",
    "runtime",
    "session_index.jsonl",
    "sessions",
    "sessions_archive",
    "shell_snapshots",
    "state_5.sqlite",
    "tmp",
}

FORBIDDEN_ANYWHERE_NAMES = {
    "auth.json",
    "session_index.jsonl",
}

FORBIDDEN_ANYWHERE_DIRS = {
    ".tmp",
    "archived_sessions",
    "history",
    "memories",
    "pandeng_supervisor",
    "project_assets",
    "runtime",
    "sessions",
    "sessions_archive",
    "shell_snapshots",
    "system_cleanup_supervisor",
    "upstream_audit",
    "worktree_snapshots",
}

FORBIDDEN_PATTERNS = [
    "*.sqlite",
    "*.sqlite-shm",
    "*.sqlite-wal",
    "logs_*.sqlite*",
    "state_*.sqlite*",
]


@dataclass
class Check:
    name: str
    ok: bool
    details: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check that a public .codex export contains function surfaces only.",
    )
    parser.add_argument(
        "--export-root",
        required=True,
        help="Root of the candidate public export repository.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser


def _export_root(raw_root: str) -> Path:
    if raw_root == MISSING_EXPORT_ROOT:
        raise ValueError("release gate requires --export-root")
    root = Path(raw_root).expanduser().resolve()
    if not root.exists():
        raise ValueError("export root does not exist: %s" % root)
    if not root.is_dir():
        raise ValueError("export root must be a directory: %s" % root)
    return root


def _check_required_paths(root: Path) -> List[Check]:
    checks = []
    for relpath in REQUIRED_PATHS:
        path = root / relpath
        checks.append(
            Check(
                name="required:%s" % relpath,
                ok=path.exists(),
                details="present" if path.exists() else "missing",
            )
        )
    return checks


def _check_forbidden_root_entries(root: Path) -> List[Check]:
    present = sorted(name for name in FORBIDDEN_ROOT_ENTRIES if (root / name).exists())
    return [
        Check(
            name="forbidden_root_entries",
            ok=not present,
            details="none" if not present else ", ".join(present),
        )
    ]


def _is_forbidden_pattern(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in FORBIDDEN_PATTERNS)


def _check_forbidden_tree_entries(root: Path) -> List[Check]:
    offenders = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_current = current.relative_to(root)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname != ".git" and dirname not in {"__pycache__"}
        ]
        for dirname in list(dirnames):
            if dirname in FORBIDDEN_ANYWHERE_DIRS:
                offenders.append((rel_current / dirname).as_posix())
        for filename in filenames:
            relpath = (rel_current / filename).as_posix()
            if filename in FORBIDDEN_ANYWHERE_NAMES or _is_forbidden_pattern(filename):
                offenders.append(relpath)
    offenders = sorted(offenders)
    return [
        Check(
            name="forbidden_tree_entries",
            ok=not offenders,
            details="none" if not offenders else ", ".join(offenders[:20]),
        )
    ]


def _check_symlinks(root: Path) -> List[Check]:
    symlinks = []
    for path in root.rglob("*"):
        if ".git" in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            symlinks.append(path.relative_to(root).as_posix())
    return [
        Check(
            name="symlink_free_export",
            ok=not symlinks,
            details="none" if not symlinks else ", ".join(sorted(symlinks)[:20]),
        )
    ]


def audit_export(root: Path) -> List[Check]:
    checks = []
    checks.extend(_check_required_paths(root))
    checks.extend(_check_forbidden_root_entries(root))
    checks.extend(_check_forbidden_tree_entries(root))
    checks.extend(_check_symlinks(root))
    return checks


def main() -> int:
    args = _build_parser().parse_args()
    try:
        root = _export_root(args.export_root)
        checks = audit_export(root)
        ok = all(check.ok for check in checks)
        payload = {
            "ok": ok,
            "export_root": root.as_posix(),
            "checks": [asdict(check) for check in checks],
            "plain_result": (
                "公开导出只包含功能面，没有发现本地热数据或私有资产。"
                if ok
                else "公开导出存在缺失功能面或本地私有/运行态污染。"
            ),
        }
    except Exception as exc:  # noqa: BLE001 - CLI should report cleanly
        payload = {
            "ok": False,
            "export_root": args.export_root,
            "checks": [],
            "plain_result": "公开导出审计无法运行。",
            "error": str(exc),
        }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["plain_result"])
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
