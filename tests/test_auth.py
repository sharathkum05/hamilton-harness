import pytest

from hamilton_harness.web.auth import (
    Credentials,
    FailureCounter,
    SessionSigner,
    check_password,
    hash_password,
)


def test_a_password_is_kept_only_as_a_salted_hash():
    stored = hash_password("correct horse")
    assert "correct horse" not in stored
    assert stored.startswith("scrypt$")
    assert check_password("correct horse", stored)
    assert not check_password("correct hors", stored)
    # Same password, new salt: two hashes never match each other.
    assert hash_password("correct horse") != stored


@pytest.mark.parametrize("stored", ["", "plain-text", "md5$abc", "scrypt$x$8$1$aa$bb"])
def test_a_damaged_hash_never_lets_anyone_in(stored):
    assert not check_password("anything", stored)


def test_credentials_compare_the_email_without_case():
    login = Credentials.from_password(" Admin@Example.com ", "pw-123456")
    assert login.email == "admin@example.com"
    assert login.check("ADMIN@example.com", "pw-123456")
    assert not login.check("someone@example.com", "pw-123456")
    assert not login.check("admin@example.com", "wrong")


def test_a_session_cookie_names_who_signed_in_until_it_expires():
    now = [1000.0]
    signer = SessionSigner("a-secret-of-some-length", clock=lambda: now[0])
    value = signer.issue("admin@example.com", seconds=60)
    assert signer.verify(value) == "admin@example.com"
    now[0] += 61
    assert signer.verify(value) is None


def test_a_session_cookie_cannot_be_forged_or_moved_between_servers():
    signer = SessionSigner("a-secret-of-some-length")
    value = signer.issue("admin@example.com")
    payload, signature = value.rsplit(".", 1)
    assert signer.verify(f"{payload}.{signature[:-2]}xx") is None
    assert signer.verify(payload) is None
    assert signer.verify("") is None
    assert SessionSigner("another-secret-entirely").verify(value) is None


def test_a_short_secret_is_refused():
    with pytest.raises(ValueError):
        SessionSigner("short")


def test_failures_block_an_address_and_wear_off():
    now = [0.0]
    counter = FailureCounter(limit=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        assert not counter.blocked("1.2.3.4")
        counter.fail("1.2.3.4")
    assert counter.blocked("1.2.3.4")
    assert not counter.blocked("5.6.7.8")
    now[0] += 61
    assert not counter.blocked("1.2.3.4")


def test_a_successful_sign_in_clears_the_count():
    counter = FailureCounter(limit=2, window=60)
    counter.fail("a")
    counter.clear("a")
    counter.fail("a")
    assert not counter.blocked("a")
