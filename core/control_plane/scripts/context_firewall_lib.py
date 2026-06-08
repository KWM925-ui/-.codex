#!/usr/bin/env python3
"""Shared helpers for the auditable context-firewall layer."""

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Pattern, Tuple


DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()

INGRESS_POLICY_PATH = "core/control_plane/context_ingress_policy.json"
MEMORY_POLICY_PATH = "core/control_plane/memory_admission_policy.json"
COMPACTION_POLICY_PATH = "core/control_plane/context_compaction_policy.json"
UNTRUSTED_POLICY_PATH = "core/control_plane/untrusted_content_policy.json"


@dataclass
class FirewallCheck:
    name: str
    ok: bool
    details: str


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_layout_version(
    path: Path,
    data: Dict[str, Any],
    manifest: Dict[str, Any],
    label: str,
) -> FirewallCheck:
    expected = manifest.get("layout_version")
    actual = data.get("generated_for_layout_version")
    return FirewallCheck(
        "%s:layout_version" % label,
        actual == expected,
        "expected=%s actual=%s path=%s" % (expected, actual, path),
    )


def _load_json_document(
    root: Path,
    relpath: str,
    label: str,
) -> Tuple[List[FirewallCheck], Optional[Dict[str, Any]]]:
    path = root / relpath
    checks = []
    if not path.exists():
        return [
            FirewallCheck(
                "%s:file" % label,
                False,
                "missing file: %s" % path,
            )
        ], None

    checks.append(
        FirewallCheck(
            "%s:file" % label,
            True,
            "file present: %s" % path,
        )
    )
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        checks.append(
            FirewallCheck(
                "%s:json" % label,
                False,
                "invalid json at %s: %s" % (path, exc),
            )
        )
        return checks, None

    checks.append(
        FirewallCheck(
            "%s:json" % label,
            True,
            "valid json: %s" % path,
        )
    )
    return checks, data


def _compare_expected_ids(
    actual_ids: Iterable[str],
    expected_ids: Iterable[str],
    label: str,
) -> FirewallCheck:
    actual = set(actual_ids)
    expected = set(expected_ids)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    return FirewallCheck(
        label,
        not (missing or extra),
        "missing=%s extra=%s" % (missing, extra),
    )


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _safe_str(value: Any) -> Optional[str]:
    if isinstance(value, str) and value:
        return value
    return None


def load_context_firewall_contracts(root: Path) -> Dict[str, Dict[str, Any]]:
    return {
        "context_ingress_policy": load_json(root / INGRESS_POLICY_PATH),
        "memory_admission_policy": load_json(root / MEMORY_POLICY_PATH),
        "context_compaction_policy": load_json(root / COMPACTION_POLICY_PATH),
        "untrusted_content_policy": load_json(root / UNTRUSTED_POLICY_PATH),
    }


def summarize_context_firewall(
    root: Path,
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    contracts = load_context_firewall_contracts(root)
    ingress = contracts["context_ingress_policy"]
    memory = contracts["memory_admission_policy"]
    compaction = contracts["context_compaction_policy"]
    untrusted = contracts["untrusted_content_policy"]
    return {
        "layout_version": manifest.get("layout_version"),
        "stages": [entry["id"] for entry in ingress.get("stages", [])],
        "source_classes": [
            entry["source_class"] for entry in ingress.get("source_classes", [])
        ],
        "profiles": [entry["id"] for entry in compaction.get("profiles", [])],
        "relevance_tiers": [
            entry["id"]
            for entry in ingress.get("relevance_policy", {}).get("tiers", [])
            if isinstance(entry, dict) and entry.get("id")
        ],
        "memory_kinds": [entry["id"] for entry in memory.get("memory_kinds", [])],
        "untrusted_source_classes": [
            entry["source_class"] for entry in untrusted.get("source_class_rules", [])
        ],
        "marker_categories": [
            entry["id"] for entry in untrusted.get("marker_categories", [])
        ],
    }


def _firewall_spec(manifest: Dict[str, Any]) -> Dict[str, Any]:
    spec = manifest.get("context_firewall_policy", {})
    return {
        "allowed_treatments": set(spec.get("allowed_treatments", [])),
        "allowed_freshness_policies": set(
            spec.get("allowed_freshness_policies", []),
        ),
        "allowed_memory_actions": set(spec.get("allowed_memory_actions", [])),
        "allowed_handling_actions": set(spec.get("allowed_handling_actions", [])),
        "required_stages": list(spec.get("required_stages", [])),
        "required_source_classes": list(spec.get("required_source_classes", [])),
        "required_memory_kinds": list(spec.get("required_memory_kinds", [])),
        "required_profiles": list(spec.get("required_profiles", [])),
        "required_marker_categories": list(
            spec.get("required_marker_categories", []),
        ),
        "required_untrusted_source_classes": list(
            spec.get("required_untrusted_source_classes", []),
        ),
        "forbidden_memory_kinds": set(spec.get("forbidden_memory_kinds", [])),
        "max_total_chars_upper_bound": spec.get("max_total_chars_upper_bound"),
    }


def _require_object_list(
    data: Dict[str, Any],
    key: str,
    label: str,
    checks: List[FirewallCheck],
) -> Optional[List[Dict[str, Any]]]:
    value = data.get(key)
    if not isinstance(value, list):
        checks.append(FirewallCheck(label, False, "%s must be a list" % key))
        return None
    return [entry for entry in value if isinstance(entry, dict)]


def _audit_ingress_relevance_policy(
    relevance_policy: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    allowed_relevance_actions = {"admit", "demote", "drop"}
    checks.extend(
        _audit_relevance_policy_actions(
            relevance_policy,
            allowed_relevance_actions,
        )
    )
    checks.extend(
        _audit_relevance_tiers(
            relevance_policy.get("tiers"),
            allowed_relevance_actions,
        )
    )
    checks.extend(
        _audit_relevance_source_overrides(
            relevance_policy.get("source_overrides", []),
            allowed_relevance_actions,
            spec,
        )
    )
    return checks


def _audit_relevance_policy_actions(
    relevance_policy: Dict[str, Any],
    allowed_relevance_actions: set,
) -> List[FirewallCheck]:
    return [
        FirewallCheck(
            "context_ingress_policy:relevance_policy:default_source_action",
            relevance_policy.get("default_source_action") in allowed_relevance_actions,
            "default_source_action=%s"
            % relevance_policy.get("default_source_action"),
        ),
        FirewallCheck(
            "context_ingress_policy:relevance_policy:missing_score_action",
            relevance_policy.get("missing_score_action") in allowed_relevance_actions,
            "missing_score_action=%s"
            % relevance_policy.get("missing_score_action"),
        ),
    ]


def _audit_relevance_tiers(
    tiers: Any,
    allowed_relevance_actions: set,
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = [
        FirewallCheck(
            "context_ingress_policy:relevance_policy:tiers",
            isinstance(tiers, list) and bool(tiers),
            "tiers=%s" % tiers,
        )
    ]
    if isinstance(tiers, list):
        previous_max_score = -1.0
        for index, entry in enumerate(tiers):
            if not isinstance(entry, dict):
                checks.append(
                    FirewallCheck(
                        "context_ingress_policy:relevance_policy:tier:%d" % index,
                        False,
                        "tier must be an object",
                    )
                )
                continue
            tier_id = entry.get("id") or "tier-%d" % index
            max_score = _safe_float(entry.get("max_score"))
            checks.append(
                FirewallCheck(
                    "context_ingress_policy:relevance_policy:max_score:%s" % tier_id,
                    max_score is not None and 0.0 <= max_score <= 1.0,
                    "max_score=%s" % entry.get("max_score"),
                )
            )
            checks.append(
                FirewallCheck(
                    "context_ingress_policy:relevance_policy:action:%s" % tier_id,
                    entry.get("action") in allowed_relevance_actions,
                    "action=%s" % entry.get("action"),
                )
            )
            checks.append(
                FirewallCheck(
                    "context_ingress_policy:relevance_policy:ordering:%s" % tier_id,
                    max_score is not None and max_score >= previous_max_score,
                    "previous_max_score=%s current_max_score=%s"
                    % (previous_max_score, entry.get("max_score")),
                )
            )
            if max_score is not None:
                previous_max_score = max_score
        checks.append(
            FirewallCheck(
                "context_ingress_policy:relevance_policy:covers_full_range",
                bool(tiers)
                and isinstance(tiers[-1], dict)
                and _safe_float(tiers[-1].get("max_score")) == 1.0,
                "last_max_score=%s"
                % (
                    tiers[-1].get("max_score")
                    if tiers and isinstance(tiers[-1], dict)
                    else None
                ),
            )
        )
    return checks


def _audit_relevance_source_overrides(
    overrides: Any,
    allowed_relevance_actions: set,
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = [
        FirewallCheck(
            "context_ingress_policy:relevance_policy:source_overrides",
            isinstance(overrides, list),
            "source_overrides=%s" % overrides,
        )
    ]
    if isinstance(overrides, list):
        for entry in overrides:
            if not isinstance(entry, dict):
                continue
            source_class = entry.get("source_class")
            checks.append(
                FirewallCheck(
                    "context_ingress_policy:relevance_policy:override_source_class:%s"
                    % source_class,
                    source_class in spec["required_source_classes"],
                    "source_class=%s" % source_class,
                )
            )
            checks.append(
                FirewallCheck(
                    "context_ingress_policy:relevance_policy:override_action:%s"
                    % source_class,
                    entry.get("below_threshold_action") in allowed_relevance_actions,
                    "below_threshold_action=%s"
                    % entry.get("below_threshold_action"),
                )
            )
    return checks


def _audit_ingress_source_class(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    source_class = entry.get("source_class")
    authority_rank = _safe_int(entry.get("authority_rank"))
    max_age_days = _safe_int(entry.get("max_age_days"))
    return [
        FirewallCheck(
            "context_ingress_policy:treatment:%s" % source_class,
            entry.get("treatment") in spec["allowed_treatments"],
            "treatment=%s allowed=%s"
            % (entry.get("treatment"), sorted(spec["allowed_treatments"])),
        ),
        FirewallCheck(
            "context_ingress_policy:freshness_policy:%s" % source_class,
            entry.get("freshness_policy") in spec["allowed_freshness_policies"],
            "freshness_policy=%s allowed=%s"
            % (
                entry.get("freshness_policy"),
                sorted(spec["allowed_freshness_policies"]),
            ),
        ),
        FirewallCheck(
            "context_ingress_policy:authority_rank:%s" % source_class,
            authority_rank is not None and authority_rank >= 1,
            "authority_rank=%s" % entry.get("authority_rank"),
        ),
        FirewallCheck(
            "context_ingress_policy:max_age_days:%s" % source_class,
            max_age_days is not None and max_age_days >= 0,
            "max_age_days=%s" % entry.get("max_age_days"),
        ),
        FirewallCheck(
            "context_ingress_policy:allows_memory_writeback:%s" % source_class,
            isinstance(entry.get("allows_memory_writeback"), bool),
            "allows_memory_writeback=%s" % entry.get("allows_memory_writeback"),
        ),
    ]


def _audit_ingress_policy(
    root: Path,
    manifest: Dict[str, Any],
    spec: Dict[str, Any],
) -> Tuple[List[FirewallCheck], bool]:
    checks: List[FirewallCheck] = []
    ingress_checks, ingress = _load_json_document(
        root,
        INGRESS_POLICY_PATH,
        "context_ingress_policy",
    )
    checks.extend(ingress_checks)
    if ingress is None:
        return checks, False
    checks.append(
        _check_layout_version(
            root / INGRESS_POLICY_PATH,
            ingress,
            manifest,
            "context_ingress_policy",
        )
    )

    stages = _require_object_list(
        ingress,
        "stages",
        "context_ingress_policy:stages",
        checks,
    )
    if stages is None:
        return checks, False
    stage_ids = [entry.get("id") for entry in stages]
    checks.append(
        _compare_expected_ids(
            stage_ids,
            spec["required_stages"],
            "context_ingress_policy:stages",
        )
    )

    source_classes = _require_object_list(
        ingress,
        "source_classes",
        "context_ingress_policy:source_classes",
        checks,
    )
    if source_classes is None:
        return checks, False
    source_class_ids = [entry.get("source_class") for entry in source_classes]
    checks.append(
        _compare_expected_ids(
            source_class_ids,
            spec["required_source_classes"],
            "context_ingress_policy:source_classes",
        )
    )

    relevance_policy = ingress.get("relevance_policy")
    checks.append(
        FirewallCheck(
            "context_ingress_policy:relevance_policy",
            isinstance(relevance_policy, dict),
            "relevance_policy_present=%s" % isinstance(relevance_policy, dict),
        )
    )
    if not isinstance(relevance_policy, dict):
        return checks, False
    checks.extend(_audit_ingress_relevance_policy(relevance_policy, spec))
    for entry in source_classes:
        checks.extend(_audit_ingress_source_class(entry, spec))
    return checks, True


def _audit_memory_policy(
    root: Path,
    manifest: Dict[str, Any],
    spec: Dict[str, Any],
) -> Tuple[List[FirewallCheck], bool]:
    checks: List[FirewallCheck] = []
    memory_checks, memory = _load_json_document(
        root,
        MEMORY_POLICY_PATH,
        "memory_admission_policy",
    )
    checks.extend(memory_checks)
    if memory is None:
        return checks, False
    checks.append(
        _check_layout_version(
            root / MEMORY_POLICY_PATH,
            memory,
            manifest,
            "memory_admission_policy",
        )
    )

    checks.append(
        FirewallCheck(
            "memory_admission_policy:default_action",
            memory.get("default_action") in spec["allowed_memory_actions"],
            "default_action=%s allowed=%s"
            % (memory.get("default_action"), sorted(spec["allowed_memory_actions"])),
        )
    )

    memory_kinds = _require_object_list(
        memory,
        "memory_kinds",
        "memory_admission_policy:memory_kinds",
        checks,
    )
    if memory_kinds is None:
        return checks, False
    memory_kind_ids = [entry.get("id") for entry in memory_kinds]
    checks.append(
        _compare_expected_ids(
            memory_kind_ids,
            spec["required_memory_kinds"],
            "memory_admission_policy:memory_kinds",
        )
    )

    source_rules = _require_object_list(
        memory,
        "source_class_rules",
        "memory_admission_policy:source_class_rules",
        checks,
    )
    if source_rules is None:
        return checks, False
    memory_source_class_ids = [entry.get("source_class") for entry in source_rules]
    checks.append(
        _compare_expected_ids(
            memory_source_class_ids,
            spec["required_source_classes"],
            "memory_admission_policy:source_class_rules",
        )
    )

    known_memory_kinds = set(memory_kind_ids)
    for entry in source_rules:
        checks.extend(
            _audit_memory_source_rule(entry, spec, known_memory_kinds)
        )
    return checks, True


def _audit_memory_source_rule(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
    known_memory_kinds: set,
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    source_class = entry.get("source_class")
    memory_action = entry.get("memory_action")
    checks.append(
        FirewallCheck(
            "memory_admission_policy:memory_action:%s" % source_class,
            memory_action in spec["allowed_memory_actions"],
            "memory_action=%s allowed=%s"
            % (memory_action, sorted(spec["allowed_memory_actions"])),
        )
    )
    allowed_kinds = entry.get("allowed_memory_kinds")
    checks.append(
        FirewallCheck(
            "memory_admission_policy:allowed_memory_kinds:%s" % source_class,
            isinstance(allowed_kinds, list),
            "allowed_memory_kinds=%s" % allowed_kinds,
        )
    )
    if isinstance(allowed_kinds, list):
        unknown_kinds = sorted(set(allowed_kinds) - known_memory_kinds)
        forbidden_kinds = sorted(
            set(allowed_kinds) & spec["forbidden_memory_kinds"],
        )
        checks.append(
            FirewallCheck(
                "memory_admission_policy:known_memory_kinds:%s" % source_class,
                not unknown_kinds,
                "unknown_kinds=%s" % unknown_kinds,
            )
        )
        checks.append(
            FirewallCheck(
                "memory_admission_policy:forbidden_memory_kinds:%s" % source_class,
                not forbidden_kinds,
                "forbidden_kinds=%s" % forbidden_kinds,
            )
        )
    checks.append(
        FirewallCheck(
            "memory_admission_policy:requires_fresh_anchor:%s" % source_class,
            isinstance(entry.get("requires_fresh_anchor"), bool),
            "requires_fresh_anchor=%s" % entry.get("requires_fresh_anchor"),
        )
    )
    return checks


def _audit_compaction_policy(
    root: Path,
    manifest: Dict[str, Any],
    spec: Dict[str, Any],
) -> Tuple[List[FirewallCheck], bool]:
    checks: List[FirewallCheck] = []
    compaction_checks, compaction = _load_json_document(
        root,
        COMPACTION_POLICY_PATH,
        "context_compaction_policy",
    )
    checks.extend(compaction_checks)
    if compaction is None:
        return checks, False
    checks.append(
        _check_layout_version(
            root / COMPACTION_POLICY_PATH,
            compaction,
            manifest,
            "context_compaction_policy",
        )
    )

    profiles = _require_object_list(
        compaction,
        "profiles",
        "context_compaction_policy:profiles",
        checks,
    )
    if profiles is None:
        return checks, False
    profile_ids = [entry.get("id") for entry in profiles]
    checks.append(
        _compare_expected_ids(
            profile_ids,
            spec["required_profiles"],
            "context_compaction_policy:profiles",
        )
    )

    for entry in profiles:
        checks.extend(_audit_compaction_profile(entry, spec))
    return checks, True


def _audit_compaction_profile(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    profile_id = entry.get("id")
    max_chars_per_item = _safe_int(entry.get("max_chars_per_item"))
    checks.extend(_audit_compaction_profile_budget(entry, spec))
    checks.extend(_audit_compaction_profile_sources(entry, spec))
    checks.extend(
        _audit_compaction_char_limits(
            entry,
            spec,
            profile_id,
            max_chars_per_item,
        )
    )
    return checks


def _audit_compaction_profile_budget(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    profile_id = entry.get("id")
    max_total_chars = _safe_int(entry.get("max_total_chars"))
    max_items = _safe_int(entry.get("max_items"))
    max_chars_per_item = _safe_int(entry.get("max_chars_per_item"))
    min_chars_per_item = _safe_int(entry.get("min_chars_per_item"))
    return [
        FirewallCheck(
            "context_compaction_policy:max_total_chars:%s" % profile_id,
            max_total_chars is not None
            and max_total_chars > 0
            and (
                spec["max_total_chars_upper_bound"] is None
                or max_total_chars <= spec["max_total_chars_upper_bound"]
            ),
            "max_total_chars=%s upper_bound=%s"
            % (entry.get("max_total_chars"), spec["max_total_chars_upper_bound"]),
        ),
        FirewallCheck(
            "context_compaction_policy:max_items:%s" % profile_id,
            max_items is not None and max_items > 0,
            "max_items=%s" % entry.get("max_items"),
        ),
        FirewallCheck(
            "context_compaction_policy:per_item_bounds:%s" % profile_id,
            max_chars_per_item is not None
            and min_chars_per_item is not None
            and max_chars_per_item >= min_chars_per_item > 0,
            "max_chars_per_item=%s min_chars_per_item=%s"
            % (entry.get("max_chars_per_item"), entry.get("min_chars_per_item")),
        ),
    ]


def _audit_compaction_profile_sources(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    profile_id = entry.get("id")
    reserved_source_classes = entry.get("reserved_source_classes")
    checks.append(
        FirewallCheck(
            "context_compaction_policy:reserved_source_classes:%s" % profile_id,
            isinstance(reserved_source_classes, list)
            and set(reserved_source_classes).issubset(
                set(spec["required_source_classes"]),
            ),
            "reserved_source_classes=%s" % reserved_source_classes,
        )
    )
    drop_order = entry.get("drop_order")
    checks.append(
        _compare_expected_ids(
            drop_order if isinstance(drop_order, list) else [],
            spec["required_source_classes"],
            "context_compaction_policy:drop_order:%s" % profile_id,
        )
    )
    return checks


def _audit_compaction_char_limits(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
    profile_id: Any,
    max_chars_per_item: Optional[int],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    char_limits = entry.get("source_class_char_limits")
    if not isinstance(char_limits, list):
        checks.append(
            FirewallCheck(
                "context_compaction_policy:source_class_char_limits:%s" % profile_id,
                False,
                "source_class_char_limits must be a list",
            )
        )
        return checks
    char_limit_items = [item for item in char_limits if isinstance(item, dict)]
    char_limit_ids = [item.get("source_class") for item in char_limit_items]
    checks.append(
        _compare_expected_ids(
            char_limit_ids,
            spec["required_source_classes"],
            "context_compaction_policy:source_class_char_limits:%s" % profile_id,
        )
    )
    for item in char_limit_items:
        source_class = item.get("source_class")
        max_chars = _safe_int(item.get("max_chars"))
        checks.append(
            FirewallCheck(
                "context_compaction_policy:max_chars:%s:%s"
                % (profile_id, source_class),
                max_chars is not None
                and max_chars > 0
                and max_chars_per_item is not None
                and max_chars <= max_chars_per_item,
                "max_chars=%s max_chars_per_item=%s"
                % (item.get("max_chars"), entry.get("max_chars_per_item")),
            )
        )
    return checks


def _audit_untrusted_source_rule(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    source_class = entry.get("source_class")
    return [
        FirewallCheck(
            "untrusted_content_policy:known_source_class:%s" % source_class,
            source_class in spec["required_source_classes"],
            "source_class=%s" % source_class,
        ),
        FirewallCheck(
            "untrusted_content_policy:strip_instruction_authority:%s"
            % source_class,
            isinstance(entry.get("strip_instruction_authority"), bool),
            "strip_instruction_authority=%s"
            % entry.get("strip_instruction_authority"),
        ),
        FirewallCheck(
            "untrusted_content_policy:quoted_only:%s" % source_class,
            isinstance(entry.get("quoted_only"), bool),
            "quoted_only=%s" % entry.get("quoted_only"),
        ),
    ]


def _audit_marker_category(
    entry: Dict[str, Any],
    spec: Dict[str, Any],
) -> List[FirewallCheck]:
    checks: List[FirewallCheck] = []
    marker_id = entry.get("id")
    checks.append(
        FirewallCheck(
            "untrusted_content_policy:action:%s" % marker_id,
            entry.get("action") in spec["allowed_handling_actions"],
            "action=%s allowed=%s"
            % (entry.get("action"), sorted(spec["allowed_handling_actions"])),
        )
    )
    patterns = entry.get("patterns")
    checks.append(
        FirewallCheck(
            "untrusted_content_policy:patterns:%s" % marker_id,
            isinstance(patterns, list) and bool(patterns),
            "patterns=%s" % patterns,
        )
    )
    if isinstance(patterns, list):
        try:
            for pattern in patterns:
                re.compile(pattern)
        except re.error as exc:
            checks.append(
                FirewallCheck(
                    "untrusted_content_policy:regex:%s" % marker_id,
                    False,
                    "invalid regex: %s" % exc,
                )
            )
        else:
            checks.append(
                FirewallCheck(
                    "untrusted_content_policy:regex:%s" % marker_id,
                    True,
                    "regex patterns compile",
                )
            )
    return checks


def _audit_untrusted_policy(
    root: Path,
    manifest: Dict[str, Any],
    spec: Dict[str, Any],
) -> Tuple[List[FirewallCheck], bool]:
    checks: List[FirewallCheck] = []
    untrusted_checks, untrusted = _load_json_document(
        root,
        UNTRUSTED_POLICY_PATH,
        "untrusted_content_policy",
    )
    checks.extend(untrusted_checks)
    if untrusted is None:
        return checks, False
    checks.append(
        _check_layout_version(
            root / UNTRUSTED_POLICY_PATH,
            untrusted,
            manifest,
            "untrusted_content_policy",
        )
    )

    source_class_rules = _require_object_list(
        untrusted,
        "source_class_rules",
        "untrusted_content_policy:source_class_rules",
        checks,
    )
    if source_class_rules is None:
        return checks, False
    untrusted_source_ids = [entry.get("source_class") for entry in source_class_rules]
    checks.append(
        _compare_expected_ids(
            untrusted_source_ids,
            spec["required_untrusted_source_classes"],
            "untrusted_content_policy:source_class_rules",
        )
    )
    for entry in source_class_rules:
        checks.extend(_audit_untrusted_source_rule(entry, spec))

    marker_categories = _require_object_list(
        untrusted,
        "marker_categories",
        "untrusted_content_policy:marker_categories",
        checks,
    )
    if marker_categories is None:
        return checks, False
    marker_ids = [entry.get("id") for entry in marker_categories]
    checks.append(
        _compare_expected_ids(
            marker_ids,
            spec["required_marker_categories"],
            "untrusted_content_policy:marker_categories",
        )
    )
    checks.append(
        FirewallCheck(
            "untrusted_content_policy:default_action_for_flagged",
            untrusted.get("default_action_for_flagged")
            in spec["allowed_handling_actions"],
            "default_action_for_flagged=%s allowed=%s"
            % (
                untrusted.get("default_action_for_flagged"),
                sorted(spec["allowed_handling_actions"]),
            ),
        )
    )
    for entry in marker_categories:
        checks.extend(_audit_marker_category(entry, spec))

    return checks, True


def validate_context_firewall_contracts(
    root: Path,
    manifest: Dict[str, Any],
) -> List[FirewallCheck]:
    spec = _firewall_spec(manifest)
    checks: List[FirewallCheck] = []
    for audit_stage in (
        _audit_ingress_policy,
        _audit_memory_policy,
        _audit_compaction_policy,
        _audit_untrusted_policy,
    ):
        stage_checks, should_continue = audit_stage(root, manifest, spec)
        checks.extend(stage_checks)
        if not should_continue:
            return checks
    return checks


def _compile_marker_patterns(
    marker_categories: List[Dict[str, Any]],
) -> List[Tuple[str, str, List[Pattern[str]]]]:
    compiled = []
    for entry in marker_categories:
        compiled.append(
            (
                entry["id"],
                entry["action"],
                [re.compile(pattern) for pattern in entry.get("patterns", [])],
            )
        )
    return compiled


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _input_items_and_profile(
    input_payload: Any,
) -> Tuple[List[Any], Optional[str]]:
    if isinstance(input_payload, list):
        return input_payload, None
    if isinstance(input_payload, dict):
        items = input_payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("input payload must contain an items list")
        return items, input_payload.get("budget_profile")
    raise ValueError("input payload must be a JSON object with an items list or a list")


def _select_profile(compaction: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
    for candidate in compaction.get("profiles", []):
        if isinstance(candidate, dict) and candidate.get("id") == profile_id:
            return candidate
    raise ValueError("unknown compaction profile: %s" % profile_id)


def _indexed_context_contracts(
    ingress: Dict[str, Any],
    memory: Dict[str, Any],
    profile: Dict[str, Any],
    untrusted: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "source_rules": {
            entry["source_class"]: entry
            for entry in ingress.get("source_classes", [])
        },
        "memory_rules": {
            entry["source_class"]: entry
            for entry in memory.get("source_class_rules", [])
        },
        "memory_kind_ids": {
            entry["id"] for entry in memory.get("memory_kinds", [])
        },
        "char_limits": {
            entry["source_class"]: entry["max_chars"]
            for entry in profile.get("source_class_char_limits", [])
        },
        "drop_order": list(profile.get("drop_order", [])),
        "reserved_source_classes": set(profile.get("reserved_source_classes", [])),
        "marker_rules": _compile_marker_patterns(
            untrusted.get("marker_categories", []),
        ),
        "untrusted_source_rules": {
            entry["source_class"]: entry
            for entry in untrusted.get("source_class_rules", [])
        },
    }


def _matching_marker_flags(
    content: str,
    marker_rules: List[Tuple[str, str, List[Pattern[str]]]],
) -> Tuple[List[str], Optional[str]]:
    flags = []
    marker_action = None
    for marker_id, action, patterns in marker_rules:
        if any(pattern.search(content) for pattern in patterns):
            flags.append(marker_id)
            marker_action = marker_action or action
    return flags, marker_action


def _review_for_relevance(
    treatment: str,
    relevance_action: str,
) -> Tuple[str, Optional[str]]:
    if relevance_action != "demote":
        return treatment, None
    if treatment in {"authoritative_instruction", "evidence"}:
        treatment = "reference_only"
    return treatment, "demoted_for_relevance"


def _drop_excess_items(
    admitted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    max_items: int,
) -> None:
    while len(admitted) > max_items:
        dropped = admitted.pop()
        rejected.append(
            {
                "id": dropped["id"],
                "source_class": dropped["source_class"],
                "reason": "dropped_for_max_items",
            }
        )


def _drop_non_reserved_budget_overflow(
    admitted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    total_chars: int,
    max_total_chars: int,
    reserved_source_classes: set,
) -> int:
    for idx in range(len(admitted) - 1, -1, -1):
        if total_chars <= max_total_chars:
            break
        item = admitted[idx]
        if item["source_class"] in reserved_source_classes:
            continue
        total_chars -= len(item["content"])
        rejected.append(
            {
                "id": item["id"],
                "source_class": item["source_class"],
                "reason": "dropped_for_budget",
            }
        )
        admitted.pop(idx)
    return total_chars


def _truncate_budget_overflow(
    admitted: List[Dict[str, Any]],
    overflow: int,
    min_chars_per_item: int,
) -> None:
    for enforce_minimum in (True, False):
        for idx in range(len(admitted) - 1, -1, -1):
            if overflow <= 0:
                return
            item = admitted[idx]
            if enforce_minimum:
                available = max(len(item["content"]) - min_chars_per_item, 0)
            else:
                available = len(item["content"])
            if available <= 0:
                continue
            cut = min(available, overflow)
            item["content"] = item["content"][:-cut].rstrip()
            item["dropped_chars"] += cut
            item["kept_chars"] = len(item["content"])
            if "truncated_to_total_budget" not in item["reasons"]:
                item["reasons"].append("truncated_to_total_budget")
            overflow -= cut


def _enforce_context_budget(
    admitted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    profile: Dict[str, Any],
    reserved_source_classes: set,
) -> int:
    _drop_excess_items(admitted, rejected, profile["max_items"])
    total_chars = sum(len(item["content"]) for item in admitted)
    max_total_chars = profile["max_total_chars"]
    if total_chars > max_total_chars:
        total_chars = _drop_non_reserved_budget_overflow(
            admitted,
            rejected,
            total_chars,
            max_total_chars,
            reserved_source_classes,
        )
    if total_chars > max_total_chars:
        _truncate_budget_overflow(
            admitted,
            total_chars - max_total_chars,
            profile["min_chars_per_item"],
        )
        total_chars = sum(len(item["content"]) for item in admitted)
    return total_chars


def _remove_internal_sort_fields(items: List[Dict[str, Any]]) -> None:
    for item in items:
        item.pop("_drop_rank", None)
        item.pop("_index", None)


def resolve_relevance_action(
    source_class: str,
    relevance_score: Optional[float],
    relevance_policy: Dict[str, Any],
) -> Tuple[str, Optional[str]]:
    allowed_actions = {"admit", "demote", "drop"}
    if relevance_score is None:
        action = relevance_policy.get("missing_score_action", "admit")
        if action not in allowed_actions:
            action = "admit"
        return action, None

    action = relevance_policy.get("default_source_action", "admit")
    matched_tier_id = None
    for tier in relevance_policy.get("tiers", []):
        if not isinstance(tier, dict):
            continue
        max_score = _safe_float(tier.get("max_score"))
        if max_score is None:
            continue
        if relevance_score <= max_score:
            matched_tier_id = _safe_str(tier.get("id"))
            tier_action = tier.get("action")
            if tier_action in allowed_actions:
                action = tier_action
            break

    if action != "admit":
        for override in relevance_policy.get("source_overrides", []):
            if not isinstance(override, dict):
                continue
            if override.get("source_class") != source_class:
                continue
            override_action = override.get("below_threshold_action")
            if override_action in allowed_actions:
                action = override_action
            break
    return action, matched_tier_id


def _reject_context_item(
    item_id: str,
    source_class: Any,
    reason: str,
    **extra: Any,
) -> Dict[str, Any]:
    rejected = {"id": item_id, "reason": reason}
    if source_class is not None:
        rejected["source_class"] = source_class
    rejected.update(extra)
    return rejected


def _evaluate_freshness(
    item_id: str,
    source_class: str,
    raw_item: Dict[str, Any],
    source_rule: Dict[str, Any],
    reasons: List[str],
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    freshness_days = _safe_int(raw_item.get("freshness_days"))
    if freshness_days is None and raw_item.get("freshness_days") is not None:
        return None, _reject_context_item(
            item_id,
            source_class,
            "invalid_freshness_days",
        )
    if freshness_days is None and source_rule.get("freshness_policy") in {
        "session_local",
        "fresh_required",
        "freshness_scoped",
    }:
        reasons.append("freshness_unknown")
    if freshness_days is not None and freshness_days > source_rule["max_age_days"]:
        return None, _reject_context_item(
            item_id,
            source_class,
            "stale",
            freshness_days=freshness_days,
            max_age_days=source_rule["max_age_days"],
        )
    return freshness_days, None


def _resolve_treatment_and_render_mode(
    source_class: str,
    content: str,
    source_rule: Dict[str, Any],
    indexes: Dict[str, Any],
    reasons: List[str],
) -> Tuple[str, str, List[str]]:
    flags, marker_action = _matching_marker_flags(content, indexes["marker_rules"])
    treatment = source_rule["treatment"]
    render_mode = "plain"
    untrusted_source_rule = indexes["untrusted_source_rules"].get(source_class)
    if untrusted_source_rule is not None:
        if untrusted_source_rule.get("strip_instruction_authority"):
            treatment = "untrusted_data"
            reasons.append("instruction_authority_stripped")
        if untrusted_source_rule.get("quoted_only"):
            render_mode = "quoted_only"
    if flags and marker_action == "downgrade_to_data":
        treatment = "untrusted_data"
        reasons.append("flagged_and_downgraded")
    return treatment, render_mode, flags


def _resolve_memory_admission(
    item_id: str,
    source_class: str,
    raw_item: Dict[str, Any],
    indexes: Dict[str, Any],
    reasons: List[str],
) -> Tuple[Optional[str], Any, Optional[Dict[str, Any]]]:
    memory_kind = raw_item.get("memory_kind")
    if memory_kind is not None and memory_kind not in indexes["memory_kind_ids"]:
        return (
            None,
            memory_kind,
            _reject_context_item(
                item_id,
                source_class,
                "unknown_memory_kind",
                memory_kind=memory_kind,
            ),
        )
    memory_rule = indexes["memory_rules"][source_class]
    memory_admission = memory_rule["memory_action"]
    if memory_kind is not None and memory_kind not in memory_rule.get(
        "allowed_memory_kinds", []
    ):
        memory_admission = "deny"
        reasons.append("memory_kind_not_allowed")
    return memory_admission, memory_kind, None


def _build_admitted_context_item(
    raw_item: Dict[str, Any],
    index: int,
    item_id: str,
    source_class: str,
    source_rule: Dict[str, Any],
    indexes: Dict[str, Any],
    values: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "title": raw_item.get("title", ""),
        "path": raw_item.get("path", ""),
        "source_class": source_class,
        "treatment": values["treatment"],
        "render_mode": values["render_mode"],
        "flags": values["flags"],
        "reasons": values["reasons"],
        "memory_admission": values["memory_admission"],
        "memory_kind": values["memory_kind"],
        "freshness_days": values["freshness_days"],
        "relevance_score": values["relevance_score"],
        "relevance_tier": values["relevance_tier"],
        "relevance_action": values["relevance_action"],
        "authority_rank": source_rule["authority_rank"],
        "content": values["content"],
        "kept_chars": len(values["content"]),
        "dropped_chars": values["dropped_chars"],
        "_drop_rank": indexes["drop_order"].index(source_class),
        "_index": index,
    }


def _process_context_item(
    raw_item: Any,
    index: int,
    indexes: Dict[str, Any],
    relevance_policy: Dict[str, Any],
    seen_keys: Dict[Tuple[str, str], str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    item_id = "item-%d" % (index + 1)
    if isinstance(raw_item, dict) and raw_item.get("id"):
        item_id = str(raw_item["id"])
    if not isinstance(raw_item, dict):
        return (
            None,
            _reject_context_item(
                item_id,
                None,
                "invalid_item_type",
                details="each item must be a JSON object",
            ),
            None,
        )

    source_rules = indexes["source_rules"]
    source_class = raw_item.get("source_class")
    content = raw_item.get("content")
    if source_class not in source_rules:
        return (
            None,
            _reject_context_item(item_id, source_class, "unknown_source_class"),
            None,
        )
    if not isinstance(content, str) or not content.strip():
        return (
            None,
            _reject_context_item(item_id, source_class, "missing_content"),
            None,
        )

    source_rule = source_rules[source_class]
    reasons: List[str] = []
    relevance_score = _safe_float(raw_item.get("relevance_score"))
    relevance_action, relevance_tier = resolve_relevance_action(
        source_class,
        relevance_score,
        relevance_policy if isinstance(relevance_policy, dict) else {},
    )
    if relevance_action == "drop":
        return (
            None,
            _reject_context_item(
                item_id,
                source_class,
                "dropped_low_relevance",
                relevance_score=relevance_score,
                relevance_tier=relevance_tier,
            ),
            None,
        )
    if relevance_action == "demote":
        reasons.append("demoted_for_relevance")

    freshness_days, rejected_item = _evaluate_freshness(
        item_id,
        source_class,
        raw_item,
        source_rule,
        reasons,
    )
    if rejected_item is not None:
        return None, rejected_item, None

    treatment, render_mode, flags = _resolve_treatment_and_render_mode(
        source_class,
        content,
        source_rule,
        indexes,
        reasons,
    )
    memory_admission, memory_kind, rejected_item = _resolve_memory_admission(
        item_id,
        source_class,
        raw_item,
        indexes,
        reasons,
    )
    if rejected_item is not None:
        return None, rejected_item, None

    normalized_key = (source_class, _normalize_text(content))
    duplicate_of = seen_keys.get(normalized_key)
    if duplicate_of is not None:
        return (
            None,
            _reject_context_item(
                item_id,
                source_class,
                "duplicate",
                duplicate_of=duplicate_of,
            ),
            None,
        )
    seen_keys[normalized_key] = item_id

    kept_content = content
    dropped_chars = 0
    source_limit = indexes["char_limits"][source_class]
    if len(kept_content) > source_limit:
        dropped_chars += len(kept_content) - source_limit
        kept_content = kept_content[:source_limit].rstrip()
        reasons.append("truncated_to_source_limit")

    treatment, review_reason = _review_for_relevance(treatment, relevance_action)
    admitted_item = _build_admitted_context_item(
        raw_item,
        index,
        item_id,
        source_class,
        source_rule,
        indexes,
        {
            "treatment": treatment,
            "render_mode": render_mode,
            "flags": flags,
            "reasons": reasons,
            "memory_admission": memory_admission,
            "memory_kind": memory_kind,
            "freshness_days": freshness_days,
            "relevance_score": relevance_score,
            "relevance_tier": relevance_tier,
            "relevance_action": relevance_action,
            "content": kept_content,
            "dropped_chars": dropped_chars,
        },
    )
    review_item = None
    if review_reason is not None:
        review_item = {
            "id": item_id,
            "source_class": source_class,
            "reason": review_reason,
            "relevance_score": relevance_score,
            "relevance_tier": relevance_tier,
        }
    return admitted_item, None, review_item


def curate_context(
    root: Path,
    input_payload: Any,
    requested_profile: Optional[str] = None,
) -> Dict[str, Any]:
    manifest, contracts = _validated_context_firewall_contracts(root)
    items, payload_profile = _input_items_and_profile(input_payload)
    profile_id = requested_profile or payload_profile or "balanced"
    ingress = contracts["context_ingress_policy"]
    memory = contracts["memory_admission_policy"]
    compaction = contracts["context_compaction_policy"]
    untrusted = contracts["untrusted_content_policy"]
    profile = _select_profile(compaction, profile_id)
    indexes = _indexed_context_contracts(ingress, memory, profile, untrusted)

    admitted, rejected, review_items = _curate_context_items(
        items,
        indexes,
        ingress.get("relevance_policy", {}),
    )
    _sort_admitted_context_items(admitted)
    total_chars = _finalize_context_budget(
        admitted,
        rejected,
        profile,
        indexes["reserved_source_classes"],
    )
    return _build_curated_context_result(
        root,
        manifest,
        profile_id,
        items,
        admitted,
        rejected,
        review_items,
        total_chars,
    )


def _validated_context_firewall_contracts(
    root: Path,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    manifest = load_json(root / "core/control_plane/codex_home_layout_manifest.json")
    contract_checks = validate_context_firewall_contracts(root, manifest)
    failed_contract_checks = [check for check in contract_checks if not check.ok]
    if failed_contract_checks:
        raise ValueError(
            "context firewall contracts are invalid: %s"
            % ", ".join(check.name for check in failed_contract_checks[:5])
        )
    return manifest, load_context_firewall_contracts(root)


def _curate_context_items(
    items: List[Any],
    indexes: Dict[str, Any],
    relevance_policy: Any,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    admitted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    review_items: List[Dict[str, Any]] = []
    seen_keys: Dict[Tuple[str, str], str] = {}
    effective_relevance_policy = relevance_policy if isinstance(relevance_policy, dict) else {}

    for index, raw_item in enumerate(items):
        admitted_item, rejected_item, review_item = _process_context_item(
            raw_item,
            index,
            indexes,
            effective_relevance_policy,
            seen_keys,
        )
        if rejected_item is not None:
            rejected.append(rejected_item)
            continue
        if admitted_item is not None:
            admitted.append(admitted_item)
        if review_item is not None:
            review_items.append(review_item)
    return admitted, rejected, review_items


def _sort_admitted_context_items(admitted: List[Dict[str, Any]]) -> None:
    admitted.sort(
        key=lambda item: (
            -item["_drop_rank"],
            item["authority_rank"],
            -(item["relevance_score"] if item["relevance_score"] is not None else -1.0),
            item["_index"],
        )
    )


def _finalize_context_budget(
    admitted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    profile: Dict[str, Any],
    reserved_source_classes: set,
) -> int:
    total_chars = _enforce_context_budget(
        admitted,
        rejected,
        profile,
        reserved_source_classes,
    )
    return total_chars


def _build_curated_context_result(
    root: Path,
    manifest: Dict[str, Any],
    profile_id: str,
    items: List[Any],
    admitted: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    review_items: List[Dict[str, Any]],
    total_chars: int,
) -> Dict[str, Any]:
    rendered_context = "\n\n".join(_render_context_block(item) for item in admitted)
    _remove_internal_sort_fields(admitted)
    return {
        "root": root.as_posix(),
        "layout_version": manifest.get("layout_version"),
        "budget_profile": profile_id,
        "summary": {
            "total_input_items": len(items),
            "admitted_items": len(admitted),
            "rejected_items": len(rejected),
            "review_items": len(review_items),
            "flagged_items": sum(1 for item in admitted if item["flags"]),
            "memory_allow_items": sum(
                1 for item in admitted if item["memory_admission"] == "allow"
            ),
            "total_chars": total_chars,
        },
        "curated_items": admitted,
        "review_items": sorted(review_items, key=lambda item: item.get("id", "")),
        "rejected_items": sorted(rejected, key=lambda item: item.get("id", "")),
        "rendered_context": rendered_context,
    }


def _render_context_block(item: Dict[str, Any]) -> str:
    header = "[%s:%s]" % (item["source_class"], item["id"])
    meta = [
        "treatment=%s" % item["treatment"],
        "memory=%s" % item["memory_admission"],
    ]
    if item["flags"]:
        meta.append("flags=%s" % ",".join(item["flags"]))
    if item["render_mode"] == "quoted_only":
        quoted = "\n".join("> %s" % line for line in item["content"].splitlines())
        content = quoted
    else:
        content = item["content"]
    return "%s\n%s\n%s" % (header, " ".join(meta), content)


def checks_as_jsonable(checks: List[FirewallCheck]) -> List[Dict[str, Any]]:
    return [asdict(check) for check in checks]
