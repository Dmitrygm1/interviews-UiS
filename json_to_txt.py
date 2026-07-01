from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_INPUT_DIR = Path("app/data/json")
DEFAULT_OUTPUT_DIR = Path("app/data/txt")
HEADER_SEPARATOR = "=" * 80
SECTION_SEPARATOR = "-" * 80


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_timestamp(value: Any) -> str:
    parsed = parse_timestamp(value)
    if parsed is None:
        return str(value).strip() if value else "N/A"

    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(delta: timedelta) -> str:
    total_seconds = max(int(delta.total_seconds()), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def normalize_messages(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        messages = payload
    elif isinstance(payload, dict) and isinstance(payload.get("session"), list):
        messages = payload["session"]
    else:
        raise ValueError("Unsupported JSON shape; expected a list or a dict with key 'session'.")

    records = [item for item in messages if isinstance(item, dict)]
    records.sort(key=lambda msg: msg.get("order", 0))
    return records


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_content(text: Any, width: int = 100) -> str:
    raw = str(text or "").replace("\r\n", "\n").strip()
    if not raw:
        return "(empty)"

    paragraphs = [paragraph.strip() for paragraph in raw.split("\n") if paragraph.strip()]
    wrapped = [textwrap.fill(paragraph, width=width) for paragraph in paragraphs]
    return "\n".join(wrapped)


def normalize_role(message_type: Any) -> str:
    raw = str(message_type or "message").strip().lower()
    if raw == "question":
        return "Question"
    if raw == "answer":
        return "Answer"
    return raw.capitalize() if raw else "Message"


def render_transcript(messages: list[dict[str, Any]], source_name: str, fallback_session_id: str) -> str:
    if not messages:
        raise ValueError("No message records found in JSON.")

    first = messages[0]
    last = messages[-1]

    session_id = str(first.get("session_id") or last.get("session_id") or fallback_session_id)
    user_id = str(first.get("user_id") or last.get("user_id") or session_id)

    start_raw = first.get("time")
    end_raw = last.get("time")
    start_dt = parse_timestamp(start_raw)
    end_dt = parse_timestamp(end_raw)

    if start_dt is not None and end_dt is not None:
        try:
            duration = format_duration(end_dt - start_dt)
        except TypeError:
            duration = "N/A"
    else:
        duration = "N/A"

    question_count = sum(1 for msg in messages if str(msg.get("type", "")).lower() == "question")
    answer_count = sum(1 for msg in messages if str(msg.get("type", "")).lower() == "answer")

    flagged_values = [safe_int(msg.get("flagged_messages")) for msg in messages]
    flagged_values = [value for value in flagged_values if value is not None]
    flagged_total = flagged_values[-1] if flagged_values else "N/A"

    terminated = last.get("terminated")
    terminated_value = terminated if terminated is not None else "N/A"

    lines: list[str] = [
        HEADER_SEPARATOR,
        "Interview Transcript",
        HEADER_SEPARATOR,
        "",
        f"Source File: {source_name}",
        f"User ID: {user_id}",
        f"Session ID: {session_id}",
        f"Conversation Start: {format_timestamp(start_raw)}",
        f"Conversation End: {format_timestamp(end_raw)}",
        f"Interview Duration: {duration}",
        f"Total Messages: {len(messages)}",
        f"Questions: {question_count}",
        f"Answers: {answer_count}",
        f"Flagged Messages: {flagged_total}",
        f"Terminated: {terminated_value}",
        "",
        SECTION_SEPARATOR,
        "",
    ]

    for index, message in enumerate(messages, start=1):
        role = normalize_role(message.get("type"))
        timestamp = format_timestamp(message.get("time"))
        order = message.get("order")
        order_suffix = f" #{order}" if order is not None else f" #{index}"
        lines.append(f"{role}{order_suffix} ({timestamp})")
        lines.append(format_content(message.get("content")))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def convert_json_files(input_dir: Path, output_dir: Path, overwrite: bool, dry_run: bool) -> tuple[int, int, int]:
    converted = 0
    skipped = 0
    errors = 0

    for json_path in sorted(input_dir.glob("*.json")):
        txt_path = output_dir / f"{json_path.stem}.txt"

        if txt_path.exists() and not overwrite:
            skipped += 1
            print(f"SKIP   {json_path.name} -> {txt_path.name} (already converted)")
            continue

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            messages = normalize_messages(payload)
            txt_content = render_transcript(messages, source_name=json_path.name, fallback_session_id=json_path.stem)
        except Exception as exc:  # pragma: no cover - best effort for varied data
            errors += 1
            print(f"ERROR  {json_path.name}: {exc}")
            continue

        if dry_run:
            converted += 1
            print(f"DRYRUN {json_path.name} -> {txt_path}")
            continue

        txt_path.write_text(txt_content, encoding="utf-8")
        converted += 1
        print(f"DONE   {json_path.name} -> {txt_path.name}")

    return converted, skipped, errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert interview JSON files to readable TXT transcripts. "
            "By default scans app/data/json and writes TXT files to app/data/txt."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing JSON files (default: app/data/json).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write TXT files (default: app/data/txt).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing TXT files instead of skipping them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without writing any files.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise SystemExit(f"Input path is not a directory: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    converted, skipped, errors = convert_json_files(
        input_dir=input_dir,
        output_dir=output_dir,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    mode = "Dry run complete" if args.dry_run else "Conversion complete"
    converted_label = "to convert" if args.dry_run else "converted"
    print(f"{mode}: {converted} {converted_label}, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
