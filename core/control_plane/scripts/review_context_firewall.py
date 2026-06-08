#!/usr/bin/env python3
"""Render an operator-focused review for the governed context firewall."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from context_firewall_lib import (
    DEFAULT_ROOT,
    load_context_firewall_contracts,
    load_json,
    resolve_relevance_action,
    validate_context_firewall_contracts,
)


SAMPLE_RELEVANCE_SCORES = [
    ("very_low", 0.10),
    ("borderline", 0.20),
    ("relevant", 0.80),
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review context-firewall source posture, relevance tiers, and budget profiles.",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    return parser


def _profile_bias(profile_id: str) -> str:
    if profile_id == "strict":
        return "execution_first"
    if profile_id == "exploratory":
        return "research_first"
    return "general_work"


def _source_operator_bias(
    source_class: str,
    treatment: str,
    memory_action: str,
    is_untrusted: bool,
    sample_actions: Dict[str, str],
) -> str:
    if is_untrusted:
        return "quote_and_downgrade"
    if source_class in {"repo_state", "repo_instructions", "user_message"}:
        return "preserve_authoritative_local_context"
    if sample_actions.get("borderline") == "demote":
        return "demote_before_drop"
    if memory_action == "review_only":
        return "review_before_memory_write"
    if treatment == "reference_only":
        return "reference_only"
    return "admit_with_contract_limits"


def build_context_firewall_review(root: Path) -> Dict[str, Any]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    checks = validate_context_firewall_contracts(root, manifest)
    contract_ok = all(check.ok for check in checks)
    contracts = load_context_firewall_contracts(root)
    ingress = contracts["context_ingress_policy"]
    memory = contracts["memory_admission_policy"]
    compaction = contracts["context_compaction_policy"]
    untrusted = contracts["untrusted_content_policy"]

    relevance_policy = ingress.get("relevance_policy", {})
    memory_by_source = {
        item["source_class"]: item
        for item in memory.get("source_class_rules", [])
    }
    untrusted_by_source = {
        item["source_class"]: item
        for item in untrusted.get("source_class_rules", [])
    }

    source_posture: List[Dict[str, Any]] = []
    for item in ingress.get("source_classes", []):
        source_class = item["source_class"]
        memory_rule = memory_by_source[source_class]
        untrusted_rule = untrusted_by_source.get(source_class)
        sample_relevance_actions = {}
        sample_relevance_tiers = {}
        for label, score in SAMPLE_RELEVANCE_SCORES:
            action, tier = resolve_relevance_action(
                source_class,
                score,
                relevance_policy if isinstance(relevance_policy, dict) else {},
            )
            sample_relevance_actions[label] = action
            sample_relevance_tiers[label] = tier

        is_untrusted = untrusted_rule is not None
        source_posture.append(
            {
                "source_class": source_class,
                "authority_rank": item["authority_rank"],
                "treatment": item["treatment"],
                "freshness_policy": item["freshness_policy"],
                "max_age_days": item["max_age_days"],
                "allows_memory_writeback": item["allows_memory_writeback"],
                "memory_action": memory_rule["memory_action"],
                "allowed_memory_kinds": memory_rule.get("allowed_memory_kinds", []),
                "requires_fresh_anchor": memory_rule["requires_fresh_anchor"],
                "strip_instruction_authority": bool(
                    untrusted_rule
                    and untrusted_rule.get("strip_instruction_authority")
                ),
                "quoted_only": bool(
                    untrusted_rule
                    and untrusted_rule.get("quoted_only")
                ),
                "sample_relevance_actions": sample_relevance_actions,
                "sample_relevance_tiers": sample_relevance_tiers,
                "operator_bias": _source_operator_bias(
                    source_class,
                    item["treatment"],
                    memory_rule["memory_action"],
                    is_untrusted,
                    sample_relevance_actions,
                ),
            }
        )

    profile_posture: List[Dict[str, Any]] = []
    for profile in compaction.get("profiles", []):
        char_limits = {
            item["source_class"]: item["max_chars"]
            for item in profile.get("source_class_char_limits", [])
        }
        external_budget = sum(
            char_limits.get(source_class, 0)
            for source_class in ("tool_output", "retrieved_web", "untrusted_external")
        )
        authoritative_budget = sum(
            char_limits.get(source_class, 0)
            for source_class in (
                "repo_state",
                "repo_instructions",
                "user_message",
                "operator_contract",
                "global_control",
            )
        )
        profile_posture.append(
            {
                "profile": profile["id"],
                "operator_bias": _profile_bias(profile["id"]),
                "max_total_chars": profile["max_total_chars"],
                "max_items": profile["max_items"],
                "max_chars_per_item": profile["max_chars_per_item"],
                "reserved_source_classes": profile.get("reserved_source_classes", []),
                "drop_order": profile.get("drop_order", []),
                "source_class_char_limits": char_limits,
                "external_source_char_budget": external_budget,
                "authority_source_char_budget": authoritative_budget,
            }
        )

    by_memory_action = Counter(item["memory_action"] for item in source_posture)
    by_operator_bias = Counter(item["operator_bias"] for item in source_posture)
    untrusted_sources = [
        item["source_class"]
        for item in source_posture
        if item["strip_instruction_authority"] or item["quoted_only"]
    ]

    return {
        "root": root.as_posix(),
        "layout_version": manifest.get("layout_version"),
        "contract_ok": contract_ok,
        "summary": {
            "total_source_classes": len(source_posture),
            "profiles": [item["profile"] for item in profile_posture],
            "relevance_tiers": [
                item["id"]
                for item in relevance_policy.get("tiers", [])
                if isinstance(item, dict) and item.get("id")
            ],
            "untrusted_source_classes": untrusted_sources,
            "by_memory_action": dict(sorted(by_memory_action.items())),
            "by_operator_bias": dict(sorted(by_operator_bias.items())),
        },
        "integration_status": {
            "contract_layer": contract_ok,
            "audit_layer": contract_ok,
            "redacted_suggestion_cli": contract_ok,
            "curated_context_cli": contract_ok,
            "automatic_runtime_hook": False,
            "memory_store_mutation": False,
        },
        "operator_sequence": [
            "Use source_posture to verify authority, trust, freshness, and memory behavior before changing runtime ingress.",
            "Use profile_posture to choose strict, balanced, or exploratory before running curated-context experiments.",
            "Use suggest_curated_context.py as the soft integration path when raw content should not be emitted.",
            "Treat automatic_runtime_hook=false as a deliberate report-only state until a separate integration phase is specified.",
        ],
        "source_posture": source_posture,
        "profile_posture": profile_posture,
        "marker_posture": untrusted.get("marker_categories", []),
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("contract_ok: %s" % payload["contract_ok"])
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("integration_status: %s" % json.dumps(payload["integration_status"], ensure_ascii=False, sort_keys=True))
    print("")
    print("source_posture:")
    for item in payload["source_posture"]:
        print(
            "- %s | rank=%s | treatment=%s | memory=%s | very_low=%s | borderline=%s | bias=%s"
            % (
                item["source_class"],
                item["authority_rank"],
                item["treatment"],
                item["memory_action"],
                item["sample_relevance_actions"]["very_low"],
                item["sample_relevance_actions"]["borderline"],
                item["operator_bias"],
            )
        )
    print("")
    print("profile_posture:")
    for item in payload["profile_posture"]:
        print(
            "- %s | max_total=%s | max_items=%s | external_budget=%s | authority_budget=%s | bias=%s"
            % (
                item["profile"],
                item["max_total_chars"],
                item["max_items"],
                item["external_source_char_budget"],
                item["authority_source_char_budget"],
                item["operator_bias"],
            )
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    payload = build_context_firewall_review(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload["contract_ok"] else 1
    _print_text(payload)
    return 0 if payload["contract_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
