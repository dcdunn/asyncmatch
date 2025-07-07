from .exceptions import SynchronisationTimeout
from .probe import Probe
from .poller import Poller, PollerTimeout
from .timeout import Timeout
from hamcrest.core.string_description import StringDescription
from typing import Optional

def report_failure_of_probe(probe: Probe, reason: str, exc_type: Exception) -> None:
    description = StringDescription()
    description.append_text(reason).  \
        append_text("\nExpected: ").  \
        append_description_of(probe). \
        append_text("\n     but: ")
    probe.describe_mismatch(description)
    raise exc_type(description) from None

def _wait_for_poller(poller: Poller, probe: Probe, reason: str, exc_type: Exception) -> None:
    try:
        poller.check(probe)
    except PollerTimeout:
        report_failure_of_probe(probe, reason, exc_type)

def assert_eventually(probe: Probe, duration: float, poll_delay: float, reason: Optional[str] = "") -> None:
    """
    Polls some system state using the Probe, until it is satisfied or it times
    out. ``assert_eventually`` is designed to integrate well with PyUnit, pytest
    and other unit testing frameworks. The exception raised for an unmet
    assertion is an :py:exc:`AssertionError`, which test frameworks report as a test
    failure.

    It is also compatible with the PyHamcrest library, allowing the use of matchers
    to define the conditions that must be met by the probe.
    """

    poller = Poller(Timeout(duration, poll_delay))
    _wait_for_poller(poller, probe, reason, AssertionError)

def wait_until(probe: Probe, duration: float, poll_delay: float, reason: Optional[str] = "") -> None:
    """
    Similar to assert_eventaully, but raises a SynchronisationTimeout if the
    Poller times out.
    """

    poller = Poller(Timeout(duration, poll_delay))
    _wait_for_poller(poller, probe, reason, SynchronisationTimeout)