from .probe import Probe
from .poller import Poller, PollerTimeout
from .timeout import Timeout
from hamcrest.core.string_description import StringDescription
from typing import Optional

def report_failure_of_probe(probe: Probe, reason: str) -> None:
    description = StringDescription()
    description.append_text(reason).  \
        append_text("\nExpected: ").  \
        append_description_of(probe). \
        append_text("\n     but: ")
    probe.describe_mismatch(description)
    raise AssertionError(description) from None

def assert_eventually(probe: Probe, duration: float, interval: float, reason: Optional[str] = "") -> None:
    """
    ``assert_eventually`` is designed to integrate well with PyUnit and other unit
    testing frameworks. The exception raised for an unmet assertion is an
    :py:exc:`AssertionError`, which PyUnit reports as a test failure.

    It is also compatible with the PyHamcrest library, allowing the use of matchers
    to define the conditions that must be met by the probe.
    """

    try:
        Poller(Timeout(duration, interval)).check(probe)
    except PollerTimeout:
        report_failure_of_probe(probe, reason)