"""Signing in to the dashboard with an email and a password.

The password is kept only as a scrypt hash. Signing in sets a cookie that holds
the email and an expiry, signed with a server secret, so the server keeps no
session table and a restart with the same secret keeps people signed in.

Failed attempts are counted per address, so a password cannot be guessed at
the speed of the network.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

COOKIE = "hamilton_admin"
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
    """The one admin account. Emails are compared without regard to case."""

    email: str
    password_hash: str

    @classmethod
    def from_password(cls, email: str, password: str) -> Credentials:
        return cls(email.strip().lower(), hash_password(password))

    def check(self, email: str, password: str) -> bool:
        # The hash is checked even for a wrong email, so timing does not reveal which was wrong.
        password_ok = check_password(password, self.password_hash)
        return password_ok and hmac.compare_digest(
            email.strip().lower().encode(), self.email.encode()
        )


class SessionSigner:
    """Makes and checks the signed value kept in the sign-in cookie."""

    def __init__(self, secret: str, *, clock: Callable[[], float] = time.time) -> None:
        if len(secret) < 16:
            raise ValueError("the session secret must be at least 16 characters")
        self._key = secret.encode()
        self._clock = clock

    def _sign(self, payload: str) -> str:
        return _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())

    def issue(self, email: str, seconds: int = SESSION_SECONDS) -> str:
        payload = _b64(f"{email}|{int(self._clock()) + seconds}".encode())
        return f"{payload}.{self._sign(payload)}"

    def verify(self, value: str | None) -> str | None:
        """The signed-in email, or None for a missing, forged or expired cookie."""
        if not value or "." not in value:
            return None
        payload, signature = value.rsplit(".", 1)
        if not hmac.compare_digest(signature, self._sign(payload)):
            return None
        try:
            email, expires = _unb64(payload).decode().rsplit("|", 1)
            if int(expires) < self._clock():
                return None
        except ValueError:
            return None
        return email


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

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures[key] = [*self._recent(key), self._clock()]

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
