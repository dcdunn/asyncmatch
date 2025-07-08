from asyncmatch import (
    Probe,
    assert_eventually,
    wait_until,
    SynchronisationTimeout
)
from asyncmatch.timeout import Timeout
from asyncmatch.poller import Poller, PollerTimeout
from threading import Thread, Event
from hamcrest import (
    greater_than,
    less_than,
    assert_that,
    equal_to
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
        while not self.stop_event.is_set() and self.get_count() < 501:
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
    
    def describe_to(self, description):
        description.append_description_of(self.matcher)

    def describe_mismatch(self, description):
        self.matcher.describe_mismatch(self.count, description)

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

count_of = CounterProbe

def test_usage_of_assert_eventually(counting_thread):
    assert_eventually(count_of(counting_thread, greater_than(500)), 5.0, 0.01)

def test_timeout_of_assert_eventually(counting_thread):
    with pytest.raises(AssertionError) as err:
        assert_eventually(count_of(counting_thread, less_than(0)), 0.1, 0.01, "Bespoke reason")
    
    assert_that(str(err.value),
        equal_to("Bespoke reason\nExpected: a value less than <0>\n     but: was <501>"))

def test_usage_of_wait_until(counting_thread):
    wait_until(count_of(counting_thread, greater_than(500)), 5.0, 0.01)

def test_timeout_of_wait_until(counting_thread):
    with pytest.raises(SynchronisationTimeout) as err:
        wait_until(count_of(counting_thread, less_than(0)), 0.1, 0.01, "Bespoke reason")
    
    assert_that(str(err.value),
        equal_to("Bespoke reason\nExpected: a value less than <0>\n     but: was <501>"))

def test_usage_of_assert_eventually_with_callable_as_probe(counting_thread):
    def is_satisfied() -> bool:
        return True

    assert_eventually(is_satisfied, 5.0, 0.01)

def test_timeout_of_assert_eventually_with_callable_as_probe(counting_thread):
    def led_is_on() -> bool:
        return False

    with pytest.raises(AssertionError) as err:
        assert_eventually(led_is_on, 0.1, 0.01, "Bespoke reason")

    assert_that(str(err.value),
        equal_to("Bespoke reason\nExpected: led_is_on to be satisfied\n     but: led_is_on was not satisfied"))