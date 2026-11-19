from asyncmatch import NotificationTrace, SynchronisationTimeout
from hamcrest import assert_that, ends_with, equal_to, less_than, starts_with
from threading import Thread, Timer
from time import monotonic
import pytest


class TestNotificationTrace:
    def test_should_return_immediately_when_match_already_in_trace(self):
        trace = NotificationTrace()
        trace.append("blink")

        start = monotonic()
        trace.assert_eventually_contains(equal_to("blink"), 5.0)

        assert_that(monotonic() - start, less_than(0.5))

    def test_should_raise_assertion_error_when_no_match_before_timeout(self):
        trace = NotificationTrace()
        trace.append("off")

        with pytest.raises(AssertionError):
            trace.assert_eventually_contains(equal_to("blink"), 0.1)

    def test_should_return_when_match_appended_from_another_thread(self):
        trace = NotificationTrace()
        timer = Timer(0.05, trace.append, args=("blink",))

        start = monotonic()
        timer.start()
        trace.assert_eventually_contains(equal_to("blink"), 5.0)
        elapsed = monotonic() - start
        timer.join()

        assert_that(elapsed, less_than(1.0))

    def test_should_report_reason_matcher_and_received_items_on_failure(self):
        trace = NotificationTrace()
        trace.append("on")
        trace.append("off")

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains(equal_to("blink"), 0.05, reason="LED never blinked")

        assert_that(str(err.value), equal_to(
            "LED never blinked\n"
            "Expected: a notification matching 'blink'\n"
            "     but: received ['on', 'off']"))

    def test_should_report_received_nothing_when_trace_empty(self):
        trace = NotificationTrace()

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains(equal_to("blink"), 0.05)

        assert_that(str(err.value), ends_with("     but: received nothing"))

    def test_should_find_transient_item_followed_by_later_items(self):
        # The lost-update case: a poller sampling the latest state would only see "off".
        trace = NotificationTrace()
        trace.append("blink")
        trace.append("off")

        trace.assert_eventually_contains(equal_to("blink"), 0.05)

    def test_should_lose_no_items_when_appended_concurrently(self):
        trace = NotificationTrace()
        threads, per_thread = 8, 500

        def producer(n):
            for i in range(per_thread):
                trace.append((n, i))

        workers = [Thread(target=producer, args=(n,)) for n in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        for n in range(threads):
            trace.assert_eventually_contains(equal_to((n, per_thread - 1)), 0.05)
            trace.assert_eventually_contains(equal_to((n, 0)), 0.05)

    def test_wait_until_contains_should_return_when_match_in_trace(self):
        trace = NotificationTrace()
        trace.append("blink")

        trace.wait_until_contains(equal_to("blink"), 5.0)

    def test_wait_until_contains_should_raise_synchronisation_timeout(self):
        trace = NotificationTrace()
        trace.append("off")

        with pytest.raises(SynchronisationTimeout) as err:
            trace.wait_until_contains(equal_to("blink"), 0.05, reason="no blink")

        assert_that(str(err.value), starts_with("no blink\nExpected: a notification matching 'blink'"))


class TestContainsInOrder:
    def test_should_match_items_in_order(self):
        trace = NotificationTrace()
        trace.append("blink")
        trace.append("off")

        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

    def test_should_allow_other_items_in_between(self):
        trace = NotificationTrace()
        for item in ("blink", "on", "dim", "off"):
            trace.append(item)

        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

    def test_should_skip_later_items_that_arrived_before_the_earlier_one(self):
        trace = NotificationTrace()
        for item in ("off", "blink", "on", "off"):
            trace.append(item)

        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

    def test_should_fail_when_items_arrived_in_other_order(self):
        trace = NotificationTrace()
        trace.append("blink")
        trace.append("off")

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains_in_order([equal_to("off"), equal_to("blink")], 0.05)

        assert_that(str(err.value), equal_to(
            "Expected: notifications matching 'off' then 'blink', in order\n"
            "     but: matched 'off', then received nothing"))

    def test_should_report_items_received_after_last_match(self):
        trace = NotificationTrace()
        for item in ("on", "blink", "off"):
            trace.append(item)

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains_in_order([equal_to("on"), equal_to("dim")], 0.05)

        assert_that(str(err.value), ends_with("     but: matched 'on', then received ['blink', 'off']"))

    def test_should_report_everything_received_when_nothing_matched(self):
        trace = NotificationTrace()
        trace.append("on")

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

        assert_that(str(err.value), ends_with("     but: received ['on']"))

    def test_should_need_a_separate_notification_for_each_matcher(self):
        trace = NotificationTrace()
        trace.append("blink")

        with pytest.raises(AssertionError):
            trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("blink")], 0.05)

        trace.append("blink")
        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("blink")], 0.05)

    def test_should_wait_for_later_items_in_the_sequence(self):
        trace = NotificationTrace()
        trace.append("blink")
        timer = Timer(0.05, trace.append, args=("off",))

        start = monotonic()
        timer.start()
        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 5.0)
        elapsed = monotonic() - start
        timer.join()

        assert_that(elapsed, less_than(1.0))

    def test_should_search_from_the_start_on_every_call(self):
        trace = NotificationTrace()
        trace.append("blink")
        trace.append("off")

        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)
        trace.assert_eventually_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

    def test_should_put_reason_first(self):
        trace = NotificationTrace()

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains_in_order([equal_to("blink")], 0.05, reason="no blink")

        assert_that(str(err.value), starts_with("no blink\nExpected: "))

    def test_wait_until_contains_in_order_should_raise_synchronisation_timeout(self):
        trace = NotificationTrace()
        trace.append("off")

        with pytest.raises(SynchronisationTimeout) as err:
            trace.wait_until_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)

        assert_that(str(err.value), starts_with("Expected: notifications matching 'blink' then 'off', in order"))

    def test_wait_until_contains_in_order_should_return_when_sequence_present(self):
        trace = NotificationTrace()
        trace.append("blink")
        trace.append("off")

        trace.wait_until_contains_in_order([equal_to("blink"), equal_to("off")], 0.05)


class TestFailureMessageWithoutReason:
    def test_message_should_start_with_expected_when_no_reason(self):
        trace = NotificationTrace()

        with pytest.raises(AssertionError) as err:
            trace.assert_eventually_contains(equal_to("blink"), 0.05)

        assert_that(str(err.value), starts_with("Expected: "))

    def test_synchronisation_message_should_start_with_expected_when_no_reason(self):
        trace = NotificationTrace()

        with pytest.raises(SynchronisationTimeout) as err:
            trace.wait_until_contains(equal_to("blink"), 0.05)

        assert_that(str(err.value), starts_with("Expected: "))


class TestImmediateChecks:
    def test_assert_contains_should_pass_when_match_already_in_trace(self):
        trace = NotificationTrace()
        trace.append("blink")

        trace.assert_contains(equal_to("blink"))

    def test_assert_contains_should_fail_at_once_when_no_match(self):
        trace = NotificationTrace()
        trace.append("off")

        start = monotonic()
        with pytest.raises(AssertionError) as err:
            trace.assert_contains(equal_to("blink"))
        elapsed = monotonic() - start

        assert_that(elapsed, less_than(0.05))
        assert_that(str(err.value), equal_to(
            "Expected: a notification matching 'blink'\n"
            "     but: received ['off']"))

    def test_assert_contains_should_put_reason_first(self):
        trace = NotificationTrace()

        with pytest.raises(AssertionError) as err:
            trace.assert_contains(equal_to("blink"), reason="no blink")

        assert_that(str(err.value), starts_with("no blink\nExpected: "))

    def test_assert_contains_in_order_should_pass_when_sequence_in_trace(self):
        trace = NotificationTrace()
        for item in ("blink", "on", "off"):
            trace.append(item)

        trace.assert_contains_in_order([equal_to("blink"), equal_to("off")])

    def test_assert_contains_in_order_should_fail_at_once_when_out_of_order(self):
        trace = NotificationTrace()
        trace.append("off")
        trace.append("blink")

        start = monotonic()
        with pytest.raises(AssertionError) as err:
            trace.assert_contains_in_order([equal_to("blink"), equal_to("off")], reason="wrong order")
        elapsed = monotonic() - start

        assert_that(elapsed, less_than(0.05))
        assert_that(str(err.value), equal_to(
            "wrong order\n"
            "Expected: notifications matching 'blink' then 'off', in order\n"
            "     but: matched 'blink', then received nothing"))

    def test_assert_does_not_contain_should_pass_when_no_match(self):
        trace = NotificationTrace()
        trace.append("off")

        trace.assert_does_not_contain(equal_to("blink"))

    def test_assert_does_not_contain_should_pass_when_trace_empty(self):
        NotificationTrace().assert_does_not_contain(equal_to("blink"))

    def test_assert_does_not_contain_should_fail_naming_the_matching_items(self):
        trace = NotificationTrace()
        for item in ("blink", "off", "blink"):
            trace.append(item)

        with pytest.raises(AssertionError) as err:
            trace.assert_does_not_contain(equal_to("blink"))

        assert_that(str(err.value), equal_to(
            "Expected: no notification matching 'blink'\n"
            "     but: received ['blink', 'blink']"))

    def test_assert_does_not_contain_should_put_reason_first(self):
        trace = NotificationTrace()
        trace.append("blink")

        with pytest.raises(AssertionError) as err:
            trace.assert_does_not_contain(equal_to("blink"), reason="should be ignored")

        assert_that(str(err.value), starts_with("should be ignored\nExpected: "))


class TestClear:
    def test_should_discard_notifications_appended_before_clear(self):
        trace = NotificationTrace()
        trace.append("blink")

        trace.clear()

        with pytest.raises(AssertionError) as err:
            trace.assert_contains(equal_to("blink"))
        assert_that(str(err.value), ends_with("     but: received nothing"))

    def test_should_find_notifications_appended_after_clear(self):
        trace = NotificationTrace()
        trace.append("off")
        trace.clear()
        trace.append("blink")

        trace.assert_contains(equal_to("blink"))

    def test_should_start_the_next_phase_at_the_clear(self):
        trace = NotificationTrace()
        for item in ("a", "done", "b"):
            trace.append(item)
        trace.wait_until_phase_ends(equal_to("done"), 0.05)

        trace.clear()
        trace.append("c")
        trace.append("done")
        phase = trace.wait_until_phase_ends(equal_to("done"), 0.05)

        phase.assert_contains(equal_to("c"))
        phase.assert_does_not_contain(equal_to("b"))


class TestPhases:
    def test_phase_should_hold_notifications_up_to_and_including_the_sentinel(self):
        trace = NotificationTrace()
        for item in ("a", "b", "done", "c"):
            trace.append(item)

        phase = trace.wait_until_phase_ends(equal_to("done"), 0.05)

        phase.assert_contains_in_order([equal_to("a"), equal_to("b"), equal_to("done")])
        phase.assert_does_not_contain(equal_to("c"))

    def test_next_phase_should_start_after_the_previous_sentinel(self):
        trace = NotificationTrace()
        for item in ("a", "done", "b", "done"):
            trace.append(item)

        trace.wait_until_phase_ends(equal_to("done"), 0.05)
        phase2 = trace.wait_until_phase_ends(equal_to("done"), 0.05)

        phase2.assert_contains(equal_to("b"))
        phase2.assert_does_not_contain(equal_to("a"))

    def test_should_keep_notifications_of_a_phase_that_started_before_the_test_asked(self):
        # Back-to-back phases: everything arrives before the test looks at phase 1.
        trace = NotificationTrace()
        for item in ("a", "done1", "b", "done2"):
            trace.append(item)

        trace.wait_until_phase_ends(equal_to("done1"), 0.05)
        phase2 = trace.wait_until_phase_ends(equal_to("done2"), 0.05)

        phase2.assert_contains(equal_to("b"))

    def test_should_wait_for_the_sentinel(self):
        trace = NotificationTrace()
        trace.append("a")
        timer = Timer(0.05, trace.append, args=("done",))

        start = monotonic()
        timer.start()
        phase = trace.wait_until_phase_ends(equal_to("done"), 5.0)
        elapsed = monotonic() - start
        timer.join()

        assert_that(elapsed, less_than(1.0))
        phase.assert_contains(equal_to("a"))

    def test_should_raise_synchronisation_timeout_listing_only_this_phase(self):
        trace = NotificationTrace()
        for item in ("a", "done1", "b"):
            trace.append(item)
        trace.wait_until_phase_ends(equal_to("done1"), 0.05)

        with pytest.raises(SynchronisationTimeout) as err:
            trace.wait_until_phase_ends(equal_to("done2"), 0.05, reason="phase 2 never ended")

        assert_that(str(err.value), equal_to(
            "phase 2 never ended\n"
            "Expected: a notification matching 'done2'\n"
            "     but: received ['b']"))

    def test_whole_history_searches_should_ignore_phases(self):
        trace = NotificationTrace()
        for item in ("a", "done"):
            trace.append(item)
        trace.wait_until_phase_ends(equal_to("done"), 0.05)

        trace.assert_contains(equal_to("a"))

    def test_phase_assert_contains_should_list_only_this_phase_on_failure(self):
        trace = NotificationTrace()
        for item in ("a", "done1", "b", "done2"):
            trace.append(item)
        trace.wait_until_phase_ends(equal_to("done1"), 0.05)
        phase2 = trace.wait_until_phase_ends(equal_to("done2"), 0.05)

        with pytest.raises(AssertionError) as err:
            phase2.assert_contains(equal_to("a"), reason="phase 2")

        assert_that(str(err.value), equal_to(
            "phase 2\n"
            "Expected: a notification matching 'a'\n"
            "     but: received ['b', 'done2']"))

    def test_phase_assert_contains_in_order_should_fail_when_out_of_order(self):
        trace = NotificationTrace()
        for item in ("off", "on", "done"):
            trace.append(item)
        phase = trace.wait_until_phase_ends(equal_to("done"), 0.05)

        with pytest.raises(AssertionError) as err:
            phase.assert_contains_in_order([equal_to("on"), equal_to("off")])

        assert_that(str(err.value), ends_with("     but: matched 'on', then received ['done']"))

    def test_phase_assert_does_not_contain_should_name_the_matching_items(self):
        trace = NotificationTrace()
        for item in ("error", "done"):
            trace.append(item)
        phase = trace.wait_until_phase_ends(equal_to("done"), 0.05)

        with pytest.raises(AssertionError) as err:
            phase.assert_does_not_contain(equal_to("error"))

        assert_that(str(err.value), equal_to(
            "Expected: no notification matching 'error'\n"
            "     but: received ['error']"))
