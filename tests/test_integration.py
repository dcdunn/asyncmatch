from asyncmatch import Probe
from threading import Thread, Event
from hamcrest import greater_than
from time import sleep

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

    def run(self):
        while not self.stop_event.is_set():
            self.counter.increment()
    
    def stop(self):
        self.stop_event.set()

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

def test_usage_of_probe():
    counter = Counter()
    thread = CountingThread(counter)
    probe = CounterProbe(counter, greater_than(500))

    thread.start()

    while not probe.is_satisfied():
        probe.sample()
    
    thread.stop()
    thread.join()