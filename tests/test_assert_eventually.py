from asyncmatch.assert_eventually import assert_eventually, report_failure_of_probe
from asyncmatch.probe import Probe
from unittest.mock import MagicMock, call
from hamcrest import assert_that, starts_with, contains_string
import pytest

class FakeProbe(Probe):
    def is_satisfied(self):
        return True

    def sample(self):
        pass

    def describe_to(self, description):
        description.append_text("FakeProbe")

    def describe_mismatch(self, description):
        description.append_text("FakeProbe mismatch")

class TestAssertEventually:
    def test_should_not_timeout_when_probe_satisfied_immediately(self):
        probe = MagicMock()
        probe.is_satisfied.return_value = True

        assert_eventually(probe, 5.0, 0.01)
        
        probe.assert_has_calls([
            call.is_satisfied()
        ])

    def test_should_raise_assertion_error_when_timed_out(self):
        probe = MagicMock()
        probe.is_satisfied.return_value = False

        with pytest.raises(AssertionError):
            assert_eventually(probe, 0.1, 0.01)

class TestReportFailureOfProbe:
    def test_should_report_bespoke_reason_first(self):
        probe = MagicMock()
        with pytest.raises(AssertionError) as err:
            report_failure_of_probe(probe, "Bespoke reason")

        assert_that(str(err.value), starts_with("Bespoke reason"))

    def test_should_ask_probe_to_describe_self(self):
        probe = FakeProbe()
        with pytest.raises(AssertionError) as err:
            report_failure_of_probe(probe, "")

        assert_that(str(err.value), contains_string("Expected: FakeProbe"))

    def test_should_ask_probe_to_describe_mismatch(self):
        probe = FakeProbe()
        with pytest.raises(AssertionError) as err:
            report_failure_of_probe(probe, "")

        assert_that(str(err.value), contains_string("     but: FakeProbe mismatch"))