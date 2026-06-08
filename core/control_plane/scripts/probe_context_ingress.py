#!/usr/bin/env python3
"""Run a report-only context-firewall probe over real Codex session records."""

import argparse
import json
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from context_firewall_lib import DEFAULT_ROOT, curate_context
from curated_context_redaction import redact_curated_result


SOURCE_RELEVANCE = {
    "repo_state": 0.80,
    "repo_instructions": 0.85,
    "user_message": 0.85,
    "operator_contract": 0.75,
    "global_control": 0.75,
    "tool_output": 0.65,
    "session_memory": 0.25,
    "retrieved_web": 0.55,
    "untrusted_external": 0.45,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe real Codex session ingress through the context firewall without mutating runtime state.",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument(
        "--session",
        help="Session JSONL file to probe. Defaults to the newest file under <root>/sessions.",
    )
    parser.add_argument(
        "--profile",
        default="balanced",
        help="Compaction profile id. Defaults to balanced.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=10000,
        help="Maximum recent JSONL records to inspect from the selected session.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=60,
        help="Maximum candidate ingress items to send through the firewall.",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=8000,
        help="Maximum characters retained per candidate before probing.",
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


def _latest_session(root: Path) -> Path:
    candidates = [
        path
        for path in (root / "sessions").rglob("*.jsonl")
        if path.is_file()
    ]
    if not candidates:
        raise FileNotFoundError("no session JSONL files found under %s" % (root / "sessions"))
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    candidate = value
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness_days(timestamp: Any) -> Optional[int]:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    delta = datetime.now(timezone.utc) - parsed
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 86400)


def _text_from_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _text_from_content(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("message"), str):
            return value["message"]
        if isinstance(value.get("output"), str):
            return value["output"]
        return ""
    return ""


def _safe_json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)


def _read_recent_records(
    session_path: Path,
    max_lines: int,
) -> Tuple[List[Tuple[int, Dict[str, Any]]], Dict[str, Any]]:
    recent: Deque[Tuple[int, Dict[str, Any]]] = deque(maxlen=max(1, max_lines))
    first_meta: Optional[Tuple[int, Dict[str, Any]]] = None
    total_lines = 0
    parsed_records = 0
    bad_json_records = 0
    with session_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            total_lines = line_no
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                bad_json_records += 1
                continue
            if not isinstance(record, dict):
                continue
            parsed_records += 1
            if first_meta is None and record.get("type") == "session_meta":
                first_meta = (line_no, record)
            recent.append((line_no, record))

    records = list(recent)
    if first_meta is not None and all(item[0] != first_meta[0] for item in records):
        records.insert(0, first_meta)
    return records, {
        "total_lines": total_lines,
        "parsed_records": parsed_records,
        "bad_json_records": bad_json_records,
        "inspected_records": len(records),
        "max_lines": max_lines,
    }


def _candidate(
    *,
    item_id: str,
    source_class: str,
    content: str,
    timestamp: Any,
    origin_type: str,
    line_no: int,
    session_path: Path,
    max_content_chars: int,
    memory_kind: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not content.strip():
        return None
    original_chars = len(content)
    if original_chars > max_content_chars:
        content = content[:max_content_chars].rstrip()
    item = {
        "id": item_id,
        "title": "%s:%s" % (origin_type, line_no),
        "path": session_path.as_posix(),
        "source_class": source_class,
        "content": content,
        "relevance_score": SOURCE_RELEVANCE[source_class],
        "freshness_days": _freshness_days(timestamp),
        "_probe_origin_type": origin_type,
        "_probe_line_no": line_no,
        "_probe_original_chars": original_chars,
        "_probe_input_chars": len(content),
    }
    if memory_kind is not None:
        item["memory_kind"] = memory_kind
    return item


def _items_from_record(
    line_no: int,
    record: Dict[str, Any],
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    timestamp = record.get("timestamp")
    record_type = record.get("type")
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}

    if record_type == "session_meta":
        return _items_from_session_meta(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )

    if record_type == "turn_context":
        return _items_from_turn_context(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )

    if record_type == "compacted":
        return _items_from_compacted(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )

    if record_type == "event_msg":
        return _items_from_event_msg(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )

    if record_type == "response_item":
        return _items_from_response_item(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )
    return []


def _single_candidate(candidate: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [candidate] if candidate is not None else []


def _items_from_session_meta(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    content = _safe_json_text(
        {
            "cwd": payload.get("cwd"),
            "originator": payload.get("originator"),
            "source": payload.get("source"),
            "cli_version": payload.get("cli_version"),
            "model_provider": payload.get("model_provider"),
        }
    )
    return _single_candidate(
        _candidate(
            item_id="line-%d-session-meta" % line_no,
            source_class="repo_state",
            content=content,
            timestamp=timestamp or payload.get("timestamp"),
            origin_type="session_meta",
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
            memory_kind="project_fact",
        )
    )


def _items_from_turn_context(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    content = _safe_json_text(
        {
            "cwd": payload.get("cwd"),
            "current_date": payload.get("current_date"),
            "timezone": payload.get("timezone"),
            "approval_policy": payload.get("approval_policy"),
            "sandbox_policy": payload.get("sandbox_policy"),
            "model": payload.get("model"),
        }
    )
    return _single_candidate(
        _candidate(
            item_id="line-%d-turn-context" % line_no,
            source_class="repo_state",
            content=content,
            timestamp=timestamp,
            origin_type="turn_context",
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
            memory_kind="volatile_task_state",
        )
    )


def _items_from_compacted(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    return _single_candidate(
        _candidate(
            item_id="line-%d-compacted" % line_no,
            source_class="session_memory",
            content=_text_from_content(payload) or _safe_json_text(payload),
            timestamp=timestamp,
            origin_type="compacted",
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
        )
    )


def _event_payload_content_and_source(
    payload: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    event_type = payload.get("type")
    if event_type == "user_message":
        return (
            payload.get("message") or _text_from_content(payload.get("text_elements")),
            "user_message",
            event_type,
        )
    if event_type == "agent_message":
        return payload.get("message", ""), "session_memory", event_type
    if event_type == "patch_apply_end":
        return (
            _safe_json_text(
                {
                    "status": payload.get("status"),
                    "success": payload.get("success"),
                    "stdout": payload.get("stdout"),
                    "stderr": payload.get("stderr"),
                    "changes": payload.get("changes"),
                }
            ),
            "tool_output",
            event_type,
        )
    if event_type == "web_search_end":
        return (
            _safe_json_text(
                {
                    "action": payload.get("action"),
                    "query": payload.get("query"),
                    "status": payload.get("status"),
                }
            ),
            "retrieved_web",
            event_type,
        )
    return None, None, None


def _items_from_event_msg(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    content, source_class, event_type = _event_payload_content_and_source(payload)
    if content is None or source_class is None or event_type is None:
        return []
    return _single_candidate(
        _candidate(
            item_id="line-%d-event-%s" % (line_no, event_type),
            source_class=source_class,
            content=content,
            timestamp=timestamp,
            origin_type="event_msg:%s" % event_type,
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
        )
    )


def _message_source_class(role: Any) -> str:
    if role == "developer":
        return "global_control"
    if role == "user":
        return "user_message"
    return "session_memory"


def _response_item_candidate(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> Optional[Dict[str, Any]]:
    payload_type = payload.get("type")
    if payload_type == "message":
        role = payload.get("role")
        return _candidate(
            item_id="line-%d-message-%s" % (line_no, role or "unknown"),
            source_class=_message_source_class(role),
            content=_text_from_content(payload.get("content")),
            timestamp=timestamp,
            origin_type="response_item:message:%s" % (role or "unknown"),
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
        )
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        return _candidate(
            item_id="line-%d-%s" % (line_no, payload_type),
            source_class="tool_output",
            content=payload.get("output", ""),
            timestamp=timestamp,
            origin_type="response_item:%s" % payload_type,
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
        )
    if payload_type == "reasoning":
        return _candidate(
            item_id="line-%d-reasoning-summary" % line_no,
            source_class="session_memory",
            content=_text_from_content(payload.get("summary")),
            timestamp=timestamp,
            origin_type="response_item:reasoning",
            line_no=line_no,
            session_path=session_path,
            max_content_chars=max_content_chars,
        )
    return None


def _items_from_response_item(
    line_no: int,
    payload: Dict[str, Any],
    timestamp: Any,
    session_path: Path,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    return _single_candidate(
        _response_item_candidate(
            line_no,
            payload,
            timestamp,
            session_path,
            max_content_chars,
        )
    )


def _dedupe_keep_recent(items: Iterable[Dict[str, Any]], max_candidates: int) -> List[Dict[str, Any]]:
    all_items = list(items)
    if len(all_items) <= max_candidates:
        return all_items

    anchors: List[Dict[str, Any]] = []
    for source_class in ("repo_state", "global_control", "user_message"):
        for item in reversed(all_items):
            if item["source_class"] == source_class:
                anchors.append(item)
                break

    selected: List[Dict[str, Any]] = []
    seen = set()
    for item in anchors + list(reversed(all_items)):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        selected.append(item)
        if len(selected) >= max_candidates:
            break
    selected.sort(key=lambda item: item["_probe_line_no"])
    return selected


def build_context_ingress_candidates(
    root: Path,
    session_path: Optional[Path],
    max_lines: int,
    max_candidates: int,
    max_content_chars: int,
) -> Dict[str, Any]:
    """Read one session once and return candidate items plus redacted metadata.

    The returned ``candidates`` still contain content for in-process firewall
    evaluation. Callers must not serialize them directly.
    """
    selected_session = (session_path or _latest_session(root)).resolve()
    if not selected_session.is_file():
        raise FileNotFoundError(
            "session JSONL file does not exist: %s" % selected_session
        )
    records, parse_summary = _read_recent_records(selected_session, max_lines)
    candidates: List[Dict[str, Any]] = []
    for line_no, record in records:
        candidates.extend(
            _items_from_record(
                line_no,
                record,
                selected_session,
                max_content_chars,
            )
        )
    candidates = _dedupe_keep_recent(candidates, max_candidates)

    candidate_source_counts = Counter(item["source_class"] for item in candidates)
    candidate_origin_counts = Counter(item["_probe_origin_type"] for item in candidates)
    session_stat = selected_session.stat()
    return {
        "selected_session": selected_session,
        "source_session": {
            "path": selected_session.as_posix(),
            "size_bytes": session_stat.st_size,
            "mtime": datetime.fromtimestamp(
                session_stat.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        },
        "parse_summary": parse_summary,
        "candidate_summary": {
            "total_candidates": len(candidates),
            "by_source_class": dict(sorted(candidate_source_counts.items())),
            "by_origin_type": dict(sorted(candidate_origin_counts.items())),
            "max_candidates": max_candidates,
            "max_content_chars": max_content_chars,
        },
        "candidates": candidates,
    }


def build_context_ingress_probe(
    root: Path,
    session_path: Optional[Path],
    profile: str,
    max_lines: int,
    max_candidates: int,
    max_content_chars: int,
) -> Dict[str, Any]:
    candidate_bundle = build_context_ingress_candidates(
        root,
        session_path,
        max_lines,
        max_candidates,
        max_content_chars,
    )
    candidates = candidate_bundle["candidates"]
    probe_payload = {"items": candidates, "budget_profile": profile}
    curated = curate_context(root, probe_payload, requested_profile=profile)
    redacted = redact_curated_result(curated, candidates)

    return {
        "root": root.as_posix(),
        "layout_version": curated.get("layout_version"),
        "profile": profile,
        "source_session": candidate_bundle["source_session"],
        "privacy": {
            "report_only": True,
            "raw_content_emitted": False,
            "rendered_context_emitted": False,
            "mutated_files": False,
            "automatic_runtime_hook": False,
            "memory_store_mutation": False,
        },
        "parse_summary": candidate_bundle["parse_summary"],
        "candidate_summary": candidate_bundle["candidate_summary"],
        "curation": redacted,
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("profile: %s" % payload["profile"])
    print("source_session: %s" % payload["source_session"]["path"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("parse_summary: %s" % json.dumps(payload["parse_summary"], ensure_ascii=False, sort_keys=True))
    print("candidate_summary: %s" % json.dumps(payload["candidate_summary"], ensure_ascii=False, sort_keys=True))
    print("curation_summary: %s" % json.dumps(payload["curation"]["summary"], ensure_ascii=False, sort_keys=True))
    print("")
    print("curated_items:")
    for item in payload["curation"]["curated_items"]:
        print(
            "- %s | %s | %s | action=%s | treatment=%s | flags=%s | chars=%s/%s"
            % (
                item["id"],
                item["source_class"],
                item["origin_type"],
                item["relevance_action"],
                item["treatment"],
                ",".join(item["flags"]) if item["flags"] else "(none)",
                item["kept_chars"],
                item["input_chars"],
            )
        )
    print("")
    print("review_items:")
    for item in payload["curation"]["review_items"]:
        print("- %s | %s | %s" % (item["id"], item["source_class"], item["reason"]))
    print("")
    print("rejected_items:")
    for item in payload["curation"]["rejected_items"]:
        print(
            "- %s | %s | %s"
            % (item.get("id"), item.get("source_class"), item.get("reason"))
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()
    session = Path(args.session).resolve() if args.session else None
    max_lines = _positive_int(parser, "--max-lines", args.max_lines)
    max_candidates = _positive_int(parser, "--max-candidates", args.max_candidates)
    max_content_chars = _positive_int(
        parser,
        "--max-content-chars",
        args.max_content_chars,
    )
    try:
        payload = build_context_ingress_probe(
            root,
            session,
            args.profile,
            max_lines,
            max_candidates,
            max_content_chars,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
