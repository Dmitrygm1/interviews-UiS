from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_USAGE_DIR = Path("app/data/usage")
MODEL_PRICES_PER_1M = {
    # Official OpenAI API model pages, checked 2026-07-01.
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
}


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


def nested_token_value(record: dict[str, Any], path: tuple[str, ...]) -> int:
    value: Any = record
    for key in path:
        if not isinstance(value, dict):
            return 0
        value = value.get(key)
    return int(value or 0)


def normalize_model(model: str | None) -> str:
    return re.sub(r"\s+", "-", str(model or "unknown").strip().lower())


def model_pricing(model: str | None) -> tuple[str | None, dict[str, float] | None]:
    normalized = normalize_model(model)
    for model_id, prices in MODEL_PRICES_PER_1M.items():
        if normalized == model_id or re.match(rf"^{re.escape(model_id)}-\d{{4}}", normalized):
            return model_id, prices
    return None, None


def record_tokens(record: dict[str, Any]) -> dict[str, int | str]:
    prompt_tokens = token_value(record, "prompt_tokens", "prompt_tokens")
    completion_tokens = token_value(record, "completion_tokens", "completion_tokens")
    cached_prompt_tokens = (
        token_value(record, "cached_prompt_tokens", "cached_prompt_tokens")
        or nested_token_value(record, ("usage", "prompt_tokens_details", "cached_tokens"))
        or nested_token_value(record, ("usage", "input_tokens_details", "cached_tokens"))
    )
    total_tokens = token_value(record, "total_tokens", "total_tokens") or prompt_tokens + completion_tokens
    cached_prompt_tokens = min(cached_prompt_tokens, prompt_tokens)
    return {
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached_prompt_tokens,
        "billable_prompt_tokens": prompt_tokens - cached_prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def empty_bucket() -> dict[str, Any]:
    return {
        "requests": 0,
        "prompt_tokens": 0,
        "cached_prompt_tokens": 0,
        "billable_prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def add_to_bucket(bucket: dict[str, Any], tokens: dict[str, int | str], cost: float | None) -> None:
    bucket["requests"] += 1
    for key in ("prompt_tokens", "cached_prompt_tokens", "billable_prompt_tokens", "completion_tokens", "total_tokens"):
        bucket[key] += int(tokens[key])
    if cost is not None:
        bucket["estimated_cost"] += cost


def record_cost(
    tokens: dict[str, int | str],
    model: str,
    fallback_input_price: float | None,
    fallback_output_price: float | None,
) -> tuple[float | None, str | None]:
    priced_model, prices = model_pricing(model)
    if prices is None:
        if fallback_input_price is None or fallback_output_price is None:
            return None, None
        prices = {
            "input": fallback_input_price,
            "cached_input": fallback_input_price,
            "output": fallback_output_price,
        }

    input_cost = int(tokens["billable_prompt_tokens"]) / 1_000_000 * prices["input"]
    cached_input_cost = int(tokens["cached_prompt_tokens"]) / 1_000_000 * prices["cached_input"]
    output_cost = int(tokens["completion_tokens"]) / 1_000_000 * prices["output"]
    return input_cost + cached_input_cost + output_cost, priced_model


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    return summarize_with_cost(records, None, None)


def summarize_with_cost(
    records: list[dict[str, Any]],
    fallback_input_price: float | None,
    fallback_output_price: float | None,
) -> dict[str, Any]:
    totals = empty_bucket()
    totals["by_model"] = defaultdict(empty_bucket)
    totals["by_task"] = defaultdict(empty_bucket)
    totals["unpriced_models"] = set()
    totals["priced_as"] = defaultdict(set)

    for record in records:
        tokens = record_tokens(record)
        model = record.get("response_model") or record.get("request_model") or "unknown"
        task = record.get("task") or "unknown"
        cost, priced_model = record_cost(tokens, model, fallback_input_price, fallback_output_price)

        if cost is None:
            totals["unpriced_models"].add(str(model))
        else:
            if priced_model is not None:
                totals["priced_as"][str(model)].add(priced_model)
            add_to_bucket(totals, tokens, cost)
            add_to_bucket(totals["by_model"][model], tokens, cost)
            add_to_bucket(totals["by_task"][task], tokens, cost)
            continue

        add_to_bucket(totals, tokens, None)
        add_to_bucket(totals["by_model"][model], tokens, None)
        add_to_bucket(totals["by_task"][task], tokens, None)

    return totals


def print_bucket(title: str, buckets: dict[str, dict[str, Any]]) -> None:
    print(title)
    for name, data in sorted(buckets.items()):
        print(
            f"  {name}: {data['requests']} requests, "
            f"{data['prompt_tokens']} prompt "
            f"({data['cached_prompt_tokens']} cached), "
            f"{data['completion_tokens']} completion, "
            f"{data['total_tokens']} total, "
            f"${data['estimated_cost']:.6f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize OpenAI token usage for one interview session.")
    parser.add_argument("session_id", help="Session id, matching app/data/usage/<session_id>.jsonl")
    parser.add_argument("--usage-dir", type=Path, default=DEFAULT_USAGE_DIR, help="Usage log directory.")
    parser.add_argument(
        "--fallback-input-price-per-1m",
        "--input-price-per-1m",
        "--input-price",
        dest="fallback_input_price_per_1m",
        type=float,
        default=None,
        help="Fallback input token price per 1M tokens for unknown models.",
    )
    parser.add_argument(
        "--fallback-output-price-per-1m",
        "--output-price-per-1m",
        "--output-price",
        dest="fallback_output_price_per_1m",
        type=float,
        default=None,
        help="Fallback output token price per 1M tokens for unknown models.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    usage_path = args.usage_dir / f"{args.session_id}.jsonl"
    if not usage_path.exists():
        raise SystemExit(f"No usage log found for session '{args.session_id}': {usage_path}")

    records = read_usage_records(usage_path)
    summary = summarize_with_cost(records, args.fallback_input_price_per_1m, args.fallback_output_price_per_1m)

    output = {
        "session_id": args.session_id,
        "usage_path": str(usage_path),
        "requests": summary["requests"],
        "prompt_tokens": summary["prompt_tokens"],
        "completion_tokens": summary["completion_tokens"],
        "total_tokens": summary["total_tokens"],
        "by_model": dict(summary["by_model"]),
        "by_task": dict(summary["by_task"]),
        "estimated_cost": summary["estimated_cost"],
        "known_prices_per_1m": MODEL_PRICES_PER_1M,
        "priced_as": {model: sorted(priced_as) for model, priced_as in summary["priced_as"].items()},
        "unpriced_models": sorted(summary["unpriced_models"]),
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return

    print(f"Session: {args.session_id}")
    print(f"Requests: {summary['requests']}")
    print(f"Prompt tokens: {summary['prompt_tokens']}")
    print(f"Cached prompt tokens: {summary['cached_prompt_tokens']}")
    print(f"Billable prompt tokens: {summary['billable_prompt_tokens']}")
    print(f"Completion tokens: {summary['completion_tokens']}")
    print(f"Total tokens: {summary['total_tokens']}")
    print(f"Estimated cost: ${summary['estimated_cost']:.6f}")
    if summary["unpriced_models"]:
        print(
            "Unpriced models: "
            + ", ".join(sorted(summary["unpriced_models"]))
            + " (use fallback price flags or add them to MODEL_PRICES_PER_1M)"
        )
    print_bucket("By model:", summary["by_model"])
    print_bucket("By task:", summary["by_task"])


if __name__ == "__main__":
    main()
