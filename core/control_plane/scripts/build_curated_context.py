#!/usr/bin/env python3
"""Build a deterministic curated context bundle from heterogeneous inputs."""

import argparse
import json
from pathlib import Path

from context_firewall_lib import DEFAULT_ROOT, curate_context, load_json
from curated_context_redaction import redacted_curated_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a governed curated-context report. Defaults to redacted "
            "metadata; use --emit-raw-content only when the caller explicitly "
            "needs the rendered context body."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON payload with an items list.",
    )
    parser.add_argument(
        "--profile",
        default="balanced",
        help="Compaction profile id. Defaults to balanced.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    parser.add_argument(
        "--emit-raw-content",
        action="store_true",
        help=(
            "Emit curated item content and rendered_context. This is intended "
            "for explicit integration use, not report-only review."
        ),
    )
    return parser


def _print_redacted_text(payload: dict) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("budget_profile: %s" % payload["budget_profile"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
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
        print("- %s | %s | %s" % (item.get("id"), item.get("source_class"), item.get("reason")))


def _raw_payload(result: dict) -> dict:
    payload = dict(result)
    payload["privacy"] = {
        "report_only": False,
        "raw_content_emitted": True,
        "rendered_context_emitted": True,
        "mutated_files": False,
        "automatic_runtime_hook": False,
        "memory_store_mutation": False,
    }
    return payload


def _print_raw_text(payload: dict) -> None:
    print("layout_version: %s" % payload["layout_version"])
    print("budget_profile: %s" % payload["budget_profile"])
    print("privacy: %s" % json.dumps(payload["privacy"], ensure_ascii=False, sort_keys=True))
    print("summary: %s" % json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print("")
    print(payload["rendered_context"])


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()
    input_path = Path(args.input)
    if not input_path.exists():
        parser.error("input file does not exist: %s" % input_path)
    try:
        payload = load_json(input_path)
    except json.JSONDecodeError as exc:
        parser.error("input file is not valid JSON: %s" % exc)
    try:
        result = curate_context(root, payload, requested_profile=args.profile)
    except ValueError as exc:
        parser.error(str(exc))

    if args.emit_raw_content:
        payload = _raw_payload(result)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        _print_raw_text(payload)
        return 0

    payload = redacted_curated_payload(result, payload)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    _print_redacted_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
