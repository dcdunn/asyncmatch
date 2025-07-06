from asyncmatch.probe import Probe
from hamcrest.core.string_description import StringDescription
import pytest

class TestProbeIsAbstract:
    def test_should_raise_if_is_satisfied_called(self):
        with pytest.raises(NotImplementedError):
            Probe().is_satisfied()

    def test_should_raise_if_sample_called(self):
        with pytest.raises(NotImplementedError):
            Probe().sample()

    def test_should_raise_if_describe_mismatch_called(self):
        with pytest.raises(NotImplementedError):
            description = StringDescription()
            Probe().describe_mismatch(description)

    def test_should_be_self_describing(self):
        with pytest.raises(NotImplementedError):
            description = StringDescription()
            Probe().describe_to(description)
