# asyncmatch

DISCLAIMER: the systems in this page are not real. The examples are for
illustration, and show how to use asyncmatch rather than a complete program.

Python is often used for integration or system testing. A particular challenge
is the inherent asynchrony in the subject-under-test (SUT). Well-designed
systems are likely to use asynchronous messaging protocols for communication
between different subsystems, including third-party ones. For example, consider
an IoT backend, where a REST API query is relayed through a microservice to a
remote device via MQTT. To test this system, the test harness might make an HTTP
query, and using a test double MQTT client sense that the query is translated
into an expected message to the device. This presents a problem when using a
standard Arrange-Act-Assert pattern. 

```python
# This is not a real system!

from api import get_endpoint
from hamcrest import assert_that, has_entry

# Fixture - device is a test double
def test_led_remote_control(device):
    # Arrange
    remote_control = get_endpoint("/remote")

    # Act - POST some JSON to the endpoint
    remote_control.post({"red_led": "on"})

    # Assert - use a device GPIO map
    assert_that(device.gpios, has_entry("gpio3", "high"))

```

This test is likely to fail, because when control returns to the test following
the API query, the request has not yet been translated and reached the device to
be actioned. Put another way, the system is acted upon, but the resulting state
change is not carried into effect immediately.

A naive approach is to add a wait after sending the message. At the very least
this will make the test take the duration of the wait to pass. More likely, it
will be an unreliable test. The common ameliorative, increasing the duration,
simply makes the test take even longer to run, and the sinking feeling that the
tests are cumbersome and unreliable.

In their book, [Growing Object-Oriented Software Guided by
Tests](https://www.amazon.co.uk/Growing-Object-Oriented-Software-Guided-Signature/dp/0321503627),
Steve Freeman and Nat Pryce address this concern in Chapter 27 _Testing
Asynchronous Code_. They outline some techniques to enable tests to follow the
Arrange-Act-Assert pattern for asynchronous systems. In short, the test has
to synchronise with the subject-under-test (SUT). As for any synchronisation
problem, there are two categories of approach: listen for an event
or periodically poll for state.

This project is a simple implementation in Python of those ideas, and is
compatible with [PyHamcrest](https://github.com/hamcrest/PyHamcrest).

## Quick reference

| You want to... | Use | On timeout raises |
|---|---|---|
| Check that the SUT eventually reaches a state you can read | `assert_eventually(probe, duration, poll_delay)` | `AssertionError` |
| Wait for the SUT to be ready before the next step (Arrange, or between phases) | `wait_until(probe, duration, poll_delay)` | `SynchronisationTimeout` |
| Poll a simple yes/no condition | pass a callable as the probe: `assert_eventually(red_led_is_on, ...)` | as above |
| Poll a state and report it well when the test fails | a `Probe` subclass that wraps a Hamcrest matcher | as above |
| Record events the SUT emits (callbacks, MQTT, logs) | `NotificationTrace`, fed by `trace.append(item)` | |
| Check that a matching event eventually arrives | `trace.assert_eventually_contains(matcher, duration)` | `AssertionError` |
| Wait for an event before the next step | `trace.wait_until_contains(matcher, duration)` | `SynchronisationTimeout` |
| Check that events arrive in order | `trace.assert_eventually_contains_in_order([m1, m2], duration)` / `wait_until_contains_in_order` | as above |
| Check what has already arrived, after synchronising | `trace.assert_contains`, `assert_contains_in_order`, `assert_does_not_contain` | `AssertionError` |
| Test in phases that the SUT starts by itself | `trace.wait_until_phase_ends(sentinel, duration)` returns a `Phase` | `SynchronisationTimeout` |
| Test in phases that the test starts | `trace.clear()` before the action that starts the phase | |

Use **polling** (a `Probe`) when you can only read the state of the SUT. Use
**listening** (a `NotificationTrace`) when the SUT, or a test double attached to
it, tells you when something happens, and always when a state may be
overwritten before a poll would see it.

## Guidelines

These are the rules from Freeman & Pryce's chapter, and from their advice on
matchers, that keep asynchronous tests reliable, fast and readable. The
sections that follow explain each one.

1. **Wait for success, and fail by timing out.** Never `time.sleep()` and then
   assert. A fixed sleep makes passing tests slow and failing tests flaky.
2. **Succeed fast.** A passing test should return as soon as the SUT reaches the
   expected state. Keep the polling delay small, sample once when a probe is
   created, and prefer listening when the SUT emits events.
3. **Express what is tested, not how it is tested.** A test should read as the
   state change it checks for, such as `assert_eventually(leds(red("on")))`.
   Hide probes, traces, payload formats, pin numbers and timeouts in helpers.
   See "Express what is tested, not how".
4. **Let the matcher do the describing.** Do not explain a failure with a
   `reason` string. Write matchers and probes whose descriptions say what was
   expected and what was found, in the language of the domain. See "Let the
   matcher do the describing".
5. **Put the timeout values in one place, and find them by experiment.** See
   "Flickering tests".
6. **Distinguish synchronisations from assertions.** Use `wait_until...` when the
   test is only waiting for the SUT to be ready. Use `assert_eventually...` for
   the behaviour under test. A synchronisation that looks redundant often
   prevents a race, so do not delete it.
7. **Make sure the test cannot run ahead of the SUT.** If the expected state is
   also the starting state, the assertion passes before the SUT has done
   anything. See "Runaway tests".
8. **Synchronise on the last effect of an action.** The first visible sign that
   the SUT has acted is not always the end of its work. See "Synchronise on the
   last effect".
9. **Poll in phases, and listen when updates can be lost.** Stimulate, wait for
   the change to be visible, then stimulate again. See "Polling tests run in
   phases" and "Listening for notifications".
10. **Test that something did not happen by making something else happen.** See
    "Testing that an action has no effect".
11. **Take control of hidden timers.** Do not wait for real time to pass. See
    "Hidden timers".
12. **Watch each test fail, and read the message.** See "Watch the test fail".
13. **Keep matchers stateless.** Keep state in the probe or the trace.

## Installation

Install from GitHub using pip:

```bash
# Latest from default branch
pip install "git+https://github.com/dcdunn/asyncmatch.git"

# Pinned to a release tag (recommended)
pip install "git+https://github.com/dcdunn/asyncmatch.git@v0.2.1"

# Pinned to a specific commit
pip install "git+https://github.com/dcdunn/asyncmatch.git@<commit-sha>"
```

For local development from a clone:

```bash
pip install -e .
```

## Polling for changes

Freeman & Pryce create an asynchronous assertion method, that waits for a particular state of the SUT to occur, or else to fail by timing out. There are three concepts that are required: a *Timeout*, a *Probe* and a *Poller*. 

### Timeouts

An asynchronous test fails by timing out - i.e. by failing to enter a required state before some pre-determined time has elapsed. For tests which poll for changes, a *Timeout* encapsulates a _duration_ and a _polling delay_, i.e. the amount of time to wait before the next assessment of the state of the SUT.

### Probes

A *Probe* is an object that probes some state of the SUT. The *Probe* is an abstract class that is written to support the use of Hamcrest matchers to understand if the SUT has satisfied some desired condition. Following Freeman & Pryce, the *Probe* separates the concerns of sampling the system state and of checking if it satisfies some condition. This also allows the test to report the last sampled state of the system if the test fails.

What to probe varies according to the context, and might take several iterations to get a good abstraction. For example to check if a particular USB device is connected to a laptop, one might probe the entire USB tree (using lsusb on Linux or WMI on Windows), creating some kind of representation such as a dictionary. Then, a Hamcrest matcher can be used to check that representation. 

```python
from asyncmatch import Probe
from hamcrest.core.matcher import Matcher

class UsbDeviceProbe(Probe):
    def __init__(self, matcher: Matcher):
        self.connected_devices = []
        self.matcher = matcher
        self.sample()
    def sample(self):
        # Use OS APIs to create a dict representing the USB tree
        self.connected_devices = ...
    def is_satisfied(self) -> bool:
        return self.matcher.matches(self.connected_devices)
    def describe_to(self, description):
        description.append_description_of(self.matcher)
    def describe_mismatch(self, description):
        self.matcher.describe_mismatch(self.connected_devices, description)
```
Depending on how the device tree is represented, standard Hamcrest matchers can
be used to check for, say, a particular Vendor ID and product ID:
```python
probe = UsbDeviceProbe(has_item(has_entries(
  vendor_id=VID,
  product_id=PID
)))
```
This example also shows how you can lean on the descriptions provided by
Hamcrest matchers to generate useful diagnostic information when a test fails.  

Tip: a *Probe* can sample in its *__init__* method. This gives the test an
opportunity to pass quickly, before the first polling delay. Create the probe at
the point of the assertion, after the action, so that this first sample is of
the state you are waiting for.

Sometimes a callable object that returns a boolean value is sufficient to define
a *Probe*. asyncmatch also provides a *CallableProbe*, a helper class that
wraps such a callable.

```python
from asyncmatch.callable_probe import CallableProbe

def red_led_is_on():
    ...  # whatever it takes, return True or False

probe = CallableProbe(red_led_is_on)

```

Attempting to initialise with an object that is not callable will result in a
*TypeError* being raised. Apart from a class, any callable is acceptable. The
name of the function is used in the *CallableProbe*'s descriptions, so choose a
name that reads well in a failure message, such as *red_led_is_on*. A callable
cannot report what it found, so prefer a *Probe* with a matcher when the
failure message matters. You should not need to create a *CallableProbe*
directly. The *assert_eventually* and *wait_until* functions do that
automatically if you provide a callable as the first parameter.

### Poller
The *Poller* checks a *Probe* until it is satisfied or it times out. The _check_
method blocks until the test has passed or else raises a *PollerTimeout* error.

```python

probe = UsbDeviceProbe(has_item(has_entries(
  vendor_id=VID,
  product_id=PID
)))

poller = Poller(Timeout(5.0, 0.1))

try:
    poller.check(probe)
except PollerTimeout:
    ...  # the probe was not satisfied in time

```

## *assert_eventually* and *wait_until*

You should not use the poller directly, but instead use the *assert_eventually*
function call which takes care of polling and reporting errors back to the test
framework. In the *assert_eventually* method *PollerTimeout* is handled, and
converted to an *AssertionError*, which pytest and other frameworks treat as
test failures. The diagnostic message in the error is generated using the
Hamcrest compatible describer methods.

Freeman & Pryce recommend distinguishing synchronisations from assertions. In
the _Arrange_ section of a test, we need to put the system into a known initial
state, and this may involve asynchronous operations. This library also provides
a *wait_until* method. Operationally, it is the same as *assert_eventually*
except that when the underlying poller times out, it raises a
*SynchronisationTimeout* to distinguish it from an assertion.

In the example given earlier, to synchronise the test with the SUT, we need to
write a *Probe* that reads the state of the device's LEDs, probably a subset of
the GPIO pins.

```python
# GpioProbe.py
from asyncmatch import Probe
from hamcrest.core.matcher import Matcher

class GpioProbe(Probe):
    def __init__(self, matcher: Matcher):
        self.current = None
        self.matcher = matcher
        # Sample immediately
        self.sample()

    def sample(self):
        # However this probe is carried out, e.g. using a test
        # board that samples the GPIO pins. For this example
        # self.current is a dictionary containing the GPIO states:
        # { "gpio1": "high", "gpio2": "low", ...}
        self.current = ...
    
    def is_satisfied(self):
        return self.matcher.matches(self.current)

    def describe_to(self, description):
        description.append_description_of(self.matcher)

    def describe_mismatch(self, description):
        self.matcher.describe_mismatch(self.current, description)
```

A probe must implement *describe_to* and *describe_mismatch*. They build the
failure message when the probe is never satisfied. Without them, a failing test
raises *NotImplementedError* instead of reporting what went wrong.

Keep the two halves of a probe apart. *sample* is the only method that reads the
SUT, and it stores what it read. *is_satisfied* and *describe_mismatch* only look
at that stored sample. Then the failure message reports exactly the state that
failed the check.

Then the test might be similar to this:

```python
# This is not a real system!

from api import get_endpoint
from device import Device
from probes import GpioProbe
from asyncmatch import assert_eventually
from hamcrest import has_entry

def test_led_remote_control(device):
    remote_control = get_endpoint("/remote")
    remote_control.post({"red_led": "on"})
    assert_eventually(GpioProbe(has_entry("gpio3", "high")), 10.0, 0.1, "The red LED is not on")
```

This test is cluttered up in several ways. The timeout parameters are a detail
of the test that do not need to be visible at this level of abstraction. The
duration and polling delay will vary according to a specific context.  Freeman &
Pryce note that establishing what these parameters are for a given context is an
empirical exercise. It is important that a test _passes_ as quickly as possible,
so make the polling delay small. However, the duration needs to be long enough
that it covers the acceptable envelope of normal operating times, i.e. you will
need to determine how long it is acceptable to wait before concluding that the
state change is not going to happen.

Cases where I have used this approach include:
 * Checking that a USB command sent to a docking station results in an image on a screen. The
   test harness sends the command, and a frame grabber driver senses what pixels
   are displayed. This operation might take of the order of tenths of a second,
   so timeout duration of say a few seconds, with a polling interval of 0.1s
   gives responsive and reliable tests.
 * Checking that a POST to a REST API is relayed through an IoT backend and translated into a protocol
   sent over MQTT to a device. The SUT is the backend, including the API
   gateway. An MQTT client driver in the test harness receives the messages
   sent. The message is usually relayed in fractions of a second, so a good
   duration is maybe a second or two, and a polling delay of 0.01s gives fast
   tests.
 * At a test suite setup, the SUT is a Windows device driver. The setup should make
  a clean installation of the driver, and wait for the device to enumerate in
  Windows' device tree. While this usually take a few tens of seconds, it can
  take up to two minutes. In this case a duration of three minutes and a polling
  interval of a second is appropriate.

Freeman & Pryce recommend to establish the timeout parameters for the SUT, and
express them in one place. For library code such as in this project, that
approach is not possible. However, you can achieve the same effect like this:

```python
# This is not a real system!

from api import get_endpoint
from device import Device
from probes import GpioProbe
import asyncmatch

DURATION_SECS = 5.0
POLL_DELAY_SECS = 0.1

def assert_eventually(probe, reason=""):
    asyncmatch.assert_eventually(probe, DURATION_SECS, POLL_DELAY_SECS, reason)

def wait_until(probe, reason=""):
    asyncmatch.wait_until(probe, DURATION_SECS, POLL_DELAY_SECS, reason)

def test_led_remote_control(device):
    remote_control = get_endpoint("/remote")
    remote_control.post({"red_led": "on"})
    assert_eventually(GpioProbe(has_entry("gpio3", "high")), "The red LED is not on")
```

Put these wrappers in one helper module that all the tests import, so that
there is exactly one place to change the timeouts.

### Express what is tested, not how

This test is still cluttered with details of how the test is carried out, and
exposes to the reader that there is a probe that uses a dictionary to record the
state of the GPIOs.  Tests provide the most value when they document clearly and
concisely the system state transition that they are checking for. A good test
should express _what_ is being tested without exposing the details of _how_ the test
is carried out - good tests are declarative rather than imperative.

The *how* includes:

* the mechanism: a probe, a poller or a trace;
* the representation: dictionaries, payload formats, pin numbers, register
  values;
* the timing: durations and polling delays.

The *what* is the state change in the language of the domain: the red LED is
on, the device has enumerated, the order has been accepted. 

It can be useful to write the assertion _first_, in a way that declares what the
system state is. Then, implement the *Probe* and some helper functions to
preserve the readability of the assertion. For example, this is easier to read:

```python
    assert_eventually(leds(red("on")))
```

This is easily implemented, perhaps as follows.

```python
# GpioProbe.py

# ....

def _led(gpio: str, state: str) -> Matcher:
    if state == "on":
        state = "high"
    elif state == "off":
        state = "low"
    else:
        raise ValueError(f"unknown LED state {state}")
    return has_entry(gpio, state)

def red(state: str) -> Matcher:
    return _led("gpio3", state)

def green(state: str) -> Matcher:
    return _led("gpio4", state)

def leds(matcher: Matcher) -> GpioProbe:
    return GpioProbe(matcher)

```

Careful design can unlock the higher order grammar of Hamcrest. For example, we can now write an assertion:

```python
    assert_eventually(leds(all_of(
        red("on"),
        green("off")
    )))
```

### Let the matcher do the describing

The example tests above pass a *reason*, such as "The red LED is not on". Leave
it out. A reason is a second description of the check, written by hand, and it
can drift away from what the check really does. The probe and its matcher
already know what was expected and what was found. When they describe it well,
the failure message needs nothing else.

With *red* built from *has_entry*, as above, the message describes the
representation, not the domain:

```
Expected: a dictionary containing ['gpio3': 'high']
     but: value for 'gpio3' was 'low'
```

A reader has to know that gpio3 is the red LED and that high means on. Give
*red* and *green* a matcher of their own, whose descriptions use the language
of the test. Follow Hamcrest's convention: the two descriptions should complete
the sentence "Expected *description* but *mismatch description*".

```python
# GpioProbe.py
from hamcrest.core.base_matcher import BaseMatcher

_PINS = {"red": "gpio3", "green": "gpio4"}
_LEVELS = {"on": "high", "off": "low"}
_STATES = {"high": "on", "low": "off"}

class LedMatcher(BaseMatcher):
    def __init__(self, colour: str, state: str):
        self.colour = colour
        self.state = state

    def _matches(self, gpios) -> bool:
        return gpios.get(_PINS[self.colour]) == _LEVELS[self.state]

    def describe_to(self, description):
        description.append_text(f"{self.colour} LED {self.state}")

    def describe_mismatch(self, gpios, description):
        level = gpios.get(_PINS[self.colour])
        description.append_text(f"{self.colour} LED was {_STATES.get(level, level)}")

def red(state: str) -> LedMatcher:
    return LedMatcher("red", state)

def green(state: str) -> LedMatcher:
    return LedMatcher("green", state)
```

Now the same failure reads:

```
Expected: red LED on
     but: red LED was off
```

The matcher still combines with the rest of Hamcrest. A failure of
*leds(all_of(red("on"), green("off")))* reports:

```
Expected: (red LED on and green LED off)
     but: red LED on red LED was off
```

A matcher like this must be stateless, because Hamcrest may call it any number
of times. Keep state, such as the last sample, in the probe or the trace.

Use a *reason* only for something that no matcher can know, such as which
iteration of a loop failed.

### Callables

Finally, you can provide a callable as the argument to *assert_eventually* or *wait_until*:

```python
def red_led_is_on():
    ...  # whatever it takes, return True or False

assert_eventually(red_led_is_on)

```
## Listening for notifications

Polling samples the state of the SUT. Freeman & Pryce describe a second way to
synchronise: *listening*. The test records the events the SUT emits and waits
for one that matches. Listening can do two things that polling cannot:

* **No lost updates.** If a state is overwritten between two samples (a pulse,
  a blink, a transient error), a poller never sees it. A trace keeps every
  event.
* **No poll delay.** The test thread blocks until an event is appended, then
  wakes up at once. It does not wait for the next sample.

Use polling when you can only read the state of the SUT. Use listening when the
SUT, or a test double attached to it, tells you when something happens, for
example through an MQTT subscription or a callback.

A *NotificationTrace* records the events. Call *append* from the SUT's callback,
which may run on any thread. Then make the assertion with
*assert_eventually_contains*, or synchronise with *wait_until_contains*. These
work like *assert_eventually* and *wait_until*: on timeout the first raises an
*AssertionError* and the second raises a *SynchronisationTimeout*. Pass any
Hamcrest matcher that fits the type of the items, and a duration:

```python
trace.assert_eventually_contains(has_entry("red_led", "blink"), 5.0)
```

The search covers every item appended since the trace was created. So an event
is found even if it arrived before the test started waiting, or if other events
followed it. No polling delay is needed.

### Wrap the trace in a domain helper

The call above is full of *how*: a trace, a payload format and a duration. In
the polling section, a local *assert_eventually* hides the duration. For a
trace, go one step further and hide the trace itself behind a *domain helper*.
That is a small class that knows how the SUT reports events, and that offers
methods named after what happens in the domain. The helper owns:

* **the trace, and how it is connected to the SUT.** Tests never call
  *append* and never see the trace.
* **the payload format.** Matchers such as *red("blink")* hide that the
  payload is a dictionary keyed by *red_led*.
* **the duration.** Freeman & Pryce advise putting timeout values in one place.
  For listening tests, the helper is that place. Find the right value by
  experiment, as for polling, and change it in one line.
* **the difference between asserting and synchronising.** Give each its own
  name, so a reader can tell which calls are checks and which only wait for
  the SUT to be ready.

```python
# led_events.py - this is not a real system!

from asyncmatch import NotificationTrace
from hamcrest import has_entry
from hamcrest.core.matcher import Matcher

_DURATION_SECS = 5.0

def red(state: str) -> Matcher:
    return has_entry("red_led", state)

def green(state: str) -> Matcher:
    return has_entry("green_led", state)

class LedEvents:
    def __init__(self, mqtt_client):
        self._trace = NotificationTrace()
        mqtt_client.on_message = lambda msg: self._trace.append(msg.payload)

    def have_shown(self, matcher: Matcher) -> None:
        """Assert: the LEDs eventually showed this."""
        self._trace.assert_eventually_contains(matcher, _DURATION_SECS)

    def wait_until_shown(self, matcher: Matcher) -> None:
        """Synchronise: wait for the LEDs to show this before going on."""
        self._trace.wait_until_contains(matcher, _DURATION_SECS)
```

The test then says only what should happen:

```python
def test_button_press_blinks_red_led(device, led_events):
    device.press_button()
    led_events.have_shown(red("blink"))
```

Because the matchers describe themselves, you rarely need a *reason*. When the
trace times out, the failure message gives the expected notification and
everything the trace received:

```
Expected: a notification matching a dictionary containing ['red_led': 'blink']
     but: received [<{'red_led': 'on'}>, <{'red_led': 'off'}>]
```

The following sections add methods to the same helper.

### Notifications in order

*assert_eventually_contains* searches the whole history on every call. So it
cannot tell "blink, then off" from "off, then blink". To check order, use
*assert_eventually_contains_in_order*, or *wait_until_contains_in_order* to
synchronise. Each takes a list of matchers. Each matcher must match a later
notification than the one before it. Other notifications may arrive in between.
The duration covers the whole sequence. Add a method to the helper, so the
test still names only the states:

```python
# In LedEvents
    def have_shown_in_order(self, *matchers: Matcher) -> None:
        """Assert: the LEDs eventually showed these, in this order."""
        self._trace.assert_eventually_contains_in_order(matchers, _DURATION_SECS)
```

```python
def test_button_press_blinks_then_turns_off_red_led(device, led_events):
    device.press_button()
    led_events.have_shown_in_order(red("blink"), red("off"))
```

If the sequence does not arrive in time, the message says how far it got.
It lists the notifications that matched, then what was received after the last
match:

```
Expected: notifications matching a dictionary containing ['red_led': 'blink'] then a dictionary containing ['red_led': 'off'], in order
     but: matched <{'red_led': 'blink'}>, then received [<{'red_led': 'on'}>]
```

Each call searches from the start of the trace, so calls do not affect each
other.

### Checking what has already arrived

A common pattern is to wait for the SUT to say it has finished, and then check
what it reported along the way. The waiting is a synchronisation. The checks
that follow do not need to wait, because the notifications they look at have
already arrived. *assert_contains*, *assert_contains_in_order* and
*assert_does_not_contain* check the trace once, with no duration.

Put them in the helper next to the waiting methods. Give them names that show
they look at what has already happened:

```python
# In LedEvents
    def wait_until_ready(self) -> None:
        """Synchronise: the device has finished starting up."""
        self._trace.wait_until_contains(has_entry("status", "ready"), _DURATION_SECS)

    def showed(self, matcher: Matcher) -> None:
        """Check, without waiting: the LEDs have already shown this."""
        self._trace.assert_contains(matcher)

    def showed_in_order(self, *matchers: Matcher) -> None:
        """Check, without waiting: the LEDs have already shown these, in order."""
        self._trace.assert_contains_in_order(matchers)

    def never_showed(self, matcher: Matcher) -> None:
        """Check, without waiting: the LEDs have not shown this."""
        self._trace.assert_does_not_contain(matcher)
```

```python
def test_start_up_lights_red_then_green(device, led_events):
    device.power_on()
    led_events.wait_until_ready()
    led_events.showed_in_order(red("on"), green("on"))
```

If the start-up sequence is wrong, the test fails as soon as the device is
ready. It does not wait for the full duration.

**These checks are only sound after a synchronisation.** On their own they test
an asynchronous system synchronously, and the result depends on timing. Before
a check, wait for a notification that the SUT sends *no earlier* than the ones
you check: the same notification, or one that comes after them. That assumes
the SUT sends its notifications in order, so make sure another test covers
that.

#### Testing that an action has no effect

*assert_does_not_contain* is how a listening test shows that something did
*not* happen. Freeman & Pryce describe the technique in "Testing That an
Action Has No Effect". You cannot wait for something not to happen. Instead,
trigger a second action that the SUT will process *after* the first and
whose effect you can detect. Synchronise on that effect, then check that the
first action left no trace:

```python
def test_ignores_commands_for_other_devices(remote, led_events):
    remote.send(OTHER_DEVICE, {"red_led": "on"})   # should be ignored
    remote.send(THIS_DEVICE, {"green_led": "on"})  # processed after it
    led_events.wait_until_shown(green("on"))
    led_events.never_showed(red("on"))
```

If the ignored command did have an effect, the message names the notification
that should not be there:

```
Expected: no notification matching a dictionary containing ['red_led': 'on']
     but: received [<{'red_led': 'on'}>]
```

As Freeman & Pryce note, this test relies on the SUT processing commands in
the order they were sent. If the second command could overtake the first, the
test could pass before the first one had any effect.

### Testing in phases

Some tests run in phases. Phase 1 ends with a "done" notification, the test
checks what happened in phase 1, then phase 2 runs, and so on. Each phase's
checks should look only at that phase's notifications. A trace offers two
ways to do this. Which one to use depends on **who starts the next phase**.

| Who starts the next phase? | Use | Why |
|---|---|---|
| The SUT. It moves on by itself, perhaps straight away. | *wait_until_phase_ends* | The phase boundary is set by the SUT's own "done" notification, so nothing is lost however quickly the SUT moves on. |
| The test. Nothing happens until the test acts. | *clear* | Simpler. Safe because the SUT is quiet when the test clears the trace. |

If you are not sure, use *wait_until_phase_ends*. It is correct in both cases.

#### The SUT starts each phase: *wait_until_phase_ends*

*wait_until_phase_ends(sentinel, duration)* waits for the notification that
ends the current phase (the *sentinel*). It returns a *Phase*: a snapshot of
every notification from the end of the previous phase up to and including the
sentinel. A *Phase* has the same checks as the trace: *assert_contains*,
*assert_contains_in_order* and *assert_does_not_contain*. None of them wait.

For example, suppose a device's self-test checks its lamps and then its
network, one stage straight after the other. It reports the end of each stage:

```python
# In led_events.py
from asyncmatch import Phase

# In LedEvents
    def wait_until_stage_done(self, stage: str) -> Phase:
        """Synchronise: a self-test stage has finished. Returns its notifications."""
        return self._trace.wait_until_phase_ends(has_entry("self_test", f"{stage} done"), _DURATION_SECS)
```

```python
def test_self_test_checks_lamps_then_network(device, led_events):
    device.start_self_test()

    lamps = led_events.wait_until_stage_done("lamps")
    lamps.assert_contains_in_order([red("on"), green("on")])
    lamps.assert_does_not_contain(red("blink"))

    network = led_events.wait_until_stage_done("network")
    network.assert_contains(green("blink"))
```

How it behaves:

* **Nothing is lost.** Notifications that arrive after a sentinel stay in the
  trace for the next phase. The network stage may start, or even finish,
  before the test has looked at the lamps stage. Its notifications are still
  there for the second *wait_until_stage_done*.
* **Each search starts after the previous sentinel.** Phases that end with the
  same notification, such as a plain "done", are still told apart.
* **The checks on a Phase are always safe.** The warning in "Checking what has
  already arrived" does not apply here. A *Phase* only exists once its
  sentinel has arrived, so its checks cannot run too early.
* **Failure messages list only that phase's notifications.** They are easier
  to read than the whole history:

  ```
  Expected: a notification matching a dictionary containing ['green_led': 'blink']
       but: received [<{'green_led': 'on'}>, <{'self_test': 'network done'}>]
  ```
* **If a phase never ends**, *wait_until_phase_ends* raises a
  *SynchronisationTimeout* that lists the notifications received since the
  previous phase ended.

The methods that search the whole history, such as *assert_eventually_contains*
and *assert_contains*, ignore phases. They still see every notification.

#### The test starts each phase: *clear*

*clear()* discards every notification recorded so far. Use it when each phase
starts only because the test does something. Call *clear* **before** that
action:

```python
# In LedEvents
    def forget_earlier_events(self) -> None:
        """Start afresh: only notifications from now on count."""
        self._trace.clear()
```

```python
def test_every_button_press_blinks_the_red_led(device, led_events):
    for _ in range(3):
        led_events.forget_earlier_events()
        device.press_button()
        led_events.have_shown(red("blink"))
```

Without *clear*, the second and third *have_shown* would pass immediately on
the first press's blink, without testing anything.

Two rules make *clear* safe:

* **Clear before the action that starts the phase, never after it.** A
  notification that arrives between the action and *clear* is lost.
* **Clear only when the SUT is quiet.** The previous phase must be over, which
  you know because the test has already synchronised on it. If the SUT could
  already be sending the next phase's notifications, *clear* throws them away.
  The test then fails, or passes, depending on timing. Use
  *wait_until_phase_ends* instead.

### Notifications immediately in sequence

*assert_eventually_contains_in_order* allows anything in between. Sometimes
the test needs one notification to come *immediately* after another. For
example, the LED must go from blink straight to off, with no other state in
between.

To check that, record *transitions*. Each time a notification arrives, append
the pair (previous notification, this notification) to a second trace. "Blink
immediately followed by off" is then a single item in that trace. Hamcrest's
*contains_exactly* matches it.

This is the kind of detail a domain helper is for. The second trace, the lock
and the pairing all stay inside *LedEvents*. Only the connection to the SUT
changes, and one method is added:

```python
# led_events.py - changes to LedEvents
from threading import Lock
from hamcrest import contains_exactly

class LedEvents:
    def __init__(self, mqtt_client):
        self._trace = NotificationTrace()
        self._transitions = NotificationTrace()
        self._lock = Lock()
        self._previous = None
        mqtt_client.on_message = lambda msg: self._record(msg.payload)

    def _record(self, payload) -> None:
        self._trace.append(payload)
        with self._lock:
            if self._previous is not None:
                self._transitions.append((self._previous, payload))
            self._previous = payload

    # The other methods are unchanged

    def have_shown_consecutively(self, first: Matcher, then: Matcher) -> None:
        """Assert: the LEDs eventually showed first, then immediately then."""
        self._transitions.assert_eventually_contains(contains_exactly(first, then), _DURATION_SECS)
```

```python
def test_red_led_stops_blinking_by_turning_off(device, led_events):
    device.press_button()
    led_events.have_shown_consecutively(red("blink"), red("off"))
```

The transitions trace works like any other trace. It searches every transition
since it was created, and it wakes as soon as the pair arrives. If the pair
never arrives, the message lists every transition received:

```
Expected: a notification matching a sequence containing [a dictionary containing ['red_led': 'on'], a dictionary containing ['red_led': 'off']]
     but: received [<({'red_led': 'on'}, {'red_led': 'blink'})>, <({'red_led': 'blink'}, {'red_led': 'off'})>]
```

Things to keep in mind:

* **Protect the previous notification.** The trace's own lock only covers
  *append*. Pairing a notification with the one before it is a separate
  read-then-write. The lock in *_record* keeps the pairs correct if the SUT
  calls back from more than one thread. If you know the callbacks always come
  from one thread, as with most MQTT clients, you can drop it.
* **"Immediately" means in the order *append* was called.** That matches what
  the SUT did only if its callbacks arrive in the order it emitted them. Check
  this before you rely on it. As with the "has no effect" technique, the test
  makes an assumption about how the system is built. Make sure another test
  covers that assumption.
* **Keep the pairs out of the test.** The test should say what happened, as in
  *have_shown_consecutively(red("blink"), red("off"))*, not how the helper
  records it.

## Avoiding unreliable tests

An asynchronous test can be wrong in two ways. It can fail when the SUT works,
which makes it a *flickering* test. Or it can pass when the SUT is broken,
because it checked before the SUT had done anything. The second is worse,
because nobody looks at a passing test. The techniques in this section, all
from Freeman & Pryce, prevent both.

### Runaway tests

Be careful when a test asserts that the SUT returns to a previous state. The
red LED starts off, so this test can pass before the SUT has processed either
command:

```python
def test_red_led_on_then_off(remote):
    remote.send(red_led="on")
    remote.send(red_led="off")
    assert_eventually(leds(red("off")))   # passes at once, testing nothing
```

The test has run ahead of the SUT. Make it wait for the intermediate state
before it sends the next command:

```python
def test_red_led_on_then_off(remote):
    remote.send(red_led="on")
    wait_until(leds(red("on")))
    remote.send(red_led="off")
    assert_eventually(leds(red("off")))
```

With listening, *assert_eventually_contains_in_order* checks the
intermediate state for you: `led_events.have_shown_in_order(red("on"),
red("off"))`. When a test repeats an action, see *clear* in "Testing in
phases".

The same trap catches a probe that is created before the action. It samples
the old state when it is created, and if the old state already matches, the
assertion passes at once. Create probes at the point of the assertion.

### Synchronise on the last effect

An action can have several effects, and the test sees them one at a time. If
the test synchronises on the first effect and moves on, the SUT may not have
finished the rest. The next step then races the SUT.

For example, suppose that when an LED is switched on, the SUT notifies its
listeners and then starts an auto-off timer. A test that waits for the
notification and then fires the timer can fire it before the timer exists.
The test fails rarely, and only on a busy machine:

```python
def test_led_turns_itself_off(remote, led_events, scheduler):
    remote.send(red_led="on")
    led_events.wait_until_shown(red("on"))   # the timer may not be started yet
    scheduler.run_due_actions(after=AUTO_OFF_SECS)
    led_events.have_shown(red("off"))
```

Synchronise on the effect that comes last, here the timer being started:

```python
    led_events.wait_until_shown(red("on"))
    wait_until(scheduler.has_pending_action)
    scheduler.run_due_actions(after=AUTO_OFF_SECS)
```

Read the SUT's code, or its documentation, to find out what an action does
after its first visible effect. If there is nothing to observe, that is a
reason to add something: a notification, a status, or a test seam.

### Polling tests run in phases

A poller only sees the state at the moment it samples. If the state changes
twice between samples, the poller never sees the first change. This is a
*lost update*. So a polling test must run in phases. Each phase has one
stimulus, then waits until its effect is visible, before the next phase starts.
Do not send the next stimulus until the previous one has been seen to work.

If the SUT can change state faster than the test can sample it, for example a
20 ms blink, polling cannot test it reliably. Listen for notifications instead.
A *NotificationTrace* keeps every event, so nothing is lost.

### Testing that an action has no effect

You cannot wait for something not to happen. Waiting for a fixed time is slow,
and a check straight after the action passes before the SUT has even received
it. Instead, follow the action with a second one that the SUT processes after
the first and whose effect you can detect. Wait for that effect, then check
that the first action changed nothing.

With polling:

```python
def test_ignores_commands_for_other_devices(remote, device):
    remote.send(OTHER_DEVICE, red_led="on")    # should be ignored
    remote.send(THIS_DEVICE, green_led="on")   # processed after it
    wait_until(leds(green("on")))
    assert_that(device.gpios, red("off"))
```

The final check is a plain *assert_that*, because the SUT has already finished
with the first command. With listening, use *assert_does_not_contain*, as shown
in "Testing that an action has no effect" under "Checking what has already
arrived".

This only works if the SUT processes the two actions in order. Say so in a
comment, and make sure that another test checks the order. Otherwise a change
to the SUT could make this test pass without testing anything.

### Hidden timers

Some systems start their own activity with timers: an LED that switches itself
off after 30 seconds, a nightly report, a retry after a back-off. Waiting for
real time to pass makes the tests slow, and a timer that fires in the middle of
a test makes it unpredictable.

Freeman & Pryce's answer is to take the scheduling out of the SUT, so that the
test can drive it. Give the SUT a scheduler, or a clock, as a dependency. In
tests, pass a fake that runs actions only when the test tells it to:

```python
import threading

class FakeScheduler:
    """Stands in for threading.Timer. Actions run only when the test advances time."""

    def __init__(self):
        self._lock = threading.Lock()
        self._now = 0.0
        self._pending = []                       # (due time, action)

    def schedule(self, delay_secs, action):      # the SUT calls this
        with self._lock:
            self._pending.append((self._now + delay_secs, action))

    def has_pending_action(self) -> bool:        # for wait_until
        with self._lock:
            return bool(self._pending)

    def run_due_actions(self, after: float):     # the test calls this
        with self._lock:
            self._now += after
            due = sorted((p for p in self._pending if p[0] <= self._now), key=lambda p: p[0])
            self._pending = [p for p in self._pending if p[0] > self._now]
        for _, action in due:
            action()
```

The test then runs at full speed, and can check timing exactly: advance to just
before the deadline and check that nothing has happened, then advance past it.
See "Synchronise on the last effect" for how to wait until the timer exists.

If the SUT does not let you replace its scheduler, that is design feedback:
add the seam. Keep the real scheduler simple, test it on its own, and run a few
slower end-to-end tests with it in place.

### Flickering tests

A test flickers when its timeout is too close to the time the SUT normally
takes, or when it does not synchronise properly with the SUT. Do not live with
flickering tests. They teach the team to ignore failures, and so they hide real
intermittent defects in the SUT.

* Measure how long the SUT normally takes, including on the slowest machine
  that runs the tests, and set the duration well above that. A long duration
  costs nothing when the test passes. It only delays the report of a failure.
* Keep the polling delay small, so passing tests finish quickly. Make it
  larger only if fast polling loads the SUT.
* Set both values in one place. See the wrappers in "*assert_eventually* and
  *wait_until*" and the domain helper in "Listening for notifications".
* If a test still flickers, look for a missing synchronisation before you
  increase the timeout. See "Runaway tests", "Synchronise on the last effect"
  and "Polling tests run in phases".

### Watch the test fail

A passing asynchronous test does not prove much on its own. It may have checked
before the SUT did anything. Before you rely on a test, make it fail: break the
SUT, or change the expected value, and run it again. Check two things:

* **It fails.** If it still passes, it is not testing what you think. Runaway
  tests and tests that an action has no effect are the most likely to pass
  without testing anything.
* **The message explains the failure.** Someone who reads only the message
  should understand what was expected and what happened. If they would not,
  improve the matcher's descriptions. See "Let the matcher do the describing".
