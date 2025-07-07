from time import time, sleep

class Timeout:
    """
    A simple timeout class for synchronising a test harness with a system-under-test
    """

    def __init__(self, duration: float, poll_delay: float):
        self._end_time = time() + duration
        self._poll_delay = poll_delay

    def timed_out(self) -> bool:
        return self._time_remaining() <= 0

    def sleep(self) -> None:
        sleep(self._poll_delay)

    def _time_remaining(self) -> float:
        return self._end_time - time()

