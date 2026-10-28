"""Keep track of the conversations open in the web widget.

A session pairs a harness Conversation with what the browser needs: the
transcript to redraw after a reload, a lock so one conversation handles one
message at a time, and the events of each turn for the inspector.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hamilton_harness.memory import Conversation


@dataclass
class Session:
    # Long and random: the id is the only thing protecting a transcript.
    id: str
    conversation: Conversation
    transcript: list[dict[str, str]] = field(default_factory=list)
    turns: list[list[dict[str, Any]]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_seen: float = 0.0

    def say(self, speaker: str, text: str) -> None:
        self.transcript.append({"from": speaker, "text": text})


class SessionStore:
    """In-memory sessions with a size cap and an idle timeout.

    Good for one process. Behind a load balancer, put this in a shared store.
    """

    def __init__(
        self,
        *,
        max_sessions: int = 500,
        idle_seconds: float = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max = max_sessions
        self._idle = idle_seconds
        self._clock = clock
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._sessions)

    def _expire(self) -> None:
        cutoff = self._clock() - self._idle
        stale = [key for key, session in self._sessions.items() if session.last_seen < cutoff]
        for key in stale:
            del self._sessions[key]

    def create(self, conversation: Conversation) -> Session:
        session = Session(secrets.token_urlsafe(24), conversation, last_seen=self._clock())
        with self._lock:
            self._expire()
            # Oldest first: when full, the conversation idle longest makes room.
            while len(self._sessions) >= self._max:
                self._sessions.popitem(last=False)
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            self._expire()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.last_seen = self._clock()
            self._sessions.move_to_end(session_id)
            return session


VISITOR_COOKIE = "hamilton_visitor"


class Visitors:
    """Which conversations each browser started.

    A public demo's dashboard shows each visitor only their own chats and
    orders, never what someone else typed. Kept in memory, oldest forgotten
    first, like the sessions themselves.
    """

    def __init__(self, *, max_visitors: int = 2000) -> None:
        self._seen: OrderedDict[str, set[str]] = OrderedDict()
        self._max = max_visitors
        self._lock = threading.Lock()

    def add(self, visitor: str, conversation_id: str) -> None:
        with self._lock:
            self._seen.setdefault(visitor, set()).add(conversation_id)
            self._seen.move_to_end(visitor)
            while len(self._seen) > self._max:
                self._seen.popitem(last=False)

    def conversations(self, visitor: str | None) -> set[str]:
        with self._lock:
            return set(self._seen.get(visitor or "", set()))
