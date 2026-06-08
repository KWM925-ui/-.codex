#!/usr/bin/env python3
"""Report lifecycle candidates without moving, deleting, or reading content."""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from codex_home_policy_lib import DEFAULT_ROOT, load_json
from review_runtime_reversible_targets import build_runtime_reversible_review


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Review cache/temp/session lifecycle candidates in report-only mode. "
            "This command does not read session content and never mutates files."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument(
        "--large-session-mb",
        type=int,
        default=100,
        help="Flag session JSONL files at or above this size. Defaults to 100.",
    )
    parser.add_argument(
        "--old-session-days",
        type=int,
        default=30,
        help="Flag session JSONL files at or above this age. Defaults to 30.",
    )
    parser.add_argument(
        "--large-runtime-mb",
        type=int,
        default=25,
        help="Flag runtime cache/temp surfaces at or above this size. Defaults to 25.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum candidate files to show per bucket. Defaults to 20.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    return parser


def _positive_int(parser: argparse.ArgumentParser, name: str, value: int) -> int:
    if value < 1:
        parser.error("%s must be >= 1" % name)
    return value


def _age_days(mtime: float, now: datetime) -> int:
    modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
    delta = now - modified
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 86400)


def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _scan_tree(root: Path, relpath: str, max_items: int, now: datetime) -> Dict[str, Any]:
    base = root / relpath
    summary = {
        "path": relpath,
        "exists": base.exists(),
        "kind": "missing",
        "total_bytes": 0,
        "file_count": 0,
        "dir_count": 0,
        "symlink_count": 0,
        "largest_files": [],
    }
    if not base.exists():
        return summary
    if base.is_symlink():
        summary["kind"] = "symlink"
        summary["symlink_count"] = 1
        return summary
    if base.is_file():
        stat = _safe_stat(base)
        summary["kind"] = "file"
        if stat is not None:
            summary["total_bytes"] = stat.st_size
            summary["file_count"] = 1
            summary["largest_files"] = [
                {
                    "path": relpath,
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                    "age_days": _age_days(stat.st_mtime, now),
                }
            ]
        return summary

    largest: List[Dict[str, Any]] = []
    summary["kind"] = "dir"
    for child in base.rglob("*"):
        if child.is_symlink():
            summary["symlink_count"] += 1
            continue
        if child.is_dir():
            summary["dir_count"] += 1
            continue
        if not child.is_file():
            continue
        stat = _safe_stat(child)
        if stat is None:
            continue
        summary["file_count"] += 1
        summary["total_bytes"] += stat.st_size
        largest.append(
            {
                "path": _relative(root, child),
                "size_bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
                "age_days": _age_days(stat.st_mtime, now),
            }
        )
    largest.sort(key=lambda item: item["size_bytes"], reverse=True)
    summary["largest_files"] = largest[:max_items]
    return summary


def _session_file_candidates(
    root: Path,
    max_items: int,
    large_session_bytes: int,
    old_session_days: int,
    now: datetime,
) -> List[Dict[str, Any]]:
    session_root = root / "sessions"
    candidates: List[Dict[str, Any]] = []
    if not session_root.exists():
        return candidates
    for path in session_root.rglob("*.jsonl"):
        if path.is_symlink() or not path.is_file():
            continue
        stat = _safe_stat(path)
        if stat is None:
            continue
        age = _age_days(stat.st_mtime, now)
        reasons = []
        if stat.st_size >= large_session_bytes:
            reasons.append("large_session_file")
        if age >= old_session_days:
            reasons.append("old_session_file")
        if not reasons:
            continue
        candidates.append(
            {
                "path": _relative(root, path),
                "size_bytes": stat.st_size,
                "age_days": age,
                "mtime": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
                "reasons": reasons,
                "recommended_action": "archive_with_continuity_plan_only",
                "requires_manual_review": True,
            }
        )
    candidates.sort(key=lambda item: (item["size_bytes"], item["age_days"]), reverse=True)
    return candidates[:max_items]


def _runtime_surface_candidates(
    root: Path,
    max_items: int,
    large_runtime_bytes: int,
    now: datetime,
) -> List[Dict[str, Any]]:
    runtime_review = build_runtime_reversible_review(root)
    candidates: List[Dict[str, Any]] = []
    for target in runtime_review.get("targets", []):
        relpath = target["target"]
        scan = _scan_tree(root, relpath, max_items, now)
        reasons = []
        if scan["total_bytes"] >= large_runtime_bytes:
            reasons.append("large_runtime_surface")
        if target.get("runtime_category") == "temp" and scan["file_count"] > 0:
            reasons.append("temp_surface_has_files")
        if target.get("runtime_category") == "cache":
            reasons.append("rebuildable_cache_surface")
        candidates.append(
            {
                "target": relpath,
                "runtime_category": target.get("runtime_category"),
                "retention_class": target.get("retention_class"),
                "size_bytes": scan["total_bytes"],
                "file_count": scan["file_count"],
                "dir_count": scan["dir_count"],
                "symlink_count": scan["symlink_count"],
                "reasons": reasons,
                "largest_files": scan["largest_files"],
                "recommended_action": target.get("recommended_action"),
                "operator_bias": target.get("operator_bias"),
                "requires_manual_review": True,
                "mutation_performed": False,
            }
        )
    candidates.sort(key=lambda item: item["size_bytes"], reverse=True)
    return candidates


def _history_bucket_summaries(
    root: Path,
    max_items: int,
    now: datetime,
) -> List[Dict[str, Any]]:
    history_registry = load_json(root / "history/history_surface_registry.json")
    archive_categories = {"sessions", "memory", "shell_snapshots"}
    summaries = []
    for entry in history_registry.get("surfaces", []):
        if entry.get("category") not in archive_categories:
            continue
        scan = _scan_tree(root, entry["root_path"], max_items, now)
        summaries.append(
            {
                "target": entry["root_path"],
                "history_category": entry["category"],
                "retention_role": entry.get("retention_role"),
                "size_bytes": scan["total_bytes"],
                "file_count": scan["file_count"],
                "dir_count": scan["dir_count"],
                "largest_files": scan["largest_files"],
                "recommended_action": "archive_with_continuity_plan_only",
                "requires_manual_review": True,
                "mutation_performed": False,
            }
        )
    summaries.sort(key=lambda item: item["size_bytes"], reverse=True)
    return summaries


def build_lifecycle_candidate_review(
    root: Path,
    large_session_mb: int = 100,
    old_session_days: int = 30,
    large_runtime_mb: int = 25,
    max_items: int = 20,
) -> Dict[str, Any]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    operations = load_json(
        root / "core/control_plane/codex_home_lifecycle_operations.json"
    )
    candidate_bundle = _build_lifecycle_candidate_bundle(
        root,
        large_session_mb,
        old_session_days,
        large_runtime_mb,
        max_items,
    )
    runtime_candidates = candidate_bundle["runtime_candidates"]
    session_candidates = candidate_bundle["session_candidates"]
    history_summaries = candidate_bundle["history_summaries"]
    runtime_reasons = _reason_counts(runtime_candidates)
    session_reasons = _reason_counts(session_candidates)
    return {
        "root": root.as_posix(),
        "layout_version": manifest.get("layout_version"),
        "privacy": _lifecycle_privacy_report(),
        "thresholds": {
            "large_session_mb": large_session_mb,
            "old_session_days": old_session_days,
            "large_runtime_mb": large_runtime_mb,
            "max_items": max_items,
        },
        "operator_constraints": _operator_constraints(operations),
        "summary": _lifecycle_summary(
            runtime_candidates,
            session_candidates,
            history_summaries,
            runtime_reasons,
            session_reasons,
        ),
        "operator_sequence": _operator_sequence(),
        "runtime_candidates": runtime_candidates,
        "session_file_candidates": session_candidates,
        "history_bucket_summaries": history_summaries,
    }


def _build_lifecycle_candidate_bundle(
    root: Path,
    large_session_mb: int,
    old_session_days: int,
    large_runtime_mb: int,
    max_items: int,
) -> Dict[str, List[Dict[str, Any]]]:
    now = datetime.now(timezone.utc)
    runtime_candidates = _runtime_surface_candidates(
        root,
        max_items,
        large_runtime_mb * 1024 * 1024,
        now,
    )
    session_candidates = _session_file_candidates(
        root,
        max_items,
        large_session_mb * 1024 * 1024,
        old_session_days,
        now,
    )
    history_summaries = _history_bucket_summaries(root, max_items, now)
    return {
        "runtime_candidates": runtime_candidates,
        "session_candidates": session_candidates,
        "history_summaries": history_summaries,
    }


def _reason_counts(items: List[Dict[str, Any]]) -> Counter:
    return Counter(
        reason
        for item in items
        for reason in item.get("reasons", [])
    )


def _lifecycle_privacy_report() -> Dict[str, bool]:
    return {
        "report_only": True,
        "raw_session_content_read": False,
        "raw_session_content_emitted": False,
        "mutated_files": False,
        "hard_delete_performed": False,
        "runtime_rotation_performed": False,
        "archive_move_performed": False,
    }


def _operator_constraints(operations: Dict[str, Any]) -> Dict[str, Any]:
    global_rules = operations["global_rules"]
    return {
        "manual_review_required": True,
        "allow_hard_delete": global_rules["allow_hard_delete"],
        "allow_hot_path_physical_move": global_rules["allow_hot_path_physical_move"],
        "preferred_reversible_action": global_rules["preferred_reversible_action"],
    }


def _lifecycle_summary(
    runtime_candidates: List[Dict[str, Any]],
    session_candidates: List[Dict[str, Any]],
    history_summaries: List[Dict[str, Any]],
    runtime_reasons: Counter,
    session_reasons: Counter,
) -> Dict[str, Any]:
    return {
        "runtime_candidate_count": len(runtime_candidates),
        "session_candidate_count": len(session_candidates),
        "history_bucket_count": len(history_summaries),
        "runtime_reasons": dict(sorted(runtime_reasons.items())),
        "session_reasons": dict(sorted(session_reasons.items())),
        "largest_history_bucket": (
            history_summaries[0]["target"] if history_summaries else None
        ),
    }


def _operator_sequence() -> List[str]:
    return [
        "Review candidates only; this command never moves or deletes files.",
        "For sessions, preserve session_index.jsonl continuity before any future archive action.",
        "For cache/temp, prefer reversible quarantine or rotation and keep root lookup paths stable.",
        "Run layout and context-firewall audits after any separately approved lifecycle action.",
    ]


def _print_bytes(value: int) -> str:
    if value >= 1024 * 1024 * 1024:
        return "%.1fG" % (value / float(1024 * 1024 * 1024))
    if value >= 1024 * 1024:
        return "%.1fM" % (value / float(1024 * 1024))
    if value >= 1024:
        return "%.1fK" % (value / float(1024))
    return "%dB" % value


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("thresholds: %s" % json.dumps(payload["thresholds"], ensure_ascii=False, sort_keys=True))
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("operator_constraints: %s" % json.dumps(payload["operator_constraints"], ensure_ascii=False, sort_keys=True))
    print("")
    print("runtime_candidates:")
    for item in payload["runtime_candidates"]:
        print(
            "- %s | %s | files=%s | size=%s | reasons=%s"
            % (
                item["target"],
                item["runtime_category"],
                item["file_count"],
                _print_bytes(item["size_bytes"]),
                ",".join(item["reasons"]) if item["reasons"] else "(none)",
            )
        )
    print("")
    print("session_file_candidates:")
    for item in payload["session_file_candidates"]:
        print(
            "- %s | size=%s | age_days=%s | reasons=%s"
            % (
                item["path"],
                _print_bytes(item["size_bytes"]),
                item["age_days"],
                ",".join(item["reasons"]),
            )
        )
    print("")
    print("history_bucket_summaries:")
    for item in payload["history_bucket_summaries"]:
        print(
            "- %s | files=%s | size=%s"
            % (
                item["target"],
                item["file_count"],
                _print_bytes(item["size_bytes"]),
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    large_session_mb = _positive_int(parser, "--large-session-mb", args.large_session_mb)
    old_session_days = _positive_int(parser, "--old-session-days", args.old_session_days)
    large_runtime_mb = _positive_int(parser, "--large-runtime-mb", args.large_runtime_mb)
    max_items = _positive_int(parser, "--max-items", args.max_items)
    payload = build_lifecycle_candidate_review(
        Path(args.root).resolve(),
        large_session_mb,
        old_session_days,
        large_runtime_mb,
        max_items,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
