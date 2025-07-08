from asyncmatch.assert_eventually import (
    assert_eventually,
    wait_until,
    _report_failure_of_probe,
    SynchronisationTimeout
)
from asyncmatch.probe import Probe
from unittest.mock import MagicMock, call
from hamcrest import assert_that, starts_with, contains_string
import pytest

class FakeProbe(Probe):
    def __init__(self, value):
        self.value = value
    def is_satisfied(self):
        return self.value
    def sample(self):
        pass
    def describe_to(self, description):
        description.append_text("FakeProbe")
    def describe_mismatch(self, description):
        description.append_text("FakeProbe mismatch")

class TestAssertEventually:
    def test_should_not_timeout_when_probe_satisfied_immediately(self):
        probe = FakeProbe(True)
        assert_eventually(probe, 5.0, 0.01)
        
    def test_should_raise_assertion_error_when_timed_out(self):
        probe = FakeProbe(False)
        with pytest.raises(AssertionError):
            assert_eventually(probe, 0.1, 0.01)

    def test_should_accept_callable_as_probe(self):
        def is_satisfied():
            return True
        assert_eventually(is_satisfied, 5.0, 0.01)

    def test_should_raise_error_if_not_probe_or_callable(self):
        with pytest.raises(TypeError):
            assert_eventually([42], 5.0, 0.01)

    def test_should_raise_assertion_error_when_timed_out_using_callable(self):
        def is_satisfied():
            return False
        with pytest.raises(AssertionError):
            assert_eventually(is_satisfied, 0.1, 0.01)

class TestWaitUntil:
    def test_should_not_timeout_when_probe_satisfied_immediately(self):
        probe = FakeProbe(True)
        wait_until(probe, 5.0, 0.01)

    def test_should_raise_synchronisation_error_when_timed_out(self):
        probe = FakeProbe(False)
        with pytest.raises(SynchronisationTimeout):
            wait_until(probe, 0.1, 0.01)

    def test_should_raise_error_if_not_probe_or_callable(self):
        with pytest.raises(TypeError):
            wait_until([42], 5.0, 0.01)

    def test_should_raise_assertion_error_when_timed_out_using_callable(self):
        def is_satisfied():
            return False
        with pytest.raises(SynchronisationTimeout):
            wait_until(is_satisfied, 0.1, 0.01)


class SomeError(Exception):
    pass

class TestReportFailureOfProbe:
    def test_should_report_bespoke_reason_first(self):
        probe = FakeProbe(False)
        with pytest.raises(SomeError) as err:
            _report_failure_of_probe(probe, "Bespoke reason", SomeError)

        assert_that(str(err.value), starts_with("Bespoke reason"))

    def test_should_ask_probe_to_describe_self(self):
        probe = FakeProbe(False)
        with pytest.raises(SomeError) as err:
            _report_failure_of_probe(probe, "", SomeError)
        assert_that(str(err.value), contains_string("Expected: FakeProbe"))

    def test_should_ask_probe_to_describe_mismatch(self):
        probe = FakeProbe(False)
        with pytest.raises(SomeError) as err:
            _report_failure_of_probe(probe, "", SomeError)
        assert_that(str(err.value), contains_string("     but: FakeProbe mismatch"))