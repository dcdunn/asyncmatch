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

    def _probe_satisfied(self, probe: Probe) -> bool:
        satisfied = probe.is_satisfied()
        if not isinstance(satisfied, bool):
            raise TypeError(f"Probe {probe} did not return a boolean value")
        return satisfied

    def check(self, probe: Probe) -> None:
        """
        Check the probe until it is satisfied or the timeout expires.
        """
        while not self._probe_satisfied(probe):
            if self.timeout.timed_out():
                raise PollerTimeout()
            self.timeout.sleep()
            probe.sample()