from asyncmatch.poller import Poller, PollerTimeout
from unittest.mock import Mock, MagicMock, call
import pytest

@pytest.fixture
def mockery():
    m = Mock()
    timeout = MagicMock()
    probe = MagicMock()
    m.attach_mock(timeout, 'timeout')
    m.attach_mock(probe, 'probe')
    yield m
    m.reset_mock()


class TestPoller:
    def test_should_not_timeout_when_probe_satisfied_immediately(self, mockery):
        mockery.probe.is_satisfied.return_value = True
        poller = Poller(mockery.timeout)
        poller.check(mockery.probe)
        
        mockery.assert_has_calls([
            call.probe.is_satisfied()
        ])

    
    def test_should_raise_error_when_timed_out(self, mockery):
        mockery.probe.is_satisfied.return_value = False
        mockery.timeout.timed_out.return_value = True
        poller = Poller(mockery.timeout)
        with pytest.raises(PollerTimeout):
            poller.check(mockery.probe)

        mockery.assert_has_calls([
            call.probe.is_satisfied(),
            call.timeout.timed_out()
        ])

    def test_should_sleep_and_resample_if_not_satisfied_and_not_timed_out(self, mockery):
        mockery.probe.is_satisfied.side_effect = [False, True]
        mockery.timeout.timed_out.return_value = False
        poller = Poller(mockery.timeout)
        poller.check(mockery.probe)

        mockery.assert_has_calls([
            call.probe.is_satisfied(),
            call.timeout.timed_out(),
            call.timeout.sleep(),
            call.probe.sample(),
            call.probe.is_satisfied()
        ])

