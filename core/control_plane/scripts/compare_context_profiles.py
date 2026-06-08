#!/usr/bin/env python3
"""Compare context-firewall profiles over one redacted session probe."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from context_firewall_lib import DEFAULT_ROOT, curate_context
from curated_context_redaction import redact_curated_result
from probe_context_ingress import (
    build_context_ingress_candidates,
)


DEFAULT_PROFILES = ["strict", "balanced", "exploratory"]


def default_profiles() -> List[str]:
    return list(DEFAULT_PROFILES)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare strict/balanced/exploratory context-firewall behavior "
            "against the same real session candidates without mutating runtime state."
        ),
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
        "--profiles",
        default=",".join(DEFAULT_PROFILES),
        help="Comma-separated profile ids. Defaults to strict,balanced,exploratory.",
    )
    parser.add_argument(
        "--baseline",
        default="balanced",
        help="Profile used as the delta baseline. Defaults to balanced.",
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


def _parse_profiles(value: str) -> List[str]:
    profiles = [item.strip() for item in value.split(",") if item.strip()]
    if not profiles:
        raise ValueError("at least one profile is required")
    seen = set()
    ordered = []
    for profile in profiles:
        if profile in seen:
            continue
        seen.add(profile)
        ordered.append(profile)
    return ordered


def parse_profiles(value: str) -> List[str]:
    return _parse_profiles(value)


def validate_positive_int(parser: argparse.ArgumentParser, name: str, value: int) -> int:
    if value < 1:
        parser.error("%s must be >= 1" % name)
    return value


def _count_by_source(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(item.get("source_class", "(unknown)") for item in items)
    return dict(sorted(counts.items()))


def _count_by_reason(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(item.get("reason", "(unknown)") for item in items)
    return dict(sorted(counts.items()))


def _profile_status(redacted: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    review_ids = {item["id"] for item in redacted.get("review_items", [])}
    status: Dict[str, Dict[str, Any]] = {}
    for item in redacted.get("curated_items", []):
        item_status = "review" if item["id"] in review_ids else "admitted"
        status[item["id"]] = {
            "status": item_status,
            "kept_chars": item.get("kept_chars"),
            "dropped_chars": item.get("dropped_chars"),
            "treatment": item.get("treatment"),
            "render_mode": item.get("render_mode"),
            "relevance_action": item.get("relevance_action"),
        }
    for item in redacted.get("rejected_items", []):
        status[item.get("id", "(unknown)")] = {
            "status": "rejected",
            "reason": item.get("reason"),
            "kept_chars": 0,
            "dropped_chars": None,
            "treatment": None,
            "render_mode": None,
            "relevance_action": item.get("relevance_action"),
        }
    return status


def _profile_report(profile: str, redacted: Dict[str, Any]) -> Dict[str, Any]:
    curated_items = redacted.get("curated_items", [])
    review_items = redacted.get("review_items", [])
    rejected_items = redacted.get("rejected_items", [])
    return {
        "profile": profile,
        "summary": redacted.get("summary", {}),
        "admitted_by_source_class": _count_by_source(curated_items),
        "review_by_source_class": _count_by_source(review_items),
        "rejected_by_source_class": _count_by_source(rejected_items),
        "rejected_by_reason": _count_by_reason(rejected_items),
        "flagged_by_source_class": _count_by_source(
            item for item in curated_items if item.get("flags")
        ),
    }


def _build_item_matrix(
    profiles: List[str],
    profile_statuses: Dict[str, Dict[str, Dict[str, Any]]],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metadata_by_id = {
        item["id"]: {
            "id": item["id"],
            "source_class": item["source_class"],
            "origin_type": item["_probe_origin_type"],
            "line_no": item["_probe_line_no"],
            "original_chars": item["_probe_original_chars"],
            "input_chars": item["_probe_input_chars"],
        }
        for item in candidates
    }
    all_ids = set(metadata_by_id)
    for statuses in profile_statuses.values():
        all_ids.update(statuses)

    def sort_key(item_id: str) -> Any:
        metadata = metadata_by_id.get(item_id, {})
        return (metadata.get("line_no", 10**12), item_id)

    matrix = []
    for item_id in sorted(all_ids, key=sort_key):
        entry = dict(metadata_by_id.get(item_id, {"id": item_id}))
        statuses = {
            profile: profile_statuses.get(profile, {}).get(
                item_id,
                {"status": "absent"},
            )
            for profile in profiles
        }
        entry["profile_statuses"] = statuses
        entry["status_changes"] = len(
            {value.get("status") for value in statuses.values()}
        ) > 1
        entry["kept_char_values"] = {
            profile: statuses[profile].get("kept_chars")
            for profile in profiles
            if statuses[profile].get("kept_chars") is not None
        }
        matrix.append(entry)
    return matrix


def _profile_deltas(
    baseline: str,
    profiles: List[str],
    per_profile: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    if baseline not in per_profile:
        return {}
    baseline_summary = per_profile[baseline]["summary"]
    deltas: Dict[str, Dict[str, int]] = {}
    for profile in profiles:
        summary = per_profile[profile]["summary"]
        deltas[profile] = {
            "admitted_items": summary.get("admitted_items", 0)
            - baseline_summary.get("admitted_items", 0),
            "rejected_items": summary.get("rejected_items", 0)
            - baseline_summary.get("rejected_items", 0),
            "review_items": summary.get("review_items", 0)
            - baseline_summary.get("review_items", 0),
            "total_chars": summary.get("total_chars", 0)
            - baseline_summary.get("total_chars", 0),
        }
    return deltas


def build_context_profile_comparison(
    root: Path,
    session_path: Optional[Path],
    profiles: List[str],
    baseline: str,
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
    per_profile: Dict[str, Dict[str, Any]] = {}
    statuses_by_profile: Dict[str, Dict[str, Dict[str, Any]]] = {}
    layout_version = None

    for profile in profiles:
        curated = curate_context(
            root,
            {"items": candidates, "budget_profile": profile},
            requested_profile=profile,
        )
        layout_version = layout_version or curated.get("layout_version")
        redacted = redact_curated_result(curated, candidates)
        statuses_by_profile[profile] = _profile_status(redacted)
        per_profile[profile] = _profile_report(profile, redacted)

    item_matrix = _build_item_matrix(profiles, statuses_by_profile, candidates)
    changed_items = [
        item
        for item in item_matrix
        if item["status_changes"]
        or len(set(item.get("kept_char_values", {}).values())) > 1
    ]
    profile_summaries = [per_profile[profile] for profile in profiles]
    total_chars_by_profile = {
        profile: per_profile[profile]["summary"].get("total_chars", 0)
        for profile in profiles
    }
    widest_profile = max(
        total_chars_by_profile,
        key=lambda profile: total_chars_by_profile[profile],
    ) if total_chars_by_profile else None
    narrowest_profile = min(
        total_chars_by_profile,
        key=lambda profile: total_chars_by_profile[profile],
    ) if total_chars_by_profile else None

    return {
        "root": root.as_posix(),
        "layout_version": layout_version,
        "profiles": profiles,
        "baseline_profile": baseline,
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
        "summary": {
            "profile_count": len(profiles),
            "total_candidates": len(candidates),
            "profiles": profiles,
            "baseline_profile": baseline,
            "widest_profile_by_chars": widest_profile,
            "narrowest_profile_by_chars": narrowest_profile,
            "items_with_profile_differences": len(changed_items),
        },
        "profile_summaries": profile_summaries,
        "profile_deltas_vs_baseline": _profile_deltas(
            baseline,
            profiles,
            per_profile,
        ),
        "changed_items": changed_items,
        "item_matrix": item_matrix,
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("profiles: %s" % ",".join(payload["profiles"]))
    print("baseline_profile: %s" % payload["baseline_profile"])
    print("source_session: %s" % payload["source_session"]["path"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("candidate_summary: %s" % json.dumps(payload["candidate_summary"], ensure_ascii=False, sort_keys=True))
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("")
    print("profile_summaries:")
    for item in payload["profile_summaries"]:
        summary = item["summary"]
        print(
            "- %s | admitted=%s | review=%s | rejected=%s | flagged=%s | chars=%s"
            % (
                item["profile"],
                summary.get("admitted_items"),
                summary.get("review_items"),
                summary.get("rejected_items"),
                summary.get("flagged_items"),
                summary.get("total_chars"),
            )
        )
    print("")
    print("profile_deltas_vs_baseline:")
    for profile, delta in payload["profile_deltas_vs_baseline"].items():
        print("- %s | %s" % (profile, json.dumps(delta, sort_keys=True)))
    print("")
    print("changed_items:")
    for item in payload["changed_items"]:
        statuses = {
            profile: item["profile_statuses"][profile]["status"]
            for profile in payload["profiles"]
        }
        kept = item.get("kept_char_values", {})
        print(
            "- %s | %s | line=%s | statuses=%s | kept=%s"
            % (
                item["id"],
                item.get("source_class"),
                item.get("line_no"),
                json.dumps(statuses, sort_keys=True),
                json.dumps(kept, sort_keys=True),
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()
    session = Path(args.session).resolve() if args.session else None
    profiles = _parse_profiles(args.profiles)
    if args.baseline not in profiles:
        parser.error(
            "baseline profile must be included in --profiles: %s"
            % args.baseline
        )
    max_lines = validate_positive_int(parser, "--max-lines", args.max_lines)
    max_candidates = validate_positive_int(parser, "--max-candidates", args.max_candidates)
    max_content_chars = validate_positive_int(
        parser,
        "--max-content-chars",
        args.max_content_chars,
    )
    try:
        payload = build_context_profile_comparison(
            root,
            session,
            profiles,
            args.baseline,
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
