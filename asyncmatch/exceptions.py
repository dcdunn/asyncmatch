
class SynchronisationTimeout(Exception):
    """
    Raised when a wait_until times out
    """
    def __init__(self, msg: str):
        super().__init__(msg)
