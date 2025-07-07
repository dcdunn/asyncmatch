# asyncmatch

DISCLAIMER: none of the code in this page is real, but is for illustrative purposes.
It may not be syntatically correct.

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
from device import Device
from matchers import pin_high

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
will be be an unreliable test. The common ameliorative, increasing the duration,
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

This project is a simple implementation in Python of those ideas, and is compatible with [PyHamcrest](https://github.com/hamcrest/PyHamcrest).

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
        # Use OS APIs to create a dict repreenting the USB tree
        self.connected_devices = ...
    def is_satified(self) -> bool:
        return self.matcher.matches(self.connected_devices)
    def describe_to(self, description):
        description.append_description_of(self.matcher)
    def describe_mismatch(self, description):
        self.matcher.describe_mismatch(self.connected_devices, description)
```
Depending on how the device tree is represented, standard Hamcrest matchers can be used to check for, say, a particular Vendor ID and product ID:
```python
probe = UsbDeviceProbe(has_item(has_entries(
  "vendor_id": VID,
  "product_id": PID
)))
```
This example also shows how you can lean on the descriptions provided by Hamcrest matchers to generate useful diagnostic information when a test fails.  

Tip: a *Probe* can can sample in its initialise function. This gives the test an opportunity to pass quickly, before the first polling delay.

### Poller
The *Poller* checks a *Probe* until it is satisfied or it times out. The _check_ method blocks until the test has passed or else raises a *PollerTimeout* error.

```python

probe = UsbDeviceProbe(has_item(has_entries(
  "vendor_id": VID,
  "product_id": PID
)))

poller = Poller(Timeout(5.0, 0.1))

try:
    poller.check(probe)
except PollerTimeout:
    # did not satify the probe in time

```

You should not use the poller directly, but instead use the *assert_eventually*
function call which takes care of polling and reporting errors back to the test
framework. In the *assert_eventually* method *PollerTimeout* is handled, and
converted to an *AssertionError*, which pytest and other frameworks treat as
test failures. The diagnostic message in the error is generated using the
Hamcrest compatible describiber methods.

### Usage tips

In the example given early, we need to synchronise the test with the SUT. We
need to write a *Probe* that reads the state of the device's LEDs, probably a
subset of the GPIO pins.

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
```
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

. Cases where I have used this approach include:
 * Checking that a USB command sent to a docking station results in an image on a screen. The test harness sends the command, and a frame grabber driver senses what pixels are displayed. This operation might take of the order of tenths of a second, so timeout duration of say a few seconds, with a polling interval of 0.1s gives responsive and reliable tests.
 * Checking that a POST to a REST API is relayed through an IoT backend and translated into a protocol sent over MQTT to a device. The SUT is the backend, including the API gateway. An MQTT client driver in the test harness receives the messages sent. The message is usually relayed in fractions of a second, so a good duration is maybe a second or two, and a polling delay of 0.01s gives fast tests.
 * At a test suite setup, the SUT is a Windows device driver. The setup should make a clean installation of the driver, and wait for the device to enumerate in Windows' device tree. While this usually take a few tens of seconds, it can take up to two minutes. In this case a duration of three minutes and a polling interval of a second is appropriate.

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

def assert_eventually(probe, reason):
    asyncmatch.assert_eventually(probe, DURATION_SECS, POLL_DELAY_SECS, reason)

def test_led_remote_control(device):
    remote_control = get_endpoint("/remote")
    remote_control.post({"red_led": "on"})
    assert_eventually(GpioProbe(has_entry("gpio3", "high")), "The red LED is not on")
```

This test is still cluttered with details of how the test is carried out, and
exposes to the reader that there is a probe that uses a dictionary to record the
state of the GPIOs.  Tests provide the most value when they document clearly and
concisely the system state transition that they are checking for. A good test
should express _what_ is being tested without exposing the details of _how_ the test
is carried out - good tests are declarative rather than imperative.  

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

def _led(gpio: str, state: str) -> Matcher
    if state == "on":
        state = "high"
    elif state == "off":
        state == "low":
    else:
        raise ValueError(f"unknown LED state {state}")
    return has_entry(gpio, state)

def red(state: str) -> Matcher:
    return _led("gpio3", state)

def green(state: str) -> Matcher:
    return _led("gpio4", state)

def leds(matcher: Matcher) -> GpioProbe
    return GpioProbe(matcher)

```

Careful design can unlock the higher order grammar of Hamcrest. For example, we can now write an assertion:

```python
    assert_eventually(leds(all_of(
        red("on"),
        green("off")
    ))
```

