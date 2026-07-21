import argparse
import concurrent.futures
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import string
import subprocess
import threading
import time
from typing import Any

import requests
import usage_report


REALISTIC_ANSWERS = [
    (
        "Jeg bruker generativ KI mest til utkast, oppsummeringer og a strukturere "
        "notater etter moter. Det sparer tid, men jeg kontrollerer alltid fakta og "
        "formuleringer for noe deles videre."
    ),
    (
        "I min rolle jobber jeg mye med koordinering, rapportering og kundedialog. "
        "KI hjelper med forste versjoner av tekster, men jeg er fortsatt forsiktig "
        "med sensitive opplysninger og beslutninger som krever faglig vurdering."
    ),
    (
        "Det som fungerer best er nar jeg har en tydelig oppgave og kan gi kontekst. "
        "Da blir svarene nyttige. Hvis oppgaven er uklar, ma jeg bruke mer tid pa "
        "a rette opp eller forklare pa nytt."
    ),
    (
        "Jeg opplever bade nytte og litt usikkerhet. Det kan gjore rutinearbeid "
        "raskere, men jeg vil gjerne ha klarere retningslinjer for hva som er greit "
        "a bruke verktoyet til pa jobb."
    ),
    (
        "Kollegaer snakker mer om KI na enn tidligere. Noen forventer nesten at vi "
        "skal bruke det, mens andre er skeptiske. For meg handler det mye om a finne "
        "en trygg og praktisk balanse."
    ),
]


def random_session_id(rng: random.Random, length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(rng.choice(chars) for _ in range(length))


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def fmt_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}s"


def parse_percent(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.strip().rstrip("%"))
    except ValueError:
        return None


class DockerStatsSampler:
    def __init__(self, container: str | None, interval: float):
        self.container = container
        self.interval = interval
        self.records: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.container:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(self.interval + 1, 2))

    def _run(self) -> None:
        self._sample()
        while not self._stop.wait(self.interval):
            self._sample()

    def _sample(self) -> None:
        try:
            completed = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    self.container,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            self.records.append({"time": time.time(), "error": type(exc).__name__})
            return

        if completed.returncode != 0:
            self.records.append(
                {
                    "time": time.time(),
                    "error": completed.stderr.strip() or f"exit {completed.returncode}",
                }
            )
            return

        for line in completed.stdout.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = {"raw": line}
            record["time"] = time.time()
            self.records.append(record)


def record_http(
    session: requests.Session,
    method: str,
    url: str,
    endpoint: str,
    timeout: float,
    global_start: float,
    user_index: int,
    turn: int | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    started = time.perf_counter()
    start_offset = started - global_start
    response_json = None
    status_code = None
    error = None
    response_bytes = 0
    ended = False

    try:
        if method == "GET":
            response = session.get(url, timeout=timeout)
        else:
            response = session.post(url, json=payload, timeout=timeout)
        status_code = response.status_code
        response_bytes = len(response.content or b"")
        if "application/json" in response.headers.get("content-type", ""):
            response_json = response.json()
        elif endpoint == "/next":
            error = "non_json_response"
        ended = response_json.get("message", "").endswith("---END---") if response_json else False
    except requests.Timeout:
        error = "timeout"
    except requests.RequestException as exc:
        error = type(exc).__name__
    except json.JSONDecodeError:
        error = "json_decode_error"

    latency = time.perf_counter() - started
    ok = error is None and status_code is not None and 200 <= status_code < 400
    return (
        {
            "endpoint": endpoint,
            "method": method,
            "user_index": user_index,
            "turn": turn,
            "status_code": status_code,
            "ok": ok,
            "error": error,
            "latency": latency,
            "start_offset": start_offset,
            "end_offset": time.perf_counter() - global_start,
            "response_bytes": response_bytes,
            "ended": ended,
        },
        response_json,
    )


def run_single_interview(
    args: argparse.Namespace,
    user_index: int,
    run_id: str,
    global_start: float,
    records: list[dict[str, Any]],
    lock: threading.Lock,
    landing_barrier: threading.Barrier | None,
    barrier: threading.Barrier | None,
) -> dict[str, Any]:
    rng = random.Random(args.seed + user_index)
    session_id = f"{args.session_prefix}-{run_id}-{user_index:04d}-{random_session_id(rng)}"
    session = requests.Session()
    base_url = args.base_url.rstrip("/")
    user_result = {"session_id": session_id, "completed_turns": 0, "failed": False}

    if args.start_jitter > 0:
        time.sleep(rng.uniform(0, args.start_jitter))

    landing_url = f"{base_url}/{args.interview_id}/{session_id}"
    rec, _ = record_http(
        session,
        "GET",
        landing_url,
        "landing",
        args.timeout,
        global_start,
        user_index,
    )
    with lock:
        records.append(rec)
    if not rec["ok"]:
        user_result["failed"] = True
        if landing_barrier:
            landing_barrier.abort()
        if barrier:
            barrier.abort()
        return user_result

    if landing_barrier:
        try:
            landing_barrier.wait(timeout=args.barrier_timeout)
        except threading.BrokenBarrierError:
            user_result["failed"] = True
            return user_result

    if args.initial_max_delay > 0:
        time.sleep(rng.uniform(args.initial_min_delay, args.initial_max_delay))

    next_url = f"{base_url}/next"
    for turn in range(args.turns):
        if turn > 0 and args.max_delay > 0:
            time.sleep(rng.uniform(args.min_delay, args.max_delay))

        if barrier and (args.burst_turns == "all" or (args.burst_turns == "first" and turn == 0)):
            try:
                barrier.wait(timeout=args.barrier_timeout)
            except threading.BrokenBarrierError:
                user_result["failed"] = True
                return user_result

        answer = REALISTIC_ANSWERS[turn % len(REALISTIC_ANSWERS)]
        payload = {
            "session_id": session_id,
            "interview_id": args.interview_id,
            "user_message": f"{answer} [load-test user {user_index}, turn {turn}]",
        }
        rec, response_json = record_http(
            session,
            "POST",
            next_url,
            "/next",
            args.timeout,
            global_start,
            user_index,
            turn=turn,
            payload=payload,
        )
        with lock:
            records.append(rec)
        if not rec["ok"]:
            user_result["failed"] = True
            if barrier:
                barrier.abort()
            return user_result
        user_result["completed_turns"] += 1
        if rec["ended"] or (response_json and response_json.get("message", "").endswith("---END---")):
            return user_result

    return user_result


def endpoint_summary(records: list[dict[str, Any]], endpoint: str | None = None) -> dict[str, Any]:
    selected = [rec for rec in records if endpoint is None or rec["endpoint"] == endpoint]
    latencies = [rec["latency"] for rec in selected]
    ok_records = [rec for rec in selected if rec["ok"]]
    status_counts = Counter(str(rec["status_code"]) for rec in selected if rec["status_code"] is not None)
    error_counts = Counter(rec["error"] for rec in selected if rec["error"])
    return {
        "count": len(selected),
        "ok": len(ok_records),
        "failed": len(selected) - len(ok_records),
        "p50": percentile(latencies, 50),
        "p90": percentile(latencies, 90),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "max": max(latencies) if latencies else None,
        "status_counts": dict(status_counts),
        "error_counts": dict(error_counts),
    }


def max_in_flight(records: list[dict[str, Any]], endpoint: str) -> int:
    events = []
    for rec in records:
        if rec["endpoint"] != endpoint:
            continue
        events.append((rec["start_offset"], 1))
        events.append((rec["end_offset"], -1))
    current = 0
    peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], -item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def summarize_by_turn(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_turn: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if rec["endpoint"] == "/next":
            by_turn[str(rec["turn"])].append(rec)
    return {turn: endpoint_summary(items) for turn, items in sorted(by_turn.items(), key=lambda item: int(item[0]))}


def print_summary(name: str, summary: dict[str, Any], timeout: float) -> None:
    slow_or_timeout = 0
    print(
        f"{name}: count={summary['count']} ok={summary['ok']} failed={summary['failed']} "
        f"p50={fmt_seconds(summary['p50'])} p90={fmt_seconds(summary['p90'])} "
        f"p95={fmt_seconds(summary['p95'])} p99={fmt_seconds(summary['p99'])} "
        f"max={fmt_seconds(summary['max'])}"
    )
    if summary["status_counts"]:
        print(f"  statuses: {summary['status_counts']}")
    if summary["error_counts"]:
        print(f"  errors: {summary['error_counts']}")
    if summary["max"] and summary["max"] >= timeout:
        slow_or_timeout = 1
    if slow_or_timeout:
        print(f"  warning: at least one request reached the configured {timeout:.1f}s timeout window")


def docker_stats_summary(records: list[dict[str, Any]]) -> dict[str, float | None]:
    cpu_values = [parse_percent(record.get("CPUPerc")) for record in records]
    cpu_values = [value for value in cpu_values if value is not None]
    mem_values = [parse_percent(record.get("MemPerc")) for record in records]
    mem_values = [value for value in mem_values if value is not None]
    return {
        "cpu_max": max(cpu_values) if cpu_values else None,
        "cpu_avg": sum(cpu_values) / len(cpu_values) if cpu_values else None,
        "mem_max": max(mem_values) if mem_values else None,
        "mem_avg": sum(mem_values) / len(mem_values) if mem_values else None,
    }


def usage_bucket(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "requests": data["requests"],
        "prompt_tokens": data["prompt_tokens"],
        "cached_prompt_tokens": data["cached_prompt_tokens"],
        "cache_write_prompt_tokens": data["cache_write_prompt_tokens"],
        "billable_prompt_tokens": data["billable_prompt_tokens"],
        "completion_tokens": data["completion_tokens"],
        "total_tokens": data["total_tokens"],
        "estimated_cost": data["estimated_cost"],
    }


def collect_usage_summary(users: list[dict[str, Any]], usage_dir: Path) -> dict[str, Any]:
    expected_sessions = [user["session_id"] for user in users if user["completed_turns"] > 0]
    records = []
    found_sessions = []
    missing_sessions = []
    unreadable_files = {}

    for session_id in expected_sessions:
        usage_path = usage_dir / f"{session_id}.jsonl"
        if not usage_path.exists():
            missing_sessions.append(session_id)
            continue
        try:
            session_records = usage_report.read_usage_records(usage_path)
        except Exception as exc:
            unreadable_files[session_id] = str(exc)
            continue
        found_sessions.append(session_id)
        records.extend(session_records)

    summary = usage_report.summarize(records)
    return {
        "usage_dir": str(usage_dir),
        "expected_sessions": len(expected_sessions),
        "usage_files_found": len(found_sessions),
        "missing_usage_sessions": missing_sessions,
        "unreadable_usage_files": unreadable_files,
        "records": len(records),
        "prompt_tokens": summary["prompt_tokens"],
        "cached_prompt_tokens": summary["cached_prompt_tokens"],
        "cache_write_prompt_tokens": summary["cache_write_prompt_tokens"],
        "billable_prompt_tokens": summary["billable_prompt_tokens"],
        "completion_tokens": summary["completion_tokens"],
        "total_tokens": summary["total_tokens"],
        "estimated_cost": summary["estimated_cost"],
        "by_model": {model: usage_bucket(data) for model, data in summary["by_model"].items()},
        "by_task": {task: usage_bucket(data) for task, data in summary["by_task"].items()},
        "priced_as": {model: sorted(priced_as) for model, priced_as in summary["priced_as"].items()},
        "unpriced_models": sorted(summary["unpriced_models"]),
    }


def read_json_file(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def find_session_files(session_id: str, data_dir: Path) -> list[Path]:
    direct_path = data_dir / f"{session_id}.json"
    if direct_path.exists():
        return [direct_path]

    matches = []
    for path in data_dir.glob("*.json"):
        try:
            session = read_json_file(path)
        except (json.JSONDecodeError, OSError):
            continue
        if session and any(row.get("session_id") == session_id for row in session):
            matches.append(path)
    return matches


def collect_session_summary(users: list[dict[str, Any]], data_dir: Path) -> dict[str, Any]:
    expected_sessions = [user for user in users if user["completed_turns"] > 0]
    missing_sessions = []
    duplicate_sessions = []
    unreadable_sessions = {}
    incomplete_sessions = []
    answer_count_distribution = Counter()
    question_count_distribution = Counter()
    found_sessions = 0

    for user in expected_sessions:
        session_id = user["session_id"]
        paths = find_session_files(session_id, data_dir)
        if not paths:
            missing_sessions.append(session_id)
            continue
        if len(paths) > 1:
            duplicate_sessions.append({"session_id": session_id, "paths": [str(path) for path in paths]})

        try:
            session = read_json_file(paths[0])
        except Exception as exc:
            unreadable_sessions[session_id] = str(exc)
            continue

        found_sessions += 1
        answer_count = sum(1 for row in session if row.get("type") == "answer")
        question_count = sum(1 for row in session if row.get("type") == "question")
        answer_count_distribution[answer_count] += 1
        question_count_distribution[question_count] += 1

        expected_answers = user["completed_turns"]
        if answer_count < expected_answers:
            incomplete_sessions.append(
                {
                    "session_id": session_id,
                    "user_index": user.get("user_index"),
                    "answers": answer_count,
                    "expected_answers": expected_answers,
                    "questions": question_count,
                    "path": str(paths[0]),
                }
            )

    return {
        "data_dir": str(data_dir),
        "expected_sessions": len(expected_sessions),
        "session_files_found": found_sessions,
        "missing_sessions": missing_sessions,
        "duplicate_sessions": duplicate_sessions,
        "unreadable_sessions": unreadable_sessions,
        "incomplete_sessions": incomplete_sessions,
        "answer_count_distribution": dict(sorted(answer_count_distribution.items())),
        "question_count_distribution": dict(sorted(question_count_distribution.items())),
    }


def markdown_number(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:.3f}{suffix}"


def markdown_summary_row(name: str, summary: dict[str, Any]) -> str:
    return (
        f"| {name} | {summary['count']} | {summary['ok']} | {summary['failed']} | "
        f"{markdown_number(summary['p50'], 's')} | {markdown_number(summary['p90'], 's')} | "
        f"{markdown_number(summary['p95'], 's')} | {markdown_number(summary['p99'], 's')} | "
        f"{markdown_number(summary['max'], 's')} | {summary['status_counts']} | {summary['error_counts']} |"
    )


def build_markdown_report(report: dict[str, Any]) -> str:
    args = report["args"]
    summaries = report["summaries"]
    next_summary = summaries["next"]
    docker = docker_stats_summary(report.get("docker_stats", []))
    failed_users = sum(1 for user in report["users"] if user["failed"])
    expected = args.get("expected_next_seconds")
    overhead = None
    if expected is not None and next_summary["p95"] is not None:
        overhead = next_summary["p95"] - expected

    lines = [
        f"# Load Test Report: {report['run_id']}",
        "",
        f"- Time: {report['time']}",
        f"- Base URL: `{args['base_url']}`",
        f"- Interview: `{args['interview_id']}`",
        f"- Users: {args['users']}",
        f"- Turns per user: {args['turns']}",
        f"- Start jitter: {args['start_jitter']}s",
        f"- Sync after landing: {args['sync_after_landing']}",
        f"- Initial answer delay: {args['initial_min_delay']}-{args['initial_max_delay']}s",
        f"- Between-turn delay: {args['min_delay']}-{args['max_delay']}s",
        f"- Burst mode: `{args['burst_turns']}`",
        f"- Timeout: {args['timeout']}s",
        f"- Expected `/next` service time: {markdown_number(expected, 's')}",
        f"- Wall time: {markdown_number(report['wall_time'], 's')}",
        f"- Peak in-flight `/next`: {report['peak_in_flight_next']}",
        f"- Failed users: {failed_users}/{len(report['users'])}",
        "",
        "## Request Latency",
        "",
        "| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        markdown_summary_row("All", summaries["all"]),
        markdown_summary_row("Landing GET", summaries["landing"]),
        markdown_summary_row("/next POST", next_summary),
    ]

    if overhead is not None:
        lines.extend(
            [
                "",
                "## Queueing Overhead",
                "",
                f"- `/next` p95 overhead versus expected service time: {markdown_number(overhead, 's')}",
            ]
        )

    if summaries.get("next_by_turn"):
        lines.extend(
            [
                "",
                "## `/next` By Turn",
                "",
                "| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for turn, summary in summaries["next_by_turn"].items():
            lines.append(markdown_summary_row(turn, summary))

    lines.extend(
        [
            "",
            "## Docker Stats",
            "",
            f"- CPU max: {markdown_number(docker['cpu_max'], '%')}",
            f"- CPU avg: {markdown_number(docker['cpu_avg'], '%')}",
            f"- Memory max: {markdown_number(docker['mem_max'], '%')}",
            f"- Memory avg: {markdown_number(docker['mem_avg'], '%')}",
        ]
    )

    usage = report.get("usage_summary")
    if usage:
        lines.extend(
            [
                "",
                "## Token Usage",
                "",
                f"- Usage directory: `{usage['usage_dir']}`",
                f"- Expected usage files: {usage['expected_sessions']}",
                f"- Usage files found: {usage['usage_files_found']}",
                f"- Missing usage files: {len(usage['missing_usage_sessions'])}",
                f"- Usage records: {usage['records']}",
                f"- Prompt tokens: {usage['prompt_tokens']}",
                f"- Cached prompt tokens: {usage['cached_prompt_tokens']}",
                f"- Cache write prompt tokens: {usage.get('cache_write_prompt_tokens', 0)}",
                f"- Billable prompt tokens: {usage['billable_prompt_tokens']}",
                f"- Completion tokens: {usage['completion_tokens']}",
                f"- Total tokens: {usage['total_tokens']}",
                f"- Estimated cost: ${usage['estimated_cost']:.6f}",
            ]
        )
        if usage["unpriced_models"]:
            lines.append(f"- Unpriced models: {', '.join(usage['unpriced_models'])}")
        if usage["by_model"]:
            lines.extend(
                [
                    "",
                    "### Usage By Model",
                    "",
                    "| Model | Requests | Prompt | Cached | Cache write | Completion | Total | Estimated Cost |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for model, data in sorted(usage["by_model"].items()):
                lines.append(
                    f"| {model} | {data['requests']} | {data['prompt_tokens']} | "
                    f"{data['cached_prompt_tokens']} | {data.get('cache_write_prompt_tokens', 0)} | "
                    f"{data['completion_tokens']} | "
                    f"{data['total_tokens']} | ${data['estimated_cost']:.6f} |"
                )
        if usage["by_task"]:
            lines.extend(
                [
                    "",
                    "### Usage By Task",
                    "",
                    "| Task | Requests | Prompt | Cached | Cache write | Completion | Total | Estimated Cost |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for task, data in sorted(usage["by_task"].items()):
                lines.append(
                    f"| {task} | {data['requests']} | {data['prompt_tokens']} | "
                    f"{data['cached_prompt_tokens']} | {data.get('cache_write_prompt_tokens', 0)} | "
                    f"{data['completion_tokens']} | "
                    f"{data['total_tokens']} | ${data['estimated_cost']:.6f} |"
                )

    session_summary = report.get("session_summary")
    if session_summary:
        lines.extend(
            [
                "",
                "## Session Integrity",
                "",
                f"- Data directory: `{session_summary['data_dir']}`",
                f"- Expected session files: {session_summary['expected_sessions']}",
                f"- Session files found: {session_summary['session_files_found']}",
                f"- Missing session files: {len(session_summary['missing_sessions'])}",
                f"- Duplicate session files: {len(session_summary['duplicate_sessions'])}",
                f"- Unreadable session files: {len(session_summary['unreadable_sessions'])}",
                f"- Incomplete sessions: {len(session_summary['incomplete_sessions'])}",
                f"- Answer count distribution: `{session_summary['answer_count_distribution']}`",
                f"- Question count distribution: `{session_summary['question_count_distribution']}`",
            ]
        )
        if session_summary["incomplete_sessions"]:
            lines.extend(["", "### Incomplete Sessions", ""])
            for item in session_summary["incomplete_sessions"][:20]:
                lines.append(
                    f"- `{item['session_id']}`: {item['answers']}/"
                    f"{item['expected_answers']} answers saved at `{item['path']}`"
                )

    lines.extend(
        [
            "",
            "## OpenAI Safety Note",
            "",
            "- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.",
            "- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.",
        ]
    )
    return "\n".join(lines) + "\n"


def print_openai_risk(args: argparse.Namespace) -> None:
    next_requests = args.users * args.turns
    chat_min = next_requests * 2
    chat_max = next_requests * 3
    moderation = next_requests
    print(
        "OpenAI risk estimate if this server is not in LOAD_TEST_MOCK_OPENAI mode: "
        f"{next_requests} /next requests can produce roughly {chat_min}-{chat_max} "
        f"chat-completion calls plus about {moderation} moderation calls."
    )
    if args.expect_mock_openai:
        print("Safety mode: expecting LOAD_TEST_MOCK_OPENAI on the server; no real model calls should occur.")
    elif args.allow_real_openai:
        print("Safety mode: --allow-real-openai was provided; this may spend API credits and hit rate limits.")
    else:
        raise SystemExit(
            "Refusing to run /next traffic without --expect-mock-openai or --allow-real-openai. "
            "Use --expect-mock-openai for VM/uWSGI tests, or --allow-real-openai for a deliberate paid API test."
        )


def build_report(
    args: argparse.Namespace,
    run_id: str,
    records: list[dict[str, Any]],
    users: list[dict[str, Any]],
    docker_stats: list[dict[str, Any]],
    wall_time: float,
    usage_summary: dict[str, Any] | None = None,
    session_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_args = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    return {
        "run_id": run_id,
        "time": datetime.now(timezone.utc).isoformat(),
        "args": report_args,
        "wall_time": wall_time,
        "requests": records,
        "users": users,
        "summaries": {
            "all": endpoint_summary(records),
            "landing": endpoint_summary(records, "landing"),
            "next": endpoint_summary(records, "/next"),
            "next_by_turn": summarize_by_turn(records),
        },
        "peak_in_flight_next": max_in_flight(records, "/next"),
        "docker_stats": docker_stats,
        "usage_summary": usage_summary,
        "session_summary": session_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load tester for simultaneous interview sessions.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interview-id", default="GENAI_WORKPLACE")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--initial-min-delay", type=float, default=0.0)
    parser.add_argument("--initial-max-delay", type=float, default=0.0)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--session-prefix", default="loadtest")
    parser.add_argument("--start-jitter", type=float, default=0.0)
    parser.add_argument("--sync-after-landing", action="store_true")
    parser.add_argument("--burst-turns", choices=["none", "first", "all"], default="first")
    parser.add_argument("--barrier-timeout", type=float, default=120.0)
    parser.add_argument("--expect-mock-openai", action="store_true")
    parser.add_argument("--allow-real-openai", action="store_true")
    parser.add_argument("--expected-next-seconds", type=float, default=None)
    parser.add_argument("--docker-container", default=None)
    parser.add_argument("--stats-interval", type=float, default=2.0)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--usage-dir", type=Path, default=Path("app/data/usage"))
    parser.add_argument("--data-dir", type=Path, default=Path("app/data/json"))
    parser.add_argument("--skip-usage-summary", action="store_true")
    parser.add_argument("--skip-session-summary", action="store_true")
    args = parser.parse_args()

    if args.min_delay > args.max_delay:
        raise SystemExit("--min-delay cannot be greater than --max-delay")
    if args.initial_min_delay > args.initial_max_delay:
        raise SystemExit("--initial-min-delay cannot be greater than --initial-max-delay")
    if args.users < 1 or args.turns < 0:
        raise SystemExit("--users must be positive and --turns cannot be negative")

    print_openai_risk(args)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    max_workers = args.max_workers or args.users
    print(
        f"Starting load test run {run_id}: users={args.users}, turns={args.turns}, "
        f"burst_turns={args.burst_turns}, workers={max_workers}, timeout={args.timeout:.1f}s"
    )

    records: list[dict[str, Any]] = []
    lock = threading.Lock()
    landing_barrier = threading.Barrier(args.users) if args.users > 1 and args.sync_after_landing else None
    barrier = threading.Barrier(args.users) if args.users > 1 and args.burst_turns != "none" else None
    sampler = DockerStatsSampler(args.docker_container, args.stats_interval)

    global_start = time.perf_counter()
    sampler.start()
    users: list[dict[str, Any]] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    run_single_interview,
                    args,
                    user_index,
                    run_id,
                    global_start,
                    records,
                    lock,
                    landing_barrier,
                    barrier,
                )
                for user_index in range(args.users)
            ]
            for future in concurrent.futures.as_completed(futures):
                users.append(future.result())
    finally:
        sampler.stop()

    wall_time = time.perf_counter() - global_start
    records.sort(key=lambda rec: rec["start_offset"])
    users.sort(key=lambda user: user["session_id"])
    usage_summary = None
    if not args.skip_usage_summary:
        usage_summary = collect_usage_summary(users, args.usage_dir)
    session_summary = None
    if not args.skip_session_summary:
        session_summary = collect_session_summary(users, args.data_dir)
    report = build_report(args, run_id, records, users, sampler.records, wall_time, usage_summary, session_summary)

    total_requests = len(records)
    next_count = report["summaries"]["next"]["count"]
    throughput = total_requests / wall_time if wall_time > 0 else 0
    next_throughput = next_count / wall_time if wall_time > 0 else 0
    failed_users = sum(1 for user in users if user["failed"])

    print("\nLoad test complete.")
    print(f"Total wall time: {wall_time:.2f}s")
    print(f"Total requests: {total_requests} ({throughput:.2f} req/s)")
    print(f"/next requests: {next_count} ({next_throughput:.2f} req/s)")
    print(f"Peak in-flight /next requests: {report['peak_in_flight_next']}")
    print(f"Users failed: {failed_users}/{len(users)}")
    print_summary("All requests", report["summaries"]["all"], args.timeout)
    print_summary("Landing GET", report["summaries"]["landing"], args.timeout)
    print_summary("/next POST", report["summaries"]["next"], args.timeout)

    if args.expected_next_seconds is not None and report["summaries"]["next"]["p95"] is not None:
        overhead = report["summaries"]["next"]["p95"] - args.expected_next_seconds
        print(f"/next p95 overhead vs expected service time: {overhead:.3f}s")

    if report["summaries"]["next_by_turn"]:
        print("\n/next by turn:")
        for turn, summary in report["summaries"]["next_by_turn"].items():
            print_summary(f"  turn {turn}", summary, args.timeout)

    if sampler.records:
        docker = docker_stats_summary(sampler.records)
        if docker["cpu_max"] is not None or docker["mem_max"] is not None:
            print("\nDocker stats:")
            if docker["cpu_max"] is not None:
                print(f"  CPU max={docker['cpu_max']:.2f}% avg={docker['cpu_avg']:.2f}%")
            if docker["mem_max"] is not None:
                print(f"  Mem max={docker['mem_max']:.2f}% avg={docker['mem_avg']:.2f}%")
        else:
            print(f"\nDocker stats samples collected: {len(sampler.records)}")

    if usage_summary:
        print("\nToken usage:")
        print(
            f"  usage files {usage_summary['usage_files_found']}/{usage_summary['expected_sessions']}, "
            f"records={usage_summary['records']}, total_tokens={usage_summary['total_tokens']}, "
            f"estimated_cost=${usage_summary['estimated_cost']:.6f}"
        )
        if usage_summary["missing_usage_sessions"]:
            print(f"  missing usage files: {len(usage_summary['missing_usage_sessions'])}")
        if usage_summary["unpriced_models"]:
            print(f"  unpriced models: {', '.join(usage_summary['unpriced_models'])}")

    if session_summary:
        print("\nSession integrity:")
        print(
            f"  session files {session_summary['session_files_found']}/"
            f"{session_summary['expected_sessions']}, "
            f"incomplete={len(session_summary['incomplete_sessions'])}, "
            f"missing={len(session_summary['missing_sessions'])}, "
            f"duplicates={len(session_summary['duplicate_sessions'])}"
        )

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Wrote JSON report: {args.json_output}")

    if args.markdown_output:
        with open(args.markdown_output, "w", encoding="utf-8") as f:
            f.write(build_markdown_report(report))
        print(f"Wrote Markdown report: {args.markdown_output}")


if __name__ == "__main__":
    main()
