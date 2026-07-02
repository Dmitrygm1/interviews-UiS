# Load Test Report: 20260701T175548Z

- Time: 2026-07-01T17:56:56.018693+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 60.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: 8.000s
- Wall time: 67.899s
- Peak in-flight `/next`: 31
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 300 | 0 | 4.026s | 8.043s | 8.050s | 8.059s | 8.062s | {'200': 300} | {} |
| Landing GET | 150 | 150 | 0 | 0.021s | 0.033s | 0.038s | 0.043s | 0.046s | {'200': 150} | {} |
| /next POST | 150 | 150 | 0 | 8.030s | 8.050s | 8.055s | 8.060s | 8.062s | {'200': 150} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 0.055s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 8.030s | 8.050s | 8.055s | 8.060s | 8.062s | {'200': 150} | {} |

## Docker Stats

- CPU max: 22.240%
- CPU avg: 10.250%
- Memory max: 5.000%
- Memory avg: 3.925%

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
