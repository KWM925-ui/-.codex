#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract metadata for the latest completed round from a Codex "
            "session jsonl. Raw last-agent text is hidden unless explicitly requested."
        )
    )
    parser.add_argument("session", help="Path to the session jsonl.")
    parser.add_argument(
        "--include-message",
        action="store_true",
        help="Also render the last agent message. Defaults to off to avoid transcript noise.",
    )
    parser.add_argument(
        "--chars",
        type=int,
        default=4000,
        help="Maximum characters when --include-message is used.",
    )
    args = parser.parse_args()

    session = Path(args.session).expanduser().resolve()
    last_complete = None
    last_agent_message = ""

    with session.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            payload = item.get("payload", {})
            if item.get("type") == "event_msg" and payload.get("type") == "task_complete":
                last_complete = item
                last_agent_message = payload.get("last_agent_message", "")

    modified = datetime.fromtimestamp(session.stat().st_mtime)
    print(f"Session: {session}")
    print(f"Modified: {modified.isoformat(sep=' ', timespec='seconds')}")

    if last_complete is None:
        print("Latest task_complete: <none>")
        return 0

    payload = last_complete.get("payload", {})
    print(f"Latest task_complete timestamp: {last_complete.get('timestamp', '<unknown>')}")
    print(f"Turn ID: {payload.get('turn_id', '<unknown>')}")
    if "completed_at" in payload:
        print(f"Completed at (epoch): {payload['completed_at']}")
    if "duration_ms" in payload:
        print(f"Duration ms: {payload['duration_ms']}")
    if args.include_message:
        print("Last agent message:")
        print(truncate(last_agent_message, args.chars))
    else:
        print("Last agent message: <hidden; pass --include-message to render>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
