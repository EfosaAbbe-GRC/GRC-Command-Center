"""Login throttling: temporary, per username (OWASP: throttle, don't hard-lock).

Keyed on the username, not the client IP: behind Docker Desktop's NAT every
client arrives from the same bridge gateway address, so an IP key would be one
global bucket. A throttle that expires on its own means nobody can lock the
admin out indefinitely by failing on purpose.

In-memory, which is correct only because the backend runs a single worker
(Dockerfile.backend: --workers 1). More workers would need a shared store.
"""
import threading
import time
from collections import deque

MAX_FAILURES = 5              # per username, within the window
WINDOW_SECONDS = 15 * 60
GLOBAL_MAX_FAILURES = 50      # across all usernames: catches spraying many usernames
MAX_TRACKED_USERNAMES = 10_000


class LoginThrottle:
    def __init__(self, max_failures=MAX_FAILURES, window=WINDOW_SECONDS,
                 global_max=GLOBAL_MAX_FAILURES, clock=time.monotonic):
        self.max_failures = max_failures
        self.window = window
        self.global_max = global_max
        self.clock = clock
        self._fails: dict[str, deque] = {}
        self._all: deque = deque()
        self._lock = threading.Lock()

    @staticmethod
    def _key(username: str) -> str:
        return (username or "").strip().lower()

    def _prune(self, q: deque, now: float) -> None:
        while q and now - q[0] >= self.window:
            q.popleft()

    def retry_after(self, username: str) -> int:
        """Seconds until this username may try again; 0 means allowed now."""
        now = self.clock()
        key = self._key(username)
        with self._lock:
            waits = []
            q = self._fails.get(key)
            if q is not None:
                self._prune(q, now)
                if not q:
                    del self._fails[key]
                elif len(q) >= self.max_failures:
                    waits.append(q[0] + self.window - now)
            self._prune(self._all, now)
            if len(self._all) >= self.global_max:
                waits.append(self._all[0] + self.window - now)
            return int(max(waits)) + 1 if waits else 0

    def record_failure(self, username: str) -> None:
        now = self.clock()
        key = self._key(username)
        with self._lock:
            if key not in self._fails and len(self._fails) >= MAX_TRACKED_USERNAMES:
                for k in list(self._fails):
                    self._prune(self._fails[k], now)
                    if not self._fails[k]:
                        del self._fails[k]
            self._fails.setdefault(key, deque()).append(now)
            self._all.append(now)

    def record_success(self, username: str) -> None:
        with self._lock:
            self._fails.pop(self._key(username), None)


login_throttle = LoginThrottle()
