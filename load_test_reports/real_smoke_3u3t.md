# Load Test Report: 20260702T231342Z

- Time: 2026-07-02T23:14:02.496405+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 3
- Turns per user: 3
- Start jitter: 0.0s
- Initial answer delay: 1.0-2.0s
- Between-turn delay: 1.0-2.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: n/a
- Wall time: 19.822s
- Peak in-flight `/next`: 3
- Failed users: 0/3

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 12 | 12 | 0 | 3.197s | 3.709s | 5.806s | 7.847s | 8.358s | {'200': 12} | {} |
| Landing GET | 3 | 3 | 0 | 0.016s | 0.019s | 0.019s | 0.019s | 0.019s | {'200': 3} | {} |
| /next POST | 9 | 9 | 0 | 3.397s | 4.646s | 6.502s | 7.987s | 8.358s | {'200': 9} | {} |

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 3 | 3 | 0 | 3.397s | 7.366s | 7.862s | 8.259s | 8.358s | {'200': 3} | {} |
| 1 | 3 | 3 | 0 | 3.013s | 3.307s | 3.344s | 3.373s | 3.380s | {'200': 3} | {} |
| 2 | 3 | 3 | 0 | 3.623s | 3.699s | 3.709s | 3.716s | 3.718s | {'200': 3} | {} |

## Docker Stats

- CPU max: 4.700%
- CPU avg: 1.759%
- Memory max: 4.200%
- Memory avg: 4.193%

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 3
- Usage files found: 3
- Missing usage files: 0
- Usage records: 21
- Prompt tokens: 13710
- Cached prompt tokens: 0
- Billable prompt tokens: 13710
- Completion tokens: 1304
- Total tokens: 15014
- Estimated cost: $0.063848

### Usage By Model

| Model | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.4-mini-2026-03-17 | 3 | 4485 | 0 | 971 | 5456 | $0.007733 |
| gpt-5.5-2026-04-23 | 18 | 9225 | 0 | 333 | 9558 | $0.056115 |

### Usage By Task

| Task | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| moderator | 9 | 2727 | 0 | 36 | 2763 | $0.014715 |
| probe | 6 | 4335 | 0 | 198 | 4533 | $0.027615 |
| summary | 3 | 4485 | 0 | 971 | 5456 | $0.007733 |
| transition | 3 | 2163 | 0 | 99 | 2262 | $0.013785 |

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
