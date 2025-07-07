from .timeout import Timeout
from .probe import Probe

class PollerTimeout(Exception):
    """
    Exception raised when the poller times out while checking a probe.
    """
    pass

class Poller:
    def __init__(self, timeout: Timeout):
        self.timeout = timeout

    def check(self, probe: Probe) -> None:
        """
        Check the probe until it is satisfied or the timeout expires.
        """
        while not probe.is_satisfied():
            if self.timeout.timed_out():
                raise PollerTimeout()
            self.timeout.sleep()
            probe.sample()