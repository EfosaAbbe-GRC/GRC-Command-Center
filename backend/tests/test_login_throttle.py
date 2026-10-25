"""Login throttling (core.login_throttle). Pure unit tests with a fake clock: no stack, no Groq.

The HTTP-level 429 is deliberately not tested against a live stack: throttling a
real seeded account would lock it for 15 minutes and fail every later test.
"""
from core.login_throttle import LoginThrottle


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(**kw):
    clock = FakeClock()
    return LoginThrottle(clock=clock, **kw), clock


def test_allows_until_the_limit_then_throttles():
    t, _ = make(max_failures=5, window=900)
    for _ in range(4):
        t.record_failure("admin")
        assert t.retry_after("admin") == 0
    t.record_failure("admin")
    assert 0 < t.retry_after("admin") <= 901


def test_success_resets_the_counter():
    t, _ = make(max_failures=5)
    for _ in range(4):
        t.record_failure("admin")
    t.record_success("admin")
    t.record_failure("admin")
    assert t.retry_after("admin") == 0


def test_other_usernames_are_unaffected():
    t, _ = make(max_failures=5)
    for _ in range(5):
        t.record_failure("admin")
    assert t.retry_after("admin") > 0
    assert t.retry_after("analyst") == 0


def test_username_key_ignores_case_and_whitespace():
    t, _ = make(max_failures=5)
    for name in ("Admin", "ADMIN", " admin", "admin ", "admin"):
        t.record_failure(name)
    assert t.retry_after("admin") > 0


def test_window_expires_on_its_own():
    t, clock = make(max_failures=5, window=900)
    for _ in range(5):
        t.record_failure("admin")
    clock.now += 900
    assert t.retry_after("admin") == 0


def test_global_backstop_catches_username_spraying():
    t, _ = make(max_failures=5, global_max=50)
    for i in range(50):
        t.record_failure(f"user{i}")      # one failure each: no per-user limit reached
    assert t.retry_after("someone-new") > 0
