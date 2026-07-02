# Real API Load-Test Summary

Test date: 2026-07-02

The app was run in normal OpenAI mode, with `LOAD_TEST_MOCK_OPENAI=0`. The tested backend configuration was:

```ini
listen = 512
workers = 48
cheaper = 16
cheaper-initial = 16
```

The main launch-shape test modeled 150 active respondents in the same short time window, with one answer submitted per respondent and submit times randomly spread over 60 seconds. This intentionally did not model 150 simultaneous submit clicks.

## Real API Runs

| Run | Users | Arrival Pattern | `/next` OK | `/next` Failed | Peak In-Flight `/next` | `/next` p50 | `/next` p90 | `/next` p95 | `/next` p99 | `/next` max | Usage Records | Total Tokens | Estimated Cost |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `real_smoke_1u1t` | 1 | single request | 1 | 0 | 1 | 4.029s | 4.029s | 4.029s | 4.029s | 4.029s | 2 | 997 | $0.005885 |
| `real_ramp_20u1t_20s` | 20 | random over 20s | 20 | 0 | 6 | 2.593s | 3.845s | 4.520s | 14.662s | 17.198s | 40 | 19,943 | $0.117790 |
| `real_main_150u1t_60s` | 150 | random over 60s | 150 | 0 | 14 | 2.563s | 3.325s | 3.603s | 6.378s | 13.777s | 300 | 149,488 | $0.880890 |

## Main Run Token Usage

| Task | Requests | Prompt Tokens | Completion Tokens | Total Tokens | Estimated Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| `moderator` | 150 | 43,200 | 600 | 43,800 | $0.234000 |
| `probe` | 150 | 100,950 | 4,738 | 105,688 | $0.646890 |
| **Total** | **300** | **144,150** | **5,338** | **149,488** | **$0.880890** |

All 300 chat-completion usage records were written. Moderation endpoint calls are not token-metered in the app usage logs, but all `/next` responses completed with HTTP 200.

## Overload And Failure Check

- Main run: 300/300 HTTP requests succeeded.
- `/next`: 150/150 succeeded.
- No client timeouts, 5xx responses, or non-JSON `/next` responses.
- Peak in-flight `/next` requests was 14, well below the 48-worker cap.
- Docker stats during the main run: CPU max 25.50%, CPU avg 13.08%, memory max 6.35%.
- App/nginx log scan found no `HTTP/1.1 429`, `HTTP/1.1 5xx`, rate-limit, traceback, timeout, or internal-server-error entries during the real test window.

## Interpretation

For the tested launch-shape scenario, users did not experience extra delay caused by VM overload. The main run's p95 `/next` latency was 3.603s, lower than the 20-user ramp p95 of 4.520s, and the backend never approached the 48-worker cap.

The single slowest `/next` was 13.777s, consistent with normal upstream latency tail rather than VM queueing: only 14 `/next` requests were in flight at peak, CPU stayed low, and there were no HTTP failures or rate-limit errors.

## Artifacts

- JSON report: `load_test_reports/real_main_150u1t_60s.json`
- Markdown report: `load_test_reports/real_main_150u1t_60s.md`
- Raw generated session JSON: `load_test_reports/raw_real_20260702/json/`
- Raw OpenAI usage JSONL: `load_test_reports/raw_real_20260702/usage/`

