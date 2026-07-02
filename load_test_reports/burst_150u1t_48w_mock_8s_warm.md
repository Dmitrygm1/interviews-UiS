# Load Test Report: 20260701T180108Z

- Time: 2026-07-01T18:01:42.751649+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 0.0s
- Burst mode: `first`
- Timeout: 60.0s
- Expected `/next` service time: 8.000s
- Wall time: 34.376s
- Peak in-flight `/next`: 150
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 300 | 0 | 4.748s | 24.750s | 25.008s | 32.130s | 32.334s | {'200': 300} | {} |
| Landing GET | 150 | 150 | 0 | 0.963s | 1.419s | 1.455s | 1.478s | 1.484s | {'200': 150} | {} |
| /next POST | 150 | 150 | 0 | 16.751s | 25.009s | 25.157s | 32.183s | 32.334s | {'200': 150} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 17.157s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 16.751s | 25.009s | 25.157s | 32.183s | 32.334s | {'200': 150} | {} |

## Docker Stats

- CPU max: 266.230%
- CPU avg: 46.188%
- Memory max: 5.160%
- Memory avg: 5.141%

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
