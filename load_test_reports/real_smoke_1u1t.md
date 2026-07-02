# Load Test Report: 20260702T222045Z

- Time: 2026-07-02T22:20:50.099067+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 1
- Turns per user: 1
- Start jitter: 0.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: 0.000s
- Wall time: 4.198s
- Peak in-flight `/next`: 1
- Failed users: 0/1

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 2 | 2 | 0 | 2.028s | 3.629s | 3.829s | 3.989s | 4.029s | {'200': 2} | {} |
| Landing GET | 1 | 1 | 0 | 0.026s | 0.026s | 0.026s | 0.026s | 0.026s | {'200': 1} | {} |
| /next POST | 1 | 1 | 0 | 4.029s | 4.029s | 4.029s | 4.029s | 4.029s | {'200': 1} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 4.029s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 1 | 1 | 0 | 4.029s | 4.029s | 4.029s | 4.029s | 4.029s | {'200': 1} | {} |

## Docker Stats

- CPU max: 1.840%
- CPU avg: 0.930%
- Memory max: 3.060%
- Memory avg: 3.045%

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 1
- Usage files found: 1
- Missing usage files: 0
- Usage records: 2
- Prompt tokens: 961
- Cached prompt tokens: 0
- Billable prompt tokens: 961
- Completion tokens: 36
- Total tokens: 997
- Estimated cost: $0.005885

### Usage By Model

| Model | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.5-2026-04-23 | 2 | 961 | 0 | 36 | 997 | $0.005885 |

### Usage By Task

| Task | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| moderator | 1 | 288 | 0 | 4 | 292 | $0.001560 |
| probe | 1 | 673 | 0 | 32 | 705 | $0.004325 |

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
