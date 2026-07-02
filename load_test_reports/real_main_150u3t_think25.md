# Load Test Report: 20260702T231416Z

- Time: 2026-07-02T23:16:09.377638+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 3
- Start jitter: 0.0s
- Initial answer delay: 15.0-35.0s
- Between-turn delay: 15.0-35.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: n/a
- Wall time: 112.934s
- Peak in-flight `/next`: 32
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 600 | 600 | 0 | 2.522s | 3.688s | 3.992s | 5.984s | 17.490s | {'200': 600} | {} |
| Landing GET | 150 | 150 | 0 | 0.223s | 0.367s | 0.380s | 0.391s | 0.402s | {'200': 150} | {} |
| /next POST | 450 | 450 | 0 | 2.766s | 3.812s | 4.240s | 6.349s | 17.490s | {'200': 450} | {} |

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 2.406s | 2.797s | 3.013s | 6.086s | 9.547s | {'200': 150} | {} |
| 1 | 150 | 150 | 0 | 2.646s | 3.295s | 3.703s | 4.097s | 4.311s | {'200': 150} | {} |
| 2 | 150 | 150 | 0 | 3.445s | 4.300s | 4.802s | 13.789s | 17.490s | {'200': 150} | {} |

## Docker Stats

- CPU max: 189.710%
- CPU avg: 23.464%
- Memory max: 9.760%
- Memory avg: 8.181%

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 150
- Usage files found: 150
- Missing usage files: 0
- Usage records: 1047
- Prompt tokens: 681647
- Cached prompt tokens: 0
- Billable prompt tokens: 681647
- Completion tokens: 64711
- Total tokens: 746358
- Estimated cost: $3.185869

### Usage By Model

| Model | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.4-mini-2026-03-17 | 149 | 222329 | 0 | 47796 | 270125 | $0.381829 |
| gpt-5.5-2026-04-23 | 898 | 459318 | 0 | 16915 | 476233 | $2.804040 |

### Usage By Task

| Task | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| moderator | 449 | 135619 | 0 | 1796 | 137415 | $0.731975 |
| probe | 300 | 216696 | 0 | 9473 | 226169 | $1.367670 |
| summary | 149 | 222329 | 0 | 47796 | 270125 | $0.381829 |
| transition | 149 | 107003 | 0 | 5646 | 112649 | $0.704395 |

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
