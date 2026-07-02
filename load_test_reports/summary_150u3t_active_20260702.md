# 150-User 3-Turn Active Conversation Load Test

Date: 2026-07-02

## Scenario

This test models 150 respondents all active in the interview at the same time, not 150 respondents all continuously holding a backend request open.

Each simulated user:

- Opened `GENAI_WORKPLACE`.
- Answered 3 questions.
- Waited 15-35 seconds before each answer, averaging about 25 seconds.
- Used realistic answer text instead of dummy one-word answers.

The third answer matters because the first `GENAI_WORKPLACE` topic has length 3, so turn 3 exercises the topic transition path with summary + transition work.

## Real OpenAI Run

Report: `load_test_reports/real_main_150u3t_think25.md`

Command shape:

```bash
python3 scripts/load_test.py \
  --base-url http://127.0.0.1:8000 \
  --interview-id GENAI_WORKPLACE \
  --users 150 \
  --turns 3 \
  --initial-min-delay 15 \
  --initial-max-delay 35 \
  --min-delay 15 \
  --max-delay 35 \
  --burst-turns none \
  --max-workers 150 \
  --allow-real-openai \
  --timeout 60 \
  --docker-container interviews-app-1
```

Results:

- Total `/next` requests: 450.
- HTTP success: 450/450.
- Failed users: 0/150.
- Peak in-flight `/next` requests: 32.
- `/next` p50: 2.766s.
- `/next` p95: 4.240s.
- `/next` p99: 6.349s.
- `/next` max: 17.490s.
- Docker CPU max: 189.710%.
- Docker CPU average: 23.464%.
- Docker memory max: 9.760%.
- Estimated OpenAI cost: `$3.185869`.

By turn:

| Turn | p50 | p95 | p99 | Max |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 2.406s | 3.013s | 6.086s | 9.547s |
| 1 | 2.646s | 3.703s | 4.097s | 4.311s |
| 2 | 3.445s | 4.802s | 13.789s | 17.490s |

Token usage:

- Usage files found: 150/150.
- Usage records: 1047.
- Expected records for a perfect 150-user, 3-turn run: 1050.
- Cost estimate: `$3.185869`.

The missing 3 usage records exposed an important issue: one session returned HTTP 200 for all requests, but its first `/next` did not save an answer or call OpenAI. It appears the backend failed to find the just-created timestamp-named session file during the first submit and restarted that session instead.

## Fix Applied

I changed the local file backend so new sessions are written to deterministic per-session filenames and updates are atomic:

- `app/database/file.py`
  - New sessions now use `<session_id>.json` instead of timestamp-only filenames.
  - Existing timestamp-named sessions are still readable for backward compatibility.
  - Session writes now go through a temporary file and `os.replace()`.

This avoids the concurrent-start lookup race that hid behind HTTP 200s in the first real run.

## Post-Fix Synchronized VM/uWSGI Run

Report: `load_test_reports/mock_main_150u3t_think25_sync_postfix.md`

This rerun used `LOAD_TEST_MOCK_OPENAI=1` with artificial model delays. It did not test OpenAI rate limits, but it did test the VM, nginx/uWSGI, Flask request handling, and local session persistence under the same 150-user, 3-turn active-user shape. It also synchronized after landing so all 150 users were definitely on the first question before the 15-35 second answer timers started.

Results:

- Total `/next` requests: 450.
- HTTP success: 450/450.
- Failed users: 0/150.
- Peak in-flight `/next` requests: 60.
- `/next` p50: 5.090s.
- `/next` p95: 7.566s.
- `/next` p99: 8.032s.
- `/next` max: 8.552s.
- Docker CPU max: 227.460%.
- Docker CPU average: 7.307%.
- Docker memory max: 4.340%.
- Session files found: 150/150.
- Incomplete sessions: 0.
- Answer count distribution: `{3: 150}`.
- Question count distribution: `{4: 150}`.

Log audit for this run found no 429s, 5xxs, tracebacks, nginx errors, or app exceptions. uWSGI scaled up to all 48 configured workers. The peak of 60 in-flight `/next` requests means some requests were queued briefly while 48 workers were available/busy.

## Interpretation

The realistic answer to "can 150 active users become only 32 concurrent requests?" is yes, if "active" means reading and typing in the interview. Users only occupy a backend worker after clicking submit and while waiting for the next question. With a 25-second average answer time and real `/next` responses mostly around 3-5 seconds, many respondents are active in the conversation but not simultaneously waiting on the backend.

The real run's peak of 32 in-flight requests was not a hard ceiling. The synchronized post-fix run reached 60 in-flight requests because the artificial model delays were longer and the synchronized start made the waves sharper. The system still returned all requests successfully, but that run also shows that in-flight requests can exceed worker count because excess requests queue in front of uWSGI.

CPU percentages are Docker-style percentages where 100% is one full CPU core. On this 3-vCPU VM, 189.710% means about 1.9 cores busy at the peak, and 227.460% means about 2.27 cores busy at the peak. That is noticeable but not full saturation of the 3-vCPU VM. Average CPU was much lower, so CPU does not currently look like the main bottleneck for text interviews.

The current app is now configured for 48 uWSGI workers with a 512 listen backlog. The post-fix test confirmed all 48 workers could be spawned under load. Raising the worker count is not a true unlimited scaling lever: more workers can reduce queueing for I/O-bound requests, but they also consume memory and process overhead, and they do not increase OpenAI rate limits.

## Bottom Line

For the tested 150-user, 3-turn, 25-second-average answer scenario:

- Real OpenAI traffic completed with no HTTP failures or visible rate-limit failures.
- The real run cost about `$3.19` at current pricing.
- A rare local file-session persistence problem was found despite HTTP success.
- The file-session problem was fixed and then validated under a stricter synchronized 150-user run.
- On this VM, the tested load did not CPU-saturate the machine and did not produce timeouts.
- The main remaining launch risk is still synchronized spikes plus OpenAI latency/rate limits, especially if real users submit closer together than the 15-35 second per-question spread used here.
