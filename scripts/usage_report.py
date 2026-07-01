from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_USAGE_DIR = Path("app/data/usage")


def read_usage_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}: {exc}") from exc
    return records


def token_value(record: dict[str, Any], key: str, fallback_key: str) -> int:
    value = record.get(key)
    if value is None:
        value = record.get("usage", {}).get(fallback_key)
    return int(value or 0)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "requests": len(records),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "by_model": defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        "by_task": defaultdict(lambda: {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
    }

    for record in records:
        prompt_tokens = token_value(record, "prompt_tokens", "prompt_tokens")
        completion_tokens = token_value(record, "completion_tokens", "completion_tokens")
        total_tokens = token_value(record, "total_tokens", "total_tokens") or prompt_tokens + completion_tokens
        model = record.get("response_model") or record.get("request_model") or "unknown"
        task = record.get("task") or "unknown"

        for bucket in (totals, totals["by_model"][model], totals["by_task"][task]):
            bucket["requests"] += 1 if bucket is not totals else 0
            bucket["prompt_tokens"] += prompt_tokens
            bucket["completion_tokens"] += completion_tokens
            bucket["total_tokens"] += total_tokens

    return totals


def estimated_cost(summary: dict[str, Any], input_price: float | None, output_price: float | None) -> float | None:
    if input_price is None or output_price is None:
        return None
    input_cost = summary["prompt_tokens"] / 1_000_000 * input_price
    output_cost = summary["completion_tokens"] / 1_000_000 * output_price
    return input_cost + output_cost


def print_bucket(title: str, buckets: dict[str, dict[str, int]]) -> None:
    print(title)
    for name, data in sorted(buckets.items()):
        print(
            f"  {name}: {data['requests']} requests, "
            f"{data['prompt_tokens']} prompt, "
            f"{data['completion_tokens']} completion, "
            f"{data['total_tokens']} total"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize OpenAI token usage for one interview session.")
    parser.add_argument("session_id", help="Session id, matching app/data/usage/<session_id>.jsonl")
    parser.add_argument("--usage-dir", type=Path, default=DEFAULT_USAGE_DIR, help="Usage log directory.")
    parser.add_argument("--input-price", type=float, default=None, help="Input token price per 1M tokens.")
    parser.add_argument("--output-price", type=float, default=None, help="Output token price per 1M tokens.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    usage_path = args.usage_dir / f"{args.session_id}.jsonl"
    if not usage_path.exists():
        raise SystemExit(f"No usage log found for session '{args.session_id}': {usage_path}")

    records = read_usage_records(usage_path)
    summary = summarize(records)
    cost = estimated_cost(summary, args.input_price, args.output_price)

    output = {
        "session_id": args.session_id,
        "usage_path": str(usage_path),
        "requests": summary["requests"],
        "prompt_tokens": summary["prompt_tokens"],
        "completion_tokens": summary["completion_tokens"],
        "total_tokens": summary["total_tokens"],
        "by_model": dict(summary["by_model"]),
        "by_task": dict(summary["by_task"]),
        "estimated_cost": cost,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return

    print(f"Session: {args.session_id}")
    print(f"Requests: {summary['requests']}")
    print(f"Prompt tokens: {summary['prompt_tokens']}")
    print(f"Completion tokens: {summary['completion_tokens']}")
    print(f"Total tokens: {summary['total_tokens']}")
    if cost is not None:
        print(f"Estimated cost: ${cost:.6f}")
    else:
        print("Estimated cost: provide --input-price and --output-price")
    print_bucket("By model:", summary["by_model"])
    print_bucket("By task:", summary["by_task"])


if __name__ == "__main__":
    main()
