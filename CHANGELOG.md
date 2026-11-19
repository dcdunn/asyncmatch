# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Added
- Added `NotificationTrace` for synchronising by listening rather than polling. The SUT calls the thread-safe `append(item)`. Tests call `assert_eventually_contains(matcher, duration, reason)`, which raises `AssertionError`, or `wait_until_contains(...)`, which raises `SynchronisationTimeout`. Both search every item appended since the trace was created and wake as soon as a match arrives.
- Added `NotificationTrace.assert_eventually_contains_in_order(matchers, duration, reason)` and `wait_until_contains_in_order(...)` for checking that notifications arrive in order. Each matcher must match a later notification than the one before it. On failure, the message says how far the sequence got.
- Added `NotificationTrace.assert_contains(matcher, reason)`, `assert_contains_in_order(matchers, reason)` and `assert_does_not_contain(matcher, reason)`. They check what has already arrived, without waiting, and are meant to follow a synchronisation such as `wait_until_contains`. `assert_does_not_contain` supports GOOS's "testing that an action has no effect" technique.
- Added `NotificationTrace.wait_until_phase_ends(sentinel, duration, reason)` for testing in phases. It waits for the notification that ends the current phase and returns a `Phase`: a snapshot of that phase's notifications with `assert_contains`, `assert_contains_in_order` and `assert_does_not_contain`. Each phase starts after the previous sentinel, so notifications from a phase the SUT starts by itself are not lost.
- Added `NotificationTrace.clear()`, which discards the notifications recorded so far. It is for phases the test starts itself; call it before the action that starts the phase.
- Added `Timeout.wait_on(condition)`, which waits on a `threading.Condition` for at most the time remaining.
- Added a "Listening for notifications" section to README.md.

### Changed
- `Timeout`'s `poll_delay` argument is now optional (default `0.0`).
- When no reason is given, failure messages from `assert_eventually` and `wait_until` now start with `Expected:` instead of a blank line.

### Fixed
- asyncmatch can now be imported on Python 3.9.0 and 3.9.1. `Callable` now comes from `typing` instead of `collections.abc`, whose subscripted form fails inside `Union` on those versions (bpo-42195).
- Removed an unreachable fallback in `CallableProbe`'s description, which returned the placeholder `"Martin"`.
- README examples: the `GpioProbe` example now implements `describe_to` and `describe_mismatch`, and the README explains why a probe needs them. Fixed the `is_satified` typo in the `UsbDeviceProbe` example; without the fix, that probe raised `NotImplementedError`. Fixed syntax errors in several examples, including the `_led` helper's `state == "low":`.

## [0.1.0] - 2026-07-21

### Added
- Added Python packaging metadata in pyproject.toml so the project can be installed with pip.
- Added project URLs and runtime dependency metadata.
- Added installation instructions in README.md for installing from GitHub (branch, tag, and commit), plus editable local install.

### Changed
- Lowered minimum supported Python version from 3.10 to 3.9.
- Replaced Python 3.10 union type syntax with Python 3.9-compatible typing.Union in asyncmatch/assert_eventually.py.

### Fixed
- Ignored setuptools egg-info directories in .gitignore.
