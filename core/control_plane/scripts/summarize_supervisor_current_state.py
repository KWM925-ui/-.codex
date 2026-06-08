#!/usr/bin/env python3
"""Summarize the active supervisor state without rewriting ledger history."""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_PACK_ROOT = Path(
    os.environ.get(
        "CODEX_SUPERVISOR_PACK_ROOT",
        "~/.codex/project_assets/codex_home/supervisor",
    )
).expanduser()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print the current supervisor frontier from the last matching "
            "ledger sections. This is read-only and does not emit session text."
        ),
    )
    parser.add_argument(
        "--pack-root",
        default=str(DEFAULT_PACK_ROOT),
        help=(
            "Supervisor pack root. Defaults to CODEX_SUPERVISOR_PACK_ROOT or "
            "~/.codex/project_assets/codex_home/supervisor."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    return parser


def _section_instances(text: str, name: str) -> List[str]:
    pattern = re.compile(
        r"^## %s\s*$([\s\S]*?)(?=^## |\Z)" % re.escape(name),
        re.MULTILINE,
    )
    return [match.group(1).strip() for match in pattern.finditer(text)]


def _last_section(text: str, name: str) -> str:
    instances = _section_instances(text, name)
    return instances[-1] if instances else ""


def _current_phase(state_text: str) -> str:
    matches = re.findall(r"Current phase:\s*`([^`]+)`", state_text)
    return matches[-1] if matches else ""


def _first_bullets(section_text: str, limit: int = 8) -> List[str]:
    bullets = []
    current = ""
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                bullets.append(current)
                if len(bullets) >= limit:
                    return bullets
            current = stripped[2:]
        elif current and stripped:
            current += " " + stripped
    if current and len(bullets) < limit:
        bullets.append(current)
    return bullets


def summarize_supervisor_current_state(pack_root: Path) -> Dict[str, Any]:
    ledger_path = pack_root / "supervisor_ledger.md"
    state_path = pack_root / "state_machine.md"
    ledger_text = ledger_path.read_text(encoding="utf-8")
    state_text = state_path.read_text(encoding="utf-8")
    current_frontier = _last_section(ledger_text, "Current Frontier")
    only_question = _last_section(ledger_text, "Only Question Next Round")
    forbidden = _last_section(ledger_text, "Forbidden Next Round")
    promotion = _last_section(ledger_text, "Promotion Gate")
    return {
        "pack_root": pack_root.as_posix(),
        "current_phase": _current_phase(state_text),
        "current_frontier": _first_bullets(current_frontier),
        "only_question": _first_bullets(only_question),
        "forbidden_next_round": _first_bullets(forbidden),
        "promotion_gate": _first_bullets(promotion),
        "section_counts": {
            "current_frontier": len(_section_instances(ledger_text, "Current Frontier")),
            "only_question": len(_section_instances(ledger_text, "Only Question Next Round")),
            "forbidden_next_round": len(_section_instances(ledger_text, "Forbidden Next Round")),
            "promotion_gate": len(_section_instances(ledger_text, "Promotion Gate")),
        },
        "privacy": {
            "read_only": True,
            "raw_session_text_emitted": False,
            "ledger_history_rewritten": False,
        },
    }


def _print_text(payload: Dict[str, Any]) -> None:
    print("当前阶段：%s" % (payload["current_phase"] or "未识别"))
    for label, key in [
        ("当前要解的问题", "current_frontier"),
        ("下一轮唯一问题", "only_question"),
        ("本轮不能做的事", "forbidden_next_round"),
        ("通过条件", "promotion_gate"),
    ]:
        print("")
        print(label + "：")
        entries = payload.get(key) or []
        if not entries:
            print("- 未识别")
            continue
        for entry in entries:
            print("- %s" % entry)


def main() -> int:
    args = _build_parser().parse_args()
    payload = summarize_supervisor_current_state(Path(args.pack_root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
