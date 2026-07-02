# Load Test Report: 20260702T222105Z

- Time: 2026-07-02T22:21:28.013266+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 20
- Turns per user: 1
- Start jitter: 20.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: 4.030s
- Wall time: 22.342s
- Peak in-flight `/next`: 6
- Failed users: 0/20

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 40 | 40 | 0 | 1.084s | 3.795s | 3.845s | 11.993s | 17.198s | {'200': 40} | {} |
| Landing GET | 20 | 20 | 0 | 0.017s | 0.022s | 0.023s | 0.024s | 0.024s | {'200': 20} | {} |
| /next POST | 20 | 20 | 0 | 2.593s | 3.845s | 4.520s | 14.662s | 17.198s | {'200': 20} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 0.490s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 20 | 20 | 0 | 2.593s | 3.845s | 4.520s | 14.662s | 17.198s | {'200': 20} | {} |

## Docker Stats

- CPU max: 10.730%
- CPU avg: 4.923%
- Memory max: 3.960%
- Memory avg: 3.634%

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 20
- Usage files found: 20
- Missing usage files: 0
- Usage records: 40
- Prompt tokens: 19220
- Cached prompt tokens: 0
- Billable prompt tokens: 19220
- Completion tokens: 723
- Total tokens: 19943
- Estimated cost: $0.117790

### Usage By Model

| Model | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.5-2026-04-23 | 40 | 19220 | 0 | 723 | 19943 | $0.117790 |

### Usage By Task

| Task | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| moderator | 20 | 5760 | 0 | 80 | 5840 | $0.031200 |
| probe | 20 | 13460 | 0 | 643 | 14103 | $0.086590 |

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
