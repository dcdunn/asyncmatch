---
name: testing-async-code-with-asyncmatch
description: Use when writing or fixing Python tests (pytest, PyHamcrest) where the system under test changes state after the call returns - background threads, queues, MQTT/REST relays, callbacks, devices, drivers, timers - or when such tests use time.sleep, flicker, are slow, or pass suspiciously fast.
---

# Testing Asynchronous Code with asyncmatch

An assert made straight after an asynchronous action is a race. **Wait for success, and fail by timing out** (Freeman & Pryce, *GOOS* ch. 27). The asyncmatch library does this, and works with PyHamcrest.

## 1. Read the installed README first

The asyncmatch README is the reference. It has a quick-reference table, guidelines and worked examples. It is packaged with the code, so read the copy that matches the installed version:

```bash
python -c "import importlib.metadata as m; d = m.distribution('asyncmatch'); print(d.version); print(d.read_text('METADATA'))"
```

- **Not installed:** run `pip install asyncmatch`.
- **Older than 0.2.1:** the README lacks the "Guidelines" and "Avoiding unreliable tests" sections. Read https://github.com/dcdunn/asyncmatch/blob/main/README.md and suggest an upgrade.

## 2. Choose polling or listening

| The SUT... | Use |
|---|---|
| only lets you read its state | polling: a `Probe` with `assert_eventually` / `wait_until` |
| emits events (callback, MQTT, log), or a state may be overwritten before a poll sees it | listening: `NotificationTrace` |

## 3. Check every test against this list before you finish

- No `time.sleep()` before an assert. Timeouts are set once, in a helper module.
- Tests read as state changes in the language of the domain. Probes, traces, payload formats and timeouts are hidden in helpers.
- There are no `reason` strings. Matchers describe the expected and actual state in the language of the domain.
- `wait_until...` is used to synchronise, and `assert_eventually...` to check.
- If the expected state is also the starting state, the test first waits for the intermediate state ("Runaway tests").
- Before each next step, the test waits for the **last** effect of the previous action, not just the first one it can see. Read the SUT's code to find out what it does after its first visible effect ("Synchronise on the last effect").
- A test that something did not happen waits for a later action it can detect, and says in a comment that it relies on the order of processing.
- The SUT's own timers are driven by a fake scheduler, not by real time ("Hidden timers").
- **You have watched each test fail.** Break the SUT or the expected value, run the test, and read the message.

## 4. Report

For each test, report how you made it fail and the failure message it gave. If a message would not explain the failure to someone who has only the message, improve the matcher's descriptions and run it again.
