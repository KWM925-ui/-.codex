#!/usr/bin/env python3
"""Shared redaction helpers for report-only context-firewall tools."""

import json
from typing import Any, Dict, List, Optional


def input_items_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


def _metadata_by_id(input_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    metadata: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(input_items, start=1):
        item_id = str(item.get("id") or "item-%d" % index)
        content = item.get("content")
        content_chars = len(content) if isinstance(content, str) else 0
        metadata[item_id] = {
            "title": item.get("title", ""),
            "path": item.get("path", ""),
            "source_class": item.get("source_class"),
            "origin_type": item.get("_probe_origin_type"),
            "line_no": item.get("_probe_line_no"),
            "original_chars": item.get("_probe_original_chars", content_chars),
            "input_chars": item.get("_probe_input_chars", content_chars),
            "has_content": isinstance(content, str) and bool(content.strip()),
        }
    return metadata


def redact_curated_result(
    result: Dict[str, Any],
    input_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return curation metadata without raw content or rendered context."""
    metadata_by_id = _metadata_by_id(input_items)
    redacted_curated = []
    for item in result.get("curated_items", []):
        metadata = metadata_by_id.get(item["id"], {})
        redacted_curated.append(
            {
                "id": item["id"],
                "title": metadata.get("title", item.get("title", "")),
                "path": metadata.get("path", item.get("path", "")),
                "source_class": item["source_class"],
                "origin_type": metadata.get("origin_type"),
                "line_no": metadata.get("line_no"),
                "treatment": item["treatment"],
                "render_mode": item["render_mode"],
                "flags": item["flags"],
                "reasons": item["reasons"],
                "memory_admission": item["memory_admission"],
                "memory_kind": item["memory_kind"],
                "freshness_days": item["freshness_days"],
                "relevance_score": item["relevance_score"],
                "relevance_action": item["relevance_action"],
                "relevance_tier": item["relevance_tier"],
                "authority_rank": item["authority_rank"],
                "original_chars": metadata.get("original_chars"),
                "input_chars": metadata.get("input_chars"),
                "kept_chars": item["kept_chars"],
                "dropped_chars": item["dropped_chars"],
            }
        )
    return {
        "summary": result.get("summary", {}),
        "curated_items": redacted_curated,
        "review_items": result.get("review_items", []),
        "rejected_items": result.get("rejected_items", []),
    }


def redacted_curated_payload(
    result: Dict[str, Any],
    input_payload: Any,
    privacy_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    redacted = redact_curated_result(
        result,
        input_items_from_payload(input_payload),
    )
    privacy = {
        "report_only": True,
        "raw_content_emitted": False,
        "rendered_context_emitted": False,
        "mutated_files": False,
        "automatic_runtime_hook": False,
        "memory_store_mutation": False,
    }
    if privacy_overrides:
        privacy.update(privacy_overrides)
    return {
        "root": result.get("root"),
        "layout_version": result.get("layout_version"),
        "budget_profile": result.get("budget_profile"),
        "privacy": privacy,
        "summary": redacted["summary"],
        "curated_items": redacted["curated_items"],
        "review_items": redacted["review_items"],
        "rejected_items": redacted["rejected_items"],
    }


def print_redacted_curated_text(payload: Dict[str, Any]) -> None:
    """Print redacted curation metadata in one shared human-readable format."""
    print("layout_version: %s" % payload["layout_version"])
    print("budget_profile: %s" % payload["budget_profile"])
    print(
        "privacy: %s"
        % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True)
    )
    print(
        "summary: %s"
        % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True)
    )
    print("")
    print("curated_items:")
    for item in payload["curated_items"]:
        print(
            "- %s | %s | action=%s | treatment=%s | chars=%s/%s | flags=%s"
            % (
                item["id"],
                item["source_class"],
                item["relevance_action"],
                item["treatment"],
                item["kept_chars"],
                item.get("input_chars"),
                ",".join(item["flags"]) if item["flags"] else "(none)",
            )
        )
    print("")
    print("review_items:")
    for item in payload["review_items"]:
        print("- %s | %s | %s" % (item["id"], item["source_class"], item["reason"]))
    print("")
    print("rejected_items:")
    for item in payload["rejected_items"]:
        print(
            "- %s | %s | %s"
            % (item.get("id"), item.get("source_class"), item.get("reason"))
        )
