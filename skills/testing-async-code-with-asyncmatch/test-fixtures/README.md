# Test fixtures for the skill

Fake asynchronous systems used to test the skill. These are not tests of
asyncmatch.

To test the skill, ask subagents to write pytest tests for a fixture: some with
the skill and some without (the control). Then compare the results.

- *simple_sut.py*: a backend relays LED commands to a device after a random
  50-300 ms delay. It tests the basics: no sleeps, timeouts in one place,
  runaway tests, and testing that an action has no effect.
- *hard_sut.py*: adds a 20 ms blink that polling misses, LED change callbacks to
  listen to, and a hidden 30 s auto-off timer that can be replaced through
  *Backend(schedule=...)*. The SUT notifies listeners *before* it starts the
  timer. A test that waits for the "on" notification and then advances a fake
  clock has a race. To expose the race, add `time.sleep(0.05)` between
  `self._device._set(led, state)` and the `if state == "on":` line in
  `Backend._apply`, then run the generated tests again.

The task given to each subagent was:

1. Posting {"red": "on"} turns the red LED on.
2. Red on, then red off, leaves the red LED off.
3. A command for a different device_id is ignored.
4. Posting {"red": "blink"} makes the red LED blink.
5. An LED that is switched on turns itself off automatically after the
   auto-off period.

Score each result on these points: waiting for the last effect, runaway tests,
the ignored-command technique, listening for the blink, the fake scheduler,
domain language, matchers that write the failure messages, and whether the
agent watched each test fail.
