from threading import Condition
from time import time, sleep

class Timeout:
    """
    A simple timeout class for synchronising a test harness with a system-under-test
    """

    def __init__(self, duration: float, poll_delay: float = 0.0):
        self._end_time = time() + duration
        self._poll_delay = poll_delay

    def timed_out(self) -> bool:
        return self._time_remaining() <= 0

    def sleep(self) -> None:
        sleep(self._poll_delay)

    def wait_on(self, condition: Condition) -> None:
        """
        Wait on the condition until notified or the time remaining expires.
        The caller must hold the condition's lock.
        """
        wait_time = self._time_remaining()
        if wait_time > 0:
            condition.wait(wait_time)

    def _time_remaining(self) -> float:
        return self._end_time - time()
