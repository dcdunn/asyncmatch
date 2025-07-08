from asyncmatch.callable_probe import CallableProbe
import pytest
from unittest.mock import MagicMock, call
from hamcrest import assert_that, equal_to
from hamcrest.core.string_description import StringDescription

def test_should_raise_type_error_if_construct_with_non_callable():
    with pytest.raises(TypeError):
        CallableProbe(42)

def test_should_raise_type_error_if_trying_to_use_class_as_callable():
    class SomeState:
        pass 

    with pytest.raises(TypeError):
        probe = CallableProbe(SomeState)

def test_should_construct_with_free_function():
    def is_satisfied():
        return True
    CallableProbe(is_satisfied)

def test_should_construct_with_bound_function():
    class SomeClass:
        def is_satisfied(self):
            return True
    obj = SomeClass()
    CallableProbe(obj.is_satisfied)

def test_should_construct_with_lambda():
    probe = CallableProbe(lambda: True)
    assert_that(probe.is_satisfied())   

def test_should_call_underlying_callable_to_sample_on_construction():
    is_satisfied = MagicMock(return_value=False)
    probe = CallableProbe(is_satisfied)
    is_satisfied.assert_called_once()

def test_should_not_be_satisfied_if_underlying_callable_returns_false():
    is_satisfied = MagicMock(return_value=False)
    probe = CallableProbe(is_satisfied)
    assert_that(not probe.is_satisfied())

def test_should_be_satisfied_if_underlying_callable_returns_true():
    is_satisfied = MagicMock(return_value=True)
    probe = CallableProbe(is_satisfied)
    assert_that(probe.is_satisfied())

def test_should_be_satisfied_if_sample_results_in_callable_returning_true():
    is_satisfied = MagicMock()
    is_satisfied.side_effect = [False, True]
    probe = CallableProbe(is_satisfied)
    assert_that(not probe.is_satisfied())
    probe.sample()
    assert_that(probe.is_satisfied())

def test_should_describe_to_using_name_of_free_function():
    def some_state():
        return True
    probe = CallableProbe(some_state)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("some_state to be satisfied"))

def test_should_describe_mismatch_using_name_of_free_function():
    def some_state():
        return True
    probe = CallableProbe(some_state)
    description = StringDescription()
    probe.describe_mismatch(description)
    assert_that(str(description), equal_to("some_state was not satisfied"))

def test_should_describe_to_using_name_of_bound_function():
    class SomeClass:
        def some_state(self):
            return True

    obj = SomeClass()
    probe = CallableProbe(obj.some_state)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("some_state to be satisfied"))

def test_should_describe_to_using_lambda():
    probe = CallableProbe(lambda: True)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("<lambda> to be satisfied"))

def test_should_describe_to_using_callable_class_name():
    class SomeState:
        def __call__(self):
            return True
    obj = SomeState()
    probe = CallableProbe(obj)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("SomeState to be satisfied"))

def test_should_describe_to_using_classmethod_name():
    class SomeClass:
        @classmethod
        def some_state(cls):
            return True

    probe = CallableProbe(SomeClass.some_state)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("some_state to be satisfied"))

def test_should_describe_to_using_staticmethod_name():
    class SomeClass:
        @staticmethod
        def some_state():
            return True

    probe = CallableProbe(SomeClass.some_state)
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("some_state to be satisfied"))

def test_should_describe_to_using_closure_name():
    def closure(state: bool):
        def is_satisfied():
            return state
        return is_satisfied

    probe = CallableProbe(closure(True))
    description = StringDescription()
    probe.describe_to(description)
    assert_that(str(description), equal_to("is_satisfied to be satisfied"))
