from asyncmatch import Probe, Timeout
from asyncmatch.poller import Poller, PollerTimeout
from threading import Thread, Event
from contextlib import contextmanager
from hamcrest import (
    greater_than,
    less_than,
)
import pytest

class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def get_count(self):
        return self.count

class CountingThread(Thread):
    def __init__(self, counter):
        super().__init__()
        self.stop_event = Event()
        self.counter = counter
        self.start()
    
    def get_count(self):
        return self.counter.get_count()

    def run(self):
        while not self.stop_event.is_set():
            self.counter.increment()
    
    def stop(self):
        self.stop_event.set()
        self.join()

@pytest.fixture
def counting_thread():
    counter = Counter()
    t = CountingThread(counter)
    yield t
    t.stop()

class CounterProbe(Probe):
    def __init__(self, counter, matcher):
        super().__init__()
        self.counter = counter
        self.count = 0
        self.matcher = matcher
        # It is often prudent to give the test a chance to pass immediately
        self.sample()

    def is_satisfied(self):
        return self.matcher.matches(self.count)
    
    def sample(self):
        self.count = self.counter.get_count()

def test_usage_of_probe(counting_thread):
    timeout = Timeout(5.0, 0.01)
    probe = CounterProbe(counting_thread, greater_than(500))
    while not probe.is_satisfied():
        if timeout.timed_out():
            raise AssertionError("Probe did not satisfy condition within timeout")
        timeout.sleep()
        probe.sample()

def test_usage_of_poller(counting_thread):
    poller = Poller(Timeout(5.0, 0.01))
    poller.check(CounterProbe(counting_thread, greater_than(500)))

def test_timeout_of_poller(counting_thread):
    with pytest.raises(PollerTimeout) as err:
        poller = Poller(Timeout(0.1, 0.01))
        poller.check(CounterProbe(counting_thread, less_than(0)))