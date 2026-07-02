# Load Test Report: 20260702T222137Z

- Time: 2026-07-02T22:22:40.159255+00:00
- Base URL: `http://127.0.0.1:8000`
- Interview: `GENAI_WORKPLACE`
- Users: 150
- Turns per user: 1
- Start jitter: 60.0s
- Burst mode: `none`
- Timeout: 60.0s
- Expected `/next` service time: 4.520s
- Wall time: 62.301s
- Peak in-flight `/next`: 14
- Failed users: 0/150

## Request Latency

| Endpoint | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| All | 300 | 300 | 0 | 1.044s | 2.991s | 3.323s | 4.090s | 13.777s | {'200': 300} | {} |
| Landing GET | 150 | 150 | 0 | 0.017s | 0.023s | 0.027s | 0.033s | 0.034s | {'200': 150} | {} |
| /next POST | 150 | 150 | 0 | 2.563s | 3.325s | 3.603s | 6.378s | 13.777s | {'200': 150} | {} |

## Queueing Overhead

- `/next` p95 overhead versus expected service time: -0.917s

## `/next` By Turn

| Turn | Count | OK | Failed | p50 | p90 | p95 | p99 | Max | Statuses | Errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 150 | 150 | 0 | 2.563s | 3.325s | 3.603s | 6.378s | 13.777s | {'200': 150} | {} |

## Docker Stats

- CPU max: 25.500%
- CPU avg: 13.083%
- Memory max: 6.350%
- Memory avg: 5.282%

## Token Usage

- Usage directory: `app/data/usage`
- Expected usage files: 150
- Usage files found: 150
- Missing usage files: 0
- Usage records: 300
- Prompt tokens: 144150
- Cached prompt tokens: 0
- Billable prompt tokens: 144150
- Completion tokens: 5338
- Total tokens: 149488
- Estimated cost: $0.880890

### Usage By Model

| Model | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.5-2026-04-23 | 300 | 144150 | 0 | 5338 | 149488 | $0.880890 |

### Usage By Task

| Task | Requests | Prompt | Cached | Completion | Total | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| moderator | 150 | 43200 | 0 | 600 | 43800 | $0.234000 |
| probe | 150 | 100950 | 0 | 4738 | 105688 | $0.646890 |

## OpenAI Safety Note

- If run without `LOAD_TEST_MOCK_OPENAI`, this traffic can make real OpenAI calls.
- The script requires either `--expect-mock-openai` or `--allow-real-openai` before sending `/next` traffic.
