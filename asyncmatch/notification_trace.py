from .exceptions import SynchronisationTimeout
from .timeout import Timeout
from hamcrest.core.matcher import Matcher
from hamcrest.core.string_description import StringDescription
from threading import Condition
from typing import Any, List, Optional, Sequence, Tuple, Type


class NotificationTrace:
    """
    Records notifications emitted by the subject-under-test so that a test
    can wait for one that matches, without polling.

    The subject-under-test calls :py:meth:`append` (from any thread). The test
    calls :py:meth:`assert_eventually_contains` or
    :py:meth:`wait_until_contains`, which block until a matching item has been
    appended or the duration expires. Every item appended since the trace was
    created (or last cleared) is searched, so neither an item that arrived
    before the test started waiting nor one that was quickly followed by
    others is missed.

    To check that notifications arrive in a particular order, use
    :py:meth:`assert_eventually_contains_in_order` or
    :py:meth:`wait_until_contains_in_order`.

    To check what has already arrived, after synchronising, use
    :py:meth:`assert_contains`, :py:meth:`assert_contains_in_order` and
    :py:meth:`assert_does_not_contain`.

    To test in phases, use :py:meth:`wait_until_phase_ends`, or
    :py:meth:`clear` when the test itself starts each phase.
    """

    def __init__(self):
        self._condition = Condition()
        self._items: List[Any] = []
        self._phase_start = 0

    def append(self, item: Any) -> None:
        """
        Record a notification. Thread-safe; wakes any waiting test.
        """
        with self._condition:
            self._items.append(item)
            self._condition.notify_all()

    def clear(self) -> None:
        """
        Discard every notification recorded so far, and start the next phase
        here.

        Only safe when the test itself starts the next phase, after calling
        clear. If the subject-under-test may already have sent notifications
        for the next phase, clear discards them; use
        :py:meth:`wait_until_phase_ends` instead.
        """
        with self._condition:
            self._items.clear()
            self._phase_start = 0

    def assert_eventually_contains(self, matcher: Matcher, duration: float, reason: Optional[str] = "") -> None:
        """
        Wait until an item matching ``matcher`` has been appended. Raises an
        :py:exc:`AssertionError` if none arrives within ``duration`` seconds.
        """
        self._wait_for([matcher], duration, reason, AssertionError)

    def wait_until_contains(self, matcher: Matcher, duration: float, reason: Optional[str] = "") -> None:
        """
        Similar to assert_eventually_contains, but raises a
        SynchronisationTimeout if no matching item arrives within ``duration``
        seconds.
        """
        self._wait_for([matcher], duration, reason, SynchronisationTimeout)

    def assert_eventually_contains_in_order(self, matchers: Sequence[Matcher], duration: float, reason: Optional[str] = "") -> None:
        """
        Wait until items matching each of ``matchers`` have been appended, in
        that order; each matcher must match a later item than the one before.
        Other items may come in between. Raises an :py:exc:`AssertionError` if
        the whole sequence has not arrived within ``duration`` seconds.
        """
        self._wait_for(matchers, duration, reason, AssertionError)

    def wait_until_contains_in_order(self, matchers: Sequence[Matcher], duration: float, reason: Optional[str] = "") -> None:
        """
        Similar to assert_eventually_contains_in_order, but raises a
        SynchronisationTimeout if the sequence has not arrived within
        ``duration`` seconds.
        """
        self._wait_for(matchers, duration, reason, SynchronisationTimeout)

    def assert_contains(self, matcher: Matcher, reason: Optional[str] = "") -> None:
        """
        Check, without waiting, that an item matching ``matcher`` has already
        been appended. Raises an :py:exc:`AssertionError` if not.

        Only use this after synchronising (e.g. with
        :py:meth:`wait_until_contains`) on a notification that the
        subject-under-test sends no earlier than the one being checked.
        Otherwise the result depends on timing.
        """
        with self._condition:
            _check_contains(self._items, [matcher], reason)

    def assert_contains_in_order(self, matchers: Sequence[Matcher], reason: Optional[str] = "") -> None:
        """
        Check, without waiting, that items matching each of ``matchers`` have
        already been appended, in that order. Raises an
        :py:exc:`AssertionError` if not. Synchronise first, as for
        :py:meth:`assert_contains`.
        """
        with self._condition:
            _check_contains(self._items, matchers, reason)

    def assert_does_not_contain(self, matcher: Matcher, reason: Optional[str] = "") -> None:
        """
        Check, without waiting, that no item matching ``matcher`` has been
        appended. Raises an :py:exc:`AssertionError` naming the matching items
        if any have.

        Only meaningful after synchronising on a notification that the
        subject-under-test sends after the one that must not appear (see
        "Testing That an Action Has No Effect" in GOOS ch. 27). Otherwise it
        can pass simply because the unwanted notification has not arrived yet.
        """
        with self._condition:
            _check_does_not_contain(self._items, matcher, reason)

    def wait_until_phase_ends(self, sentinel: Matcher, duration: float, reason: Optional[str] = "") -> "Phase":
        """
        Wait for a notification matching ``sentinel``, which marks the end of
        a phase, and return that :py:class:`Phase`: the notifications from the
        end of the previous phase up to and including the sentinel.

        The search starts after the previous phase's sentinel, so phases that
        end with identical notifications are told apart. Notifications that
        arrive after the sentinel stay in the trace for the next phase, so
        none are lost however quickly the subject-under-test moves on.
        Raises a SynchronisationTimeout if no sentinel arrives within
        ``duration`` seconds.
        """
        with self._condition:
            stream = self._wait_locked([sentinel], duration, reason, SynchronisationTimeout, self._phase_start)
            phase = Phase(self._items[self._phase_start:stream.end_of_last_match])
            self._phase_start = stream.end_of_last_match
            return phase

    def _wait_for(self, matchers: Sequence[Matcher], duration: float, reason: str, exc_type: Type[Exception]) -> None:
        with self._condition:
            self._wait_locked(matchers, duration, reason, exc_type, 0)

    def _wait_locked(self, matchers: Sequence[Matcher], duration: float, reason: str,
                     exc_type: Type[Exception], start: int) -> "_NotificationStream":
        timeout = Timeout(duration)
        stream = _NotificationStream(self._items, start)
        for matcher in matchers:
            while not stream.has_matched(matcher):
                if timeout.timed_out():
                    raise exc_type(_describe_missing(matchers, stream, reason))
                timeout.wait_on(self._condition)
        return stream


class Phase:
    """
    The notifications of one phase, as returned by
    :py:meth:`NotificationTrace.wait_until_phase_ends`: everything from the
    end of the previous phase up to and including this phase's sentinel.

    A phase is a snapshot. It does not change, so its checks never wait, and
    they are always safe: the phase only exists once its sentinel has arrived.
    Failure messages list only this phase's notifications.
    """

    def __init__(self, notifications: Sequence[Any]):
        self._notifications: Tuple[Any, ...] = tuple(notifications)

    def assert_contains(self, matcher: Matcher, reason: Optional[str] = "") -> None:
        """Check that this phase contains a notification matching ``matcher``."""
        _check_contains(self._notifications, [matcher], reason)

    def assert_contains_in_order(self, matchers: Sequence[Matcher], reason: Optional[str] = "") -> None:
        """Check that this phase contains notifications matching ``matchers``, in that order."""
        _check_contains(self._notifications, matchers, reason)

    def assert_does_not_contain(self, matcher: Matcher, reason: Optional[str] = "") -> None:
        """Check that this phase contains no notification matching ``matcher``."""
        _check_does_not_contain(self._notifications, matcher, reason)


class _NotificationStream:
    """
    Searches a growing list of notifications, picking up after the last one it
    examined. A match consumes the notification, so the next search starts
    after it.
    """

    def __init__(self, notifications: Sequence[Any], start: int = 0):
        self._notifications = notifications
        self._next = start
        self.end_of_last_match = start
        self.matched: List[Any] = []

    def has_matched(self, criteria: Matcher) -> bool:
        while self._next < len(self._notifications):
            notification = self._notifications[self._next]
            self._next += 1
            if criteria.matches(notification):
                self.matched.append(notification)
                self.end_of_last_match = self._next
                return True
        return False

    @property
    def unmatched(self) -> List[Any]:
        """Notifications received after the last match."""
        return list(self._notifications[self.end_of_last_match:])


def _check_contains(notifications: Sequence[Any], matchers: Sequence[Matcher], reason: Optional[str]) -> None:
    stream = _NotificationStream(notifications)
    for matcher in matchers:
        if not stream.has_matched(matcher):
            raise AssertionError(_describe_missing(matchers, stream, reason))


def _check_does_not_contain(notifications: Sequence[Any], matcher: Matcher, reason: Optional[str]) -> None:
    matching = [item for item in notifications if matcher.matches(item)]
    if matching:
        description = _start_description(reason)
        description.append_text("Expected: no notification matching ") \
            .append_description_of(matcher) \
            .append_text("\n     but: received ") \
            .append_list("[", ", ", "]", matching)
        raise AssertionError(str(description))


def _describe_missing(matchers: Sequence[Matcher], stream: _NotificationStream, reason: Optional[str]) -> str:
    description = _start_description(reason)
    if len(matchers) == 1:
        description.append_text("Expected: a notification matching ") \
            .append_description_of(matchers[0])
    else:
        description.append_list("Expected: notifications matching ", " then ", ", in order", matchers)
    description.append_text("\n     but: ")
    if stream.matched:
        description.append_list("matched ", " then ", ", then ", stream.matched)
    description.append_text("received ")
    if stream.unmatched:
        description.append_list("[", ", ", "]", stream.unmatched)
    else:
        description.append_text("nothing")
    return str(description)


def _start_description(reason: Optional[str]) -> StringDescription:
    description = StringDescription()
    if reason:
        description.append_text(reason).append_text("\n")
    return description
