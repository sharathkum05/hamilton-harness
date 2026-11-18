"""Signing in to the dashboard with an admin user ID and a passcode.

The passcode is kept only as a scrypt hash. Signing in sets a cookie that holds
the user ID and an expiry, signed with a server secret, so the server keeps no
session table and a restart with the same secret keeps people signed in.

Failed attempts are counted per address, so a password cannot be guessed at
the speed of the network.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

COOKIE = "hamilton_admin"
# Short enough to type in front of an audience; set your own with HAMILTON_ADMIN_USER.
DEMO_USER = "admin"
MIN_PASSWORD = 8
SESSION_SECONDS = 12 * 3600
MAX_FAILURES = 10
FAILURE_WINDOW = 15 * 60

# scrypt's recommended interactive settings: about 16 MB and a few tens of ms.
_N, _R, _P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    """A salted scrypt hash, with its settings, as one string."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, _unb64(digest))


@dataclass(frozen=True)
class Credentials:
    """The one admin account. User IDs are compared without regard to case."""

    user: str
    password_hash: str

    @classmethod
    def from_password(cls, user: str, password: str) -> Credentials:
        return cls(user.strip().lower(), hash_password(password))

    def check(self, user: str, password: str) -> bool:
        # The hash is checked even for a wrong user ID, so timing does not reveal which was wrong.
        password_ok = check_password(password, self.password_hash)
        return password_ok and hmac.compare_digest(
            user.strip().lower().encode(), self.user.encode()
        )


def make_passcode() -> str:
    """Twelve random digits in three groups: easy to read out, hard to guess."""
    return "-".join(f"{secrets.randbelow(10_000):04d}" for _ in range(3))


class AdminLogin(NamedTuple):
    user: str
    # Empty when only a hash is kept: the passcode was changed in the dashboard.
    password: str
    # "env": set by whoever started the server, so never printed. "demo": made here.
    # "changed": set in the dashboard, kept as a hash in the state folder.
    source: Literal["env", "demo", "changed"]


def _configured_user() -> str:
    # HAMILTON_ADMIN_EMAIL is the older name, still read so existing set-ups keep working.
    for name in ("HAMILTON_ADMIN_USER", "HAMILTON_ADMIN_EMAIL"):
        value = os.environ.get(name, "").strip().lower()
        if value:
            return value
    return DEMO_USER


def admin_login(state: Path) -> AdminLogin:
    """The dashboard's admin user ID and passcode.

    HAMILTON_ADMIN_USER and HAMILTON_ADMIN_PASSWORD set your own. Without a
    passcode there, a demo one is made once and kept, readable only by you, in
    the state folder; a passcode changed in the dashboard replaces it.
    """
    user = _configured_user()
    from_env = os.environ.get("HAMILTON_ADMIN_PASSWORD", "")
    if from_env:
        if len(from_env) < MIN_PASSWORD:
            raise ValueError(f"HAMILTON_ADMIN_PASSWORD must be at least {MIN_PASSWORD} characters")
        return AdminLogin(user, from_env, "env")
    changed = state / ACCOUNT_FILE
    if changed.exists():
        return AdminLogin(user, "", "changed")
    path = state / "admin-password"
    if path.exists():
        return AdminLogin(user, path.read_text(encoding="utf-8").strip(), "demo")
    state.mkdir(parents=True, exist_ok=True)
    password = make_passcode()
    path.write_text(password, encoding="utf-8")
    path.chmod(0o600)
    return AdminLogin(user, password, "demo")


def sign_in_hint(login: AdminLogin) -> str:
    """One line telling the person at the terminal how to sign in."""
    passcode = {
        "env": "the one in HAMILTON_ADMIN_PASSWORD",
        "changed": "the one you set in the dashboard",
        "demo": login.password,
    }[login.source]
    return f"user ID {login.user}, passcode {passcode}"


ACCOUNT_FILE = "admin-account.json"


class Account:
    """The admin account a running server checks, and where a changed passcode goes.

    One Account is shared by every rep a server runs, so a passcode changed on
    one dashboard holds on all of them.
    """

    def __init__(
        self, credentials: Credentials, *, state: Path | None = None, fixed: str = ""
    ) -> None:
        self._credentials = credentials
        self._state = state
        # Why the passcode cannot be changed here, when it cannot.
        self.fixed = fixed if fixed or state else "this server was started with a fixed passcode"
        self._lock = threading.Lock()

    @classmethod
    def from_state(cls, state: Path) -> tuple[Account, AdminLogin]:
        login = admin_login(state)
        if login.source == "changed":
            saved = json.loads((state / ACCOUNT_FILE).read_text(encoding="utf-8"))
            credentials = Credentials(login.user, saved["passcode_hash"])
        else:
            credentials = Credentials.from_password(login.user, login.password)
        fixed = (
            "it is set by HAMILTON_ADMIN_PASSWORD; change it there" if login.source == "env" else ""
        )
        return cls(credentials, state=None if fixed else state, fixed=fixed), login

    @property
    def user(self) -> str:
        return self._credentials.user

    def check(self, user: str, passcode: str) -> bool:
        return self._credentials.check(user, passcode)

    def change(self, current: str, new: str) -> None:
        """Set a new passcode. ValueError says why one is refused."""
        if self.fixed:
            raise ValueError(f"the passcode cannot be changed here: {self.fixed}")
        with self._lock:
            if not check_password(current, self._credentials.password_hash):
                raise PermissionError("the current passcode is not right")
            if len(new) < MIN_PASSWORD:
                raise ValueError(f"a passcode needs at least {MIN_PASSWORD} characters")
            if new == current:
                raise ValueError("choose a passcode different from the current one")
            credentials = Credentials(self.user, hash_password(new))
            assert self._state is not None
            self._state.mkdir(parents=True, exist_ok=True)
            path = self._state / ACCOUNT_FILE
            path.write_text(
                json.dumps({"user": self.user, "passcode_hash": credentials.password_hash}),
                encoding="utf-8",
            )
            path.chmod(0o600)
            # The demo passcode in plain text is no longer the passcode, so it goes.
            (self._state / "admin-password").unlink(missing_ok=True)
            self._credentials = credentials


class SessionSigner:
    """Makes and checks the signed value kept in the sign-in cookie."""

    def __init__(self, secret: str, *, clock: Callable[[], float] = time.time) -> None:
        if len(secret) < 16:
            raise ValueError("the session secret must be at least 16 characters")
        self._key = secret.encode()
        self._clock = clock

    def _sign(self, payload: str) -> str:
        return _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())

    def issue(self, user: str, seconds: int = SESSION_SECONDS) -> str:
        payload = _b64(f"{user}|{int(self._clock()) + seconds}".encode())
        return f"{payload}.{self._sign(payload)}"

    def read(self, value: str | None) -> tuple[str, int] | None:
        """Who signed in and when the session ends, or None for a bad or expired cookie."""
        if not value or "." not in value:
            return None
        payload, signature = value.rsplit(".", 1)
        if not hmac.compare_digest(signature, self._sign(payload)):
            return None
        try:
            user, expires = _unb64(payload).decode().rsplit("|", 1)
            if int(expires) < self._clock():
                return None
        except ValueError:
            return None
        return user, int(expires)

    def verify(self, value: str | None) -> str | None:
        """The signed-in user ID, or None for a missing, forged or expired cookie."""
        session = self.read(value)
        return session[0] if session else None


class FailureCounter:
    """Failed sign-ins per address over a sliding window."""

    def __init__(
        self,
        *,
        limit: int = MAX_FAILURES,
        window: float = FAILURE_WINDOW,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit, self._window, self._clock = limit, window, clock
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = self._clock() - self._window
        recent = [at for at in self._failures.get(key, []) if at > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key)) >= self._limit

    def retry_after(self, key: str) -> int:
        """Seconds until a blocked address may try again; 0 when it is not blocked."""
        with self._lock:
            recent = self._recent(key)
            if len(recent) < self._limit:
                return 0
            # The window slides: one more try is allowed once the oldest counted failure ages out.
            return max(1, int(recent[-self._limit] + self._window - self._clock()) + 1)

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures[key] = [*self._recent(key), self._clock()]

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
