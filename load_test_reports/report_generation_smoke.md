# Load Test Report: 20260702T222030Z

- Time: 2026-07-02T22:20:30.879098+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 1
- Turns per user: 0
- Start jitter: 0.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: n/a
- Wall time: 0.041s
- Peak in-flight `/next`: 0
- Failed users: 0/1

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 1 | 1 | 0 | 0.040s | 0.040s | 0.040s | 0.040s | 0.040s | {'200': 1} | {} |
| Landing GET | 1 | 1 | 0 | 0.040s | 0.040s | 0.040s | 0.040s | 0.040s | {'200': 1} | {} |
| /next POST | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | {} | {} |

## Docker Stats

- CPU max: n/a
- CPU avg: n/a
- Memory max: n/a
- Memory avg: n/a

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 0
- Usage files found: 0
- Missing usage files: 0
- Usage records: 0
- Prompt tokens: 0
- Cached prompt tokens: 0
- Billable prompt tokens: 0
- Completion tokens: 0
- Total tokens: 0
- Estimated cost: $0.000000

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
