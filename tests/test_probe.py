from asyncmatch.probe import Probe
import pytest

class TestProbeIsAbstract:
    def test_should_raise_if_is_satisfied_called(self):
        with pytest.raises(NotImplementedError):
            Probe().is_satisfied()

    def test_should_raise_if_sample_called(self):
        with pytest.raises(NotImplementedError):
            Probe().sample()
