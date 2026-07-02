# Load Test Report: 20260701T180019Z

- Time: 2026-07-01T18:00:59.092039+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 0.0s
- Burst mode: `first`
- Timeout: 60.0s
- Expected `/next` service time: 8.000s
- Wall time: 39.261s
- Peak in-flight `/next`: 150
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 300 | 0 | 4.672s | 32.333s | 33.573s | 36.616s | 37.536s | {'200': 300} | {} |
| Landing GET | 150 | 150 | 0 | 0.811s | 1.292s | 1.314s | 1.326s | 1.330s | {'200': 150} | {} |
| /next POST | 150 | 150 | 0 | 24.363s | 33.574s | 35.429s | 37.092s | 37.536s | {'200': 150} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 27.429s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 24.363s | 33.574s | 35.429s | 37.092s | 37.536s | {'200': 150} | {} |

## Docker Stats

- CPU max: 237.410%
- CPU avg: 41.537%
- Memory max: 4.500%
- Memory avg: 3.627%

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
