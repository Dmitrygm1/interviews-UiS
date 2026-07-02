import argparse
import concurrent.futures
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import random
import string
import subprocess
import threading
import time
from typing import Any

import requests


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
        if barrier:
            barrier.abort()
        return user_result

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
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "time": datetime.now(timezone.utc).isoformat(),
        "args": vars(args),
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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load tester for simultaneous interview sessions.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--interview-id", default="GENAI_WORKPLACE")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--session-prefix", default="loadtest")
    parser.add_argument("--start-jitter", type=float, default=0.0)
    parser.add_argument("--burst-turns", choices=["none", "first", "all"], default="first")
    parser.add_argument("--barrier-timeout", type=float, default=120.0)
    parser.add_argument("--expect-mock-openai", action="store_true")
    parser.add_argument("--allow-real-openai", action="store_true")
    parser.add_argument("--expected-next-seconds", type=float, default=None)
    parser.add_argument("--docker-container", default=None)
    parser.add_argument("--stats-interval", type=float, default=2.0)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--markdown-output", default=None)
    args = parser.parse_args()

    if args.min_delay > args.max_delay:
        raise SystemExit("--min-delay cannot be greater than --max-delay")
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
    barrier = threading.Barrier(args.users) if args.users > 1 and args.burst_turns != "none" else None
    sampler = DockerStatsSampler(args.docker_container, args.stats_interval)

    global_start = time.perf_counter()
    sampler.start()
    users: list[dict[str, Any]] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(run_single_interview, args, user_index, run_id, global_start, records, lock, barrier)
                for user_index in range(args.users)
            ]
            for future in concurrent.futures.as_completed(futures):
                users.append(future.result())
    finally:
        sampler.stop()

    wall_time = time.perf_counter() - global_start
    records.sort(key=lambda rec: rec["start_offset"])
    users.sort(key=lambda user: user["session_id"])
    report = build_report(args, run_id, records, users, sampler.records, wall_time)

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
