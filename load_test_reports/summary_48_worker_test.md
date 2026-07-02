# 48-Worker Load-Test Summary

Test date: 2026-07-01

These tests used `LOAD_TEST_MOCK_OPENAI=1`, so they tested VM/uWSGI/nginx/session behavior without spending OpenAI credits. Mock service time means the `/next` request still occupied a synchronous uWSGI worker while "waiting" for the model.

## Configuration Tested

```ini
listen = 512
workers = 48
cheaper = 16
cheaper-initial = 16
```

## Results

| Scenario | Workers | Users | Arrival Pattern | Mock `/next` Service Time | Peak In-Flight `/next` | Failed Users | `/next` p50 | `/next` p95 | `/next` max | Notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Spread 150 over 60s | 32 | 150 | Random over 60s | 8s | 31 | 0 | 8.032s | 8.064s | 9.420s | Baseline corrected 32-worker spread run |
| Spread 150 over 60s | 48 | 150 | Random over 60s | 8s | 31 | 0 | 8.030s | 8.055s | 8.062s | No meaningful queueing |
| Spread 150 over 60s | 48 | 150 | Random over 60s | 15s | 49 | 0 | 15.042s | 15.080s | 15.286s | One request briefly queued; no user-visible issue |
| Burst 150 at once | 48 | 150 | Synchronized | 8s | 150 | 0 | 16.751s | 25.157s | 32.334s | Warm worker pool; completes under 60s timeout |
| Burst 150 at once | 48 | 150 | Synchronized | 15s | 150 | 6 | 30.464s | 45.735s | 60.163s | 5 nginx 504s and 1 client timeout |

## Interpretation

Raising the cap from 32 to 48 helps with longer OpenAI waits, especially when users are spread over a minute rather than clicking at the same instant.

For the realistic spread pattern:

- At about 8s `/next` latency, 150 users over 60s were fine with either 32 or 48 workers.
- At about 15s `/next` latency, 48 workers handled the spread pattern cleanly.
- CPU and memory were not stressed in spread tests; the 15s spread run had CPU max 33.18% and memory max 5.05%.

For the extreme synchronized burst:

- 48 workers handled 150 simultaneous submits at 8s service time with no failures, but users still waited in waves. p95 was 25.157s.
- 48 workers did not fully protect the 150-user synchronized burst at 15s service time. The last wave reached the 60s timeout boundary, producing 504/timeouts.

## Practical Takeaway

`workers = 48` is a reasonable improvement over 32 for this VM and workload, but it is not a guarantee against a worst-case synchronized spike plus slow OpenAI responses.

For launch, the safest operating assumption is:

```text
active backend requests ~= submit rate per second * OpenAI wait seconds
```

If 150 respondents submit over 60 seconds:

```text
2.5 submits/sec * 15s ~= 37.5 active requests
```

That fits under 48 workers. If they submit all at once, queueing is unavoidable, and with 15s OpenAI waits some users can still hit the 60s browser timeout.

