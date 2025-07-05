
class Probe:

    """
    Probes some state of the subject-under-test.
    """ 

    def is_satisfied(self) -> bool:
        """
        Check if the probe is satisfied.
        """
        raise NotImplementedError

    def sample(self) -> None:
        """
        Sample the state of the subject-under-test.

        Takes a snapshot of the current state. Only sample
        in this method, so that the state can be checked
        and reported in subsequent calls to is_satisfied
        """
        raise NotImplementedError
