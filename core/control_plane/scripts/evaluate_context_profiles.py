#!/usr/bin/env python3
"""Evaluate context-firewall profile behavior over multiple redacted sessions."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from compare_context_profiles import (
    build_context_profile_comparison,
    default_profiles,
    parse_profiles,
    validate_positive_int,
)
from context_firewall_lib import DEFAULT_ROOT


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate strict/balanced/exploratory context-firewall behavior "
            "across multiple session probes without emitting raw content or "
            "mutating runtime state."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument(
        "--session",
        action="append",
        default=[],
        help=(
            "Session JSONL file to include. May be repeated. If omitted, the "
            "newest files under <root>/sessions are selected."
        ),
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Number of newest sessions to evaluate when --session is omitted.",
    )
    parser.add_argument(
        "--profiles",
        default=",".join(default_profiles()),
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
        help="Maximum recent JSONL records to inspect per session.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=60,
        help="Maximum candidate ingress items per session.",
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


def _latest_sessions(root: Path, sample_size: int) -> List[Path]:
    candidates = [
        path
        for path in (root / "sessions").rglob("*.jsonl")
        if path.is_file()
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[: max(1, sample_size)]


def _session_id(path: str) -> str:
    return Path(path).name


def _counter_add(counter: Counter, values: Dict[str, int]) -> None:
    for key, value in values.items():
        counter[key] += value


def _aggregate_profile_summaries(
    profiles: List[str],
    comparisons: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    aggregate: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:
        aggregate[profile] = {
            "profile": profile,
            "sessions_seen": 0,
            "admitted_items": 0,
            "rejected_items": 0,
            "review_items": 0,
            "flagged_items": 0,
            "memory_allow_items": 0,
            "total_chars": 0,
            "admitted_by_source_class": Counter(),
            "review_by_source_class": Counter(),
            "rejected_by_source_class": Counter(),
            "rejected_by_reason": Counter(),
            "flagged_by_source_class": Counter(),
        }

    for comparison in comparisons:
        by_profile = {
            item["profile"]: item
            for item in comparison.get("profile_summaries", [])
        }
        for profile in profiles:
            item = by_profile.get(profile)
            if item is None:
                continue
            target = aggregate[profile]
            summary = item.get("summary", {})
            target["sessions_seen"] += 1
            for key in (
                "admitted_items",
                "rejected_items",
                "review_items",
                "flagged_items",
                "memory_allow_items",
                "total_chars",
            ):
                target[key] += int(summary.get(key, 0) or 0)
            _counter_add(target["admitted_by_source_class"], item.get("admitted_by_source_class", {}))
            _counter_add(target["review_by_source_class"], item.get("review_by_source_class", {}))
            _counter_add(target["rejected_by_source_class"], item.get("rejected_by_source_class", {}))
            _counter_add(target["rejected_by_reason"], item.get("rejected_by_reason", {}))
            _counter_add(target["flagged_by_source_class"], item.get("flagged_by_source_class", {}))

    serializable: Dict[str, Dict[str, Any]] = {}
    for profile, item in aggregate.items():
        serializable[profile] = {
            key: (
                dict(sorted(value.items()))
                if isinstance(value, Counter)
                else value
            )
            for key, value in item.items()
        }
    return serializable


def _aggregate_deltas(
    profiles: List[str],
    baseline: str,
    profile_totals: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    if baseline not in profile_totals:
        return {}
    baseline_total = profile_totals[baseline]
    deltas: Dict[str, Dict[str, int]] = {}
    for profile in profiles:
        current = profile_totals[profile]
        deltas[profile] = {
            "admitted_items": current["admitted_items"] - baseline_total["admitted_items"],
            "rejected_items": current["rejected_items"] - baseline_total["rejected_items"],
            "review_items": current["review_items"] - baseline_total["review_items"],
            "flagged_items": current["flagged_items"] - baseline_total["flagged_items"],
            "total_chars": current["total_chars"] - baseline_total["total_chars"],
        }
    return deltas


def _profile_extremes(
    profile_totals: Dict[str, Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    if not profile_totals:
        return {
            "widest_profile_by_chars": None,
            "narrowest_profile_by_chars": None,
            "highest_rejection_profile": None,
            "lowest_rejection_profile": None,
        }
    return {
        "widest_profile_by_chars": max(
            profile_totals,
            key=lambda profile: profile_totals[profile]["total_chars"],
        ),
        "narrowest_profile_by_chars": min(
            profile_totals,
            key=lambda profile: profile_totals[profile]["total_chars"],
        ),
        "highest_rejection_profile": max(
            profile_totals,
            key=lambda profile: profile_totals[profile]["rejected_items"],
        ),
        "lowest_rejection_profile": min(
            profile_totals,
            key=lambda profile: profile_totals[profile]["rejected_items"],
        ),
    }


def _build_recommendation(
    profiles: List[str],
    baseline: str,
    profile_totals: Dict[str, Dict[str, Any]],
    profile_deltas: Dict[str, Dict[str, int]],
    total_changed_items: int,
) -> Dict[str, Any]:
    if baseline not in profile_totals:
        return {
            "recommended_default_profile": None,
            "confidence": "blocked",
            "reason": "baseline_profile_missing",
            "policy_adjustment": "do_not_adjust_policy",
        }

    baseline_total = profile_totals[baseline]
    total_candidates = (
        baseline_total["admitted_items"] + baseline_total["rejected_items"]
    )
    rejection_rate = (
        float(baseline_total["rejected_items"]) / float(total_candidates)
        if total_candidates
        else 0.0
    )
    strict_delta = profile_deltas.get("strict", {})
    exploratory_delta = profile_deltas.get("exploratory", {})

    reasons = []
    recommendation = baseline
    confidence = "medium"
    policy_adjustment = "keep_policy_report_only"

    if rejection_rate > 0.75:
        recommendation = "exploratory" if "exploratory" in profiles else baseline
        confidence = "low"
        reasons.append("baseline_rejection_rate_high")
        policy_adjustment = "inspect_false_positive_risk_before_tightening"
    elif exploratory_delta.get("total_chars", 0) > max(4000, baseline_total["total_chars"] // 2):
        recommendation = baseline
        confidence = "medium"
        reasons.append("exploratory_adds_large_context_budget")
    elif strict_delta.get("total_chars", 0) < -max(3000, baseline_total["total_chars"] // 3):
        recommendation = baseline
        confidence = "medium"
        reasons.append("strict_discards_substantial_context")
    else:
        reasons.append("baseline_balances_retention_and_rejection")

    if total_changed_items == 0:
        confidence = "low"
        reasons.append("profiles_behave_identically_on_sample")

    return {
        "recommended_default_profile": recommendation,
        "confidence": confidence,
        "reason": ",".join(reasons),
        "policy_adjustment": policy_adjustment,
        "requires_runtime_hook": False,
        "requires_raw_content_review": False,
        "next_safe_action": (
            "review aggregate metadata and add targeted synthetic fixtures "
            "before changing thresholds or adding runtime hooks"
        ),
    }


def _session_report(comparison: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": _session_id(comparison["source_session"]["path"]),
        "source_session": comparison["source_session"],
        "parse_summary": comparison["parse_summary"],
        "candidate_summary": comparison["candidate_summary"],
        "summary": comparison["summary"],
        "profile_deltas_vs_baseline": comparison["profile_deltas_vs_baseline"],
        "changed_items": comparison["changed_items"],
    }


def build_context_profile_evaluation(
    root: Path,
    sessions: List[Path],
    profiles: List[str],
    baseline: str,
    max_lines: int,
    max_candidates: int,
    max_content_chars: int,
) -> Dict[str, Any]:
    selected_sessions = sessions or _latest_sessions(root, 5)
    comparisons = [
        build_context_profile_comparison(
            root,
            session,
            profiles,
            baseline,
            max_lines,
            max_candidates,
            max_content_chars,
        )
        for session in selected_sessions
    ]
    layout_version = comparisons[0]["layout_version"] if comparisons else None
    profile_totals = _aggregate_profile_summaries(profiles, comparisons)
    profile_deltas = _aggregate_deltas(profiles, baseline, profile_totals)
    total_candidates = sum(
        comparison.get("candidate_summary", {}).get("total_candidates", 0)
        for comparison in comparisons
    )
    total_changed_items = sum(
        comparison.get("summary", {}).get("items_with_profile_differences", 0)
        for comparison in comparisons
    )
    total_bad_json_records = sum(
        comparison.get("parse_summary", {}).get("bad_json_records", 0)
        for comparison in comparisons
    )
    source_counts = Counter()
    origin_counts = Counter()
    for comparison in comparisons:
        _counter_add(
            source_counts,
            comparison.get("candidate_summary", {}).get("by_source_class", {}),
        )
        _counter_add(
            origin_counts,
            comparison.get("candidate_summary", {}).get("by_origin_type", {}),
        )

    recommendation = _build_recommendation(
        profiles,
        baseline,
        profile_totals,
        profile_deltas,
        total_changed_items,
    )
    extremes = _profile_extremes(profile_totals)

    return {
        "root": root.as_posix(),
        "layout_version": layout_version,
        "profiles": profiles,
        "baseline_profile": baseline,
        "privacy": {
            "report_only": True,
            "raw_content_emitted": False,
            "rendered_context_emitted": False,
            "mutated_files": False,
            "automatic_runtime_hook": False,
            "memory_store_mutation": False,
            "raw_content_review_required": False,
        },
        "sample": {
            "session_count": len(comparisons),
            "session_ids": [
                _session_id(comparison["source_session"]["path"])
                for comparison in comparisons
            ],
            "max_lines_per_session": max_lines,
            "max_candidates_per_session": max_candidates,
            "max_content_chars_per_candidate": max_content_chars,
        },
        "aggregate_summary": {
            "total_candidates": total_candidates,
            "total_changed_items": total_changed_items,
            "total_bad_json_records": total_bad_json_records,
            "by_source_class": dict(sorted(source_counts.items())),
            "by_origin_type": dict(sorted(origin_counts.items())),
            **extremes,
        },
        "profile_totals": profile_totals,
        "profile_deltas_vs_baseline": profile_deltas,
        "recommendation": recommendation,
        "session_reports": [_session_report(comparison) for comparison in comparisons],
    }


def build_context_profile_evaluation_from_paths(
    root: Path,
    session_paths: List[Path],
    sample_size: int,
    profiles: List[str],
    baseline: str,
    max_lines: int,
    max_candidates: int,
    max_content_chars: int,
) -> Dict[str, Any]:
    sessions = [path.resolve() for path in session_paths]
    if not sessions:
        sessions = _latest_sessions(root, sample_size)
    for session in sessions:
        if not session.is_file():
            raise FileNotFoundError(
                "session JSONL file does not exist: %s" % session
            )
    return build_context_profile_evaluation(
        root,
        sessions,
        profiles,
        baseline,
        max_lines,
        max_candidates,
        max_content_chars,
    )


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("profiles: %s" % ",".join(payload["profiles"]))
    print("baseline_profile: %s" % payload["baseline_profile"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("sample: %s" % json.dumps(payload["sample"], ensure_ascii=False, sort_keys=True))
    print("aggregate_summary: %s" % json.dumps(payload["aggregate_summary"], ensure_ascii=False, sort_keys=True))
    print("recommendation: %s" % json.dumps(payload["recommendation"], ensure_ascii=False, sort_keys=True))
    print("")
    print("profile_totals:")
    for profile in payload["profiles"]:
        item = payload["profile_totals"][profile]
        print(
            "- %s | admitted=%s | review=%s | rejected=%s | flagged=%s | chars=%s"
            % (
                profile,
                item["admitted_items"],
                item["review_items"],
                item["rejected_items"],
                item["flagged_items"],
                item["total_chars"],
            )
        )
    print("")
    print("session_reports:")
    for item in payload["session_reports"]:
        print(
            "- %s | candidates=%s | changed=%s | widest=%s | narrowest=%s"
            % (
                item["session_id"],
                item["candidate_summary"]["total_candidates"],
                item["summary"]["items_with_profile_differences"],
                item["summary"]["widest_profile_by_chars"],
                item["summary"]["narrowest_profile_by_chars"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()
    session_paths = [Path(value) for value in args.session]
    profiles = parse_profiles(args.profiles)
    if args.baseline not in profiles:
        parser.error(
            "baseline profile must be included in --profiles: %s"
            % args.baseline
        )
    sample_size = validate_positive_int(parser, "--sample-size", args.sample_size)
    max_lines = validate_positive_int(parser, "--max-lines", args.max_lines)
    max_candidates = validate_positive_int(parser, "--max-candidates", args.max_candidates)
    max_content_chars = validate_positive_int(
        parser,
        "--max-content-chars",
        args.max_content_chars,
    )
    try:
        payload = build_context_profile_evaluation_from_paths(
            root,
            session_paths,
            sample_size,
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
