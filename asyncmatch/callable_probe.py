from .probe import Probe
from collections.abc import Callable
from inspect import isclass

def _callable_description(callable_obj: Callable) -> str:
    """
    Returns the name of the callable object or raises a TypeError if it is not
    callable.
    """
    if not callable(callable_obj) or isclass(callable_obj):
        raise TypeError(f"{callable_obj} not callable")
    
    if hasattr(callable_obj, '__name__'):
        return callable_obj.__name__

    # If it's a callable class, use its class name
    if hasattr(type(callable_obj), '__name__'):
        return type(callable_obj).__name__

    return "Martin"

class CallableProbe(Probe):
    def __init__(self, probe_func: Callable[[], bool]):
        self._description = _callable_description(probe_func)
        self._satisfied = False
        self._probe_func = probe_func

        self.sample()
    
    def is_satisfied(self) -> bool:
        return self._satisfied

    def sample(self) -> None:
        self._satisfied = self._probe_func()

    def describe_to(self, description):
        description.append_text(f"{self._description} to be satisfied")

    def describe_mismatch(self, description):
        description.append_text(f"{self._description} was not satisfied")
