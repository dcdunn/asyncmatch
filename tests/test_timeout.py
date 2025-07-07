from unittest.mock import patch
from asyncmatch.timeout import Timeout
from hamcrest import assert_that, equal_to

def test_should_not_be_timed_out_if_no_time_elapsed():
    with patch("asyncmatch.timeout.time") as time:
        time.return_value = 0.0
        timeout = Timeout(5.0, 0.1)
        assert_that(timeout.timed_out(), equal_to(False))

def test_should_be_timed_out_if_time_elapsed_exceeds_duration():
    with patch("asyncmatch.timeout.time") as time:
        time.side_effect = [0.0, 100.0]
        timeout = Timeout(5.0, 0.1)
        assert_that(timeout.timed_out(), equal_to(True))

def test_should_be_timed_out_if_time_elapsed_equals_duration():
    with patch("asyncmatch.timeout.time") as time:
        time.side_effect = [0.0, 9.0]
        timeout = Timeout(9.0, 0.1)
        assert_that(timeout.timed_out(), equal_to(True))

def test_should_use_system_sleep():
    with patch("asyncmatch.timeout.sleep") as sleep:
        timeout = Timeout(10.0, 0.42)
        timeout.sleep()
        sleep.assert_called_once_with(0.42)