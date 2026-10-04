from hamilton_harness.memory import Conversation
from hamilton_harness.web.sessions import SessionStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_ids_are_long_and_distinct():
    store = SessionStore()
    first, second = store.create(Conversation()), store.create(Conversation())
    assert first.id != second.id
    assert len(first.id) >= 32


def test_get_returns_the_same_session():
    store = SessionStore()
    session = store.create(Conversation())
    session.say("customer", "hi")
    assert store.get(session.id).transcript == [{"from": "customer", "text": "hi"}]
    assert store.get("unknown") is None


def test_idle_sessions_expire():
    clock = Clock()
    store = SessionStore(idle_seconds=60, clock=clock)
    session = store.create(Conversation())
    clock.now = 59
    assert store.get(session.id) is not None
    clock.now = 59 + 61
    assert store.get(session.id) is None


def test_activity_keeps_a_session_alive():
    clock = Clock()
    store = SessionStore(idle_seconds=60, clock=clock)
    session = store.create(Conversation())
    for moment in (50, 100, 150):
        clock.now = moment
        assert store.get(session.id) is not None


def test_the_longest_idle_session_makes_room_when_full():
    store = SessionStore(max_sessions=2)
    first, second = store.create(Conversation()), store.create(Conversation())
    store.get(first.id)
    third = store.create(Conversation())
    assert len(store) == 2
    assert store.get(second.id) is None
    assert store.get(first.id) is not None
    assert store.get(third.id) is not None
