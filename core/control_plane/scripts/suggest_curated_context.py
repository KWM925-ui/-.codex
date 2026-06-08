#!/usr/bin/env python3
"""Suggest a redacted curated-context plan without emitting raw content."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from context_firewall_lib import DEFAULT_ROOT, curate_context, load_json
from curated_context_redaction import (
    print_redacted_curated_text,
    redacted_curated_payload,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a redacted curated-context suggestion. This is a soft "
            "integration surface: it does not mutate sessions or memory and "
            "does not emit raw content."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to /home/example/.codex.",
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
    return parser


def build_curated_context_suggestion(
    root: Path,
    input_payload: Any,
    profile: str,
) -> Dict[str, Any]:
    curated = curate_context(root, input_payload, requested_profile=profile)
    return redacted_curated_payload(
        curated,
        input_payload,
        {
            "soft_integration": True,
        },
    )


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
        result = build_curated_context_suggestion(root, payload, args.profile)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print_redacted_curated_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
