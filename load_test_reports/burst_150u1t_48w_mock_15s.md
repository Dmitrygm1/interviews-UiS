# Load Test Report: 20260701T175854Z

- Time: 2026-07-01T17:59:56.311063+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 0.0s
- Burst mode: `first`
- Timeout: 60.0s
- Expected `/next` service time: 15.000s
- Wall time: 61.659s
- Peak in-flight `/next`: 150
- Failed users: 6/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 294 | 6 | 8.000s | 45.464s | 45.666s | 60.045s | 60.163s | {'200': 294, '504': 5} | {'non_json_response': 5, 'timeout': 1} |
| Landing GET | 150 | 150 | 0 | 0.662s | 0.916s | 0.960s | 0.980s | 0.985s | {'200': 150} | {} |
| /next POST | 150 | 144 | 6 | 30.464s | 45.666s | 45.735s | 60.092s | 60.163s | {'200': 144, '504': 5} | {'non_json_response': 5, 'timeout': 1} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: 30.735s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 144 | 6 | 30.464s | 45.666s | 45.735s | 60.092s | 60.163s | {'200': 144, '504': 5} | {'non_json_response': 5, 'timeout': 1} |

## Docker Stats

- CPU max: 250.980%
- CPU avg: 18.159%
- Memory max: 5.170%
- Memory avg: 5.138%

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
