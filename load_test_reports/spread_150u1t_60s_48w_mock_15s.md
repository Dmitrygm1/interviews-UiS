# Load Test Report: 20260701T175723Z

- Time: 2026-07-01T17:58:38.204099+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 60.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: 15.000s
- Wall time: 74.950s
- Peak in-flight `/next`: 49
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 300 | 0 | 8.038s | 15.060s | 15.068s | 15.118s | 15.286s | {'200': 300} | {} |
| Landing GET | 150 | 150 | 0 | 0.030s | 0.045s | 0.121s | 0.682s | 1.068s | {'200': 150} | {} |
| /next POST | 150 | 150 | 0 | 15.042s | 15.068s | 15.080s | 15.174s | 15.286s | {'200': 150} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 0.080s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 15.042s | 15.068s | 15.080s | 15.174s | 15.286s | {'200': 150} | {} |

## Docker Stats

- CPU max: 33.180%
- CPU avg: 11.358%
- Memory max: 5.050%
- Memory avg: 4.167%

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
