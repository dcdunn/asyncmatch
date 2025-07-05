# asyncmatch

Python is sometimes used for integration or system testing. Often a particular
challenge is the inherent asynchrony in the subject-under-test. A well-designed
system is likely to have messaging protocols between different components,
including third-party ones. For example, consider an IoT backend, where a
REST API query is relayed through a couple of microservices to a remote device
via MQTT. To test this system, the test harness might make an HTTP query, and
using a test double MQTT client sense that the query is translated into an
expected message to the device. Such a system is inherently asynchronous, which
present a problem when using a standard Arrange-Act-Assert pattern. 

```python
from api import get_endpoint

def test_led_remote_control():
    # Fixture - device test double
    device = Device()

    # Arrange
    remote_control = get_endpoint("/remote")

    # Act
    api.post({"gpio1": "on"})

    # Assert
    assert_that(device.led, is_on())

```

This test is likely to always fail, because when control returns to the test
following the API query, the request has not yet been translated and reached the
device to be actioned. A naive approach, such as adding an arbitrary wait after
sending the message will, at the very least, make the test take longer to pass
than it needs to, and more likely to be an unreliable test.  

In their famous book, [Growing Object-Oriented Software Guided by Tests](https://www.amazon.co.uk/Growing-Object-Oriented-Software-Guided-Signature/dp/0321503627), Steve Freeman and Nat Pryce address this concern in Chapter 27 _Testing Asynchronous Code_. They outline some techniques to enable tests to follow the Arrange-Act-Assert pattern for asynchronous systems. In short, the test drivers have to synchronise with the subject-under-test. As for any synchronisation problem, there are two categories of approach: wait to be informed of an event or periodically poll for state.

This project is a simple implementation in Python of those ideas, and is compatible with [PyHamcrest](https://github.com/hamcrest/PyHamcrest).


## Probes

A *Probe* is an object that probes some state of the system, and uses a PyHamcrest matcher to understand if that state has satisfied some desired condition. The *Probe* underpins the *assert_eventually* matcher.

Tip: a *Probe* can can sample in its initialise function. This gives the test an opportunity to pass quickly, before the first sleep.

## Poller

The *Poller* checks a *Probe* until it is satisfied or it times out. 

```python
poller = Poller(Timeout(5.0, 0.1))

# blocks until MyProbe satisfied. Raises AssertionError if times out
poller.check(MyProbe())
```