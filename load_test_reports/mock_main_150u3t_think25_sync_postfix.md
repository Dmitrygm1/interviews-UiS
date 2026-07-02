# Load Test Report: 20260702T232249Z

- Time: 2026-07-02T23:24:51.572115+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 3
- Start jitter: 0.0s
- Sync after landing: True
- Initial answer delay: 15.0-35.0s
- Between-turn delay: 15.0-35.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: n/a
- Wall time: 122.251s
- Peak in-flight `/next`: 60
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 600 | 600 | 0 | 4.930s | 6.964s | 7.408s | 7.957s | 8.552s | {'200': 600} | {} |
| Landing GET | 150 | 150 | 0 | 0.762s | 1.169s | 1.216s | 1.234s | 1.246s | {'200': 150} | {} |
| /next POST | 450 | 450 | 0 | 5.090s | 7.208s | 7.566s | 8.032s | 8.552s | {'200': 450} | {} |

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 6.791s | 7.702s | 7.934s | 8.322s | 8.552s | {'200': 150} | {} |
| 1 | 150 | 150 | 0 | 4.958s | 5.406s | 5.437s | 5.596s | 5.660s | {'200': 150} | {} |
| 2 | 150 | 150 | 0 | 4.923s | 5.258s | 5.336s | 5.489s | 5.593s | {'200': 150} | {} |

## Docker Stats

- CPU max: 227.460%
- CPU avg: 7.307%
- Memory max: 4.340%
- Memory avg: 3.880%

## Session Integrity

- Data directory: `app/data/json`
- Expected session files: 150
- Session files found: 150
- Missing session files: 0
- Duplicate session files: 0
- Unreadable session files: 0
- Incomplete sessions: 0
- Answer count distribution: `{3: 150}`
- Question count distribution: `{4: 150}`

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
