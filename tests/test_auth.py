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


def test_credentials_compare_the_user_id_without_case():
    login = Credentials.from_password(" Admin@Example.com ", "pw-123456")
    assert login.user == "admin@example.com"
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


@pytest.fixture
def no_login_env(monkeypatch):
    for name in ("HAMILTON_ADMIN_USER", "HAMILTON_ADMIN_EMAIL", "HAMILTON_ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def test_a_demo_login_is_made_once_and_kept_private(tmp_path, no_login_env):
    from hamilton_harness.web.auth import DEMO_USER, admin_login, sign_in_hint

    first = admin_login(tmp_path)
    assert first.user == DEMO_USER == "admin" and first.source == "demo"
    assert admin_login(tmp_path) == first
    assert (tmp_path / "admin-password").stat().st_mode & 0o077 == 0
    assert sign_in_hint(first) == f"user ID admin, passcode {first.password}"


def test_a_demo_passcode_is_easy_to_read_out():
    import re

    from hamilton_harness.web.auth import make_passcode

    codes = {make_passcode() for _ in range(50)}
    assert all(re.fullmatch(r"\d{4}-\d{4}-\d{4}", code) for code in codes)
    assert len(codes) == 50


def test_a_login_from_the_environment_wins_and_is_never_printed(
    tmp_path, no_login_env, monkeypatch
):
    from hamilton_harness.web.auth import admin_login, sign_in_hint

    monkeypatch.setenv("HAMILTON_ADMIN_USER", "Owner")
    monkeypatch.setenv("HAMILTON_ADMIN_PASSWORD", "a-long-password")
    login = admin_login(tmp_path)
    assert login == ("owner", "a-long-password", "env")
    assert "a-long-password" not in sign_in_hint(login)
    assert not (tmp_path / "admin-password").exists()
    monkeypatch.setenv("HAMILTON_ADMIN_PASSWORD", "short")
    with pytest.raises(ValueError, match="at least 8"):
        admin_login(tmp_path)


def test_the_older_email_setting_still_names_the_user(tmp_path, no_login_env, monkeypatch):
    from hamilton_harness.web.auth import admin_login

    monkeypatch.setenv("HAMILTON_ADMIN_EMAIL", "owner@shop.com")
    assert admin_login(tmp_path).user == "owner@shop.com"
    monkeypatch.setenv("HAMILTON_ADMIN_USER", "owner")
    assert admin_login(tmp_path).user == "owner"


def test_a_changed_passcode_is_kept_as_a_hash_and_replaces_the_demo_one(tmp_path, no_login_env):
    from hamilton_harness.web.auth import ACCOUNT_FILE, Account, sign_in_hint

    account, login = Account.from_state(tmp_path)
    assert account.check("admin", login.password)
    account.change(login.password, "a brand new passcode")
    assert account.check("ADMIN", "a brand new passcode")
    assert not account.check("admin", login.password)
    saved = (tmp_path / ACCOUNT_FILE).read_text(encoding="utf-8")
    assert "a brand new passcode" not in saved and "scrypt$" in saved
    assert (tmp_path / ACCOUNT_FILE).stat().st_mode & 0o077 == 0
    assert not (tmp_path / "admin-password").exists()

    # After a restart the new passcode still holds, and is not printed.
    again, relogin = Account.from_state(tmp_path)
    assert again.check("admin", "a brand new passcode")
    assert relogin.source == "changed"
    assert sign_in_hint(relogin) == "user ID admin, passcode the one you set in the dashboard"


@pytest.mark.parametrize(
    ("current", "new", "error", "message"),
    [
        ("wrong-passcode", "another passcode", PermissionError, "not right"),
        (None, "short", ValueError, "at least 8"),
        (None, None, ValueError, "different"),
    ],
)
def test_a_passcode_change_is_refused_with_the_reason(
    tmp_path, no_login_env, current, new, error, message
):
    from hamilton_harness.web.auth import Account

    account, login = Account.from_state(tmp_path)
    with pytest.raises(error, match=message):
        account.change(current or login.password, new or login.password)
    assert account.check("admin", login.password)


def test_a_passcode_from_the_environment_cannot_be_changed_here(
    tmp_path, no_login_env, monkeypatch
):
    from hamilton_harness.web.auth import Account

    monkeypatch.setenv("HAMILTON_ADMIN_PASSWORD", "a-long-password")
    account, _ = Account.from_state(tmp_path)
    assert "HAMILTON_ADMIN_PASSWORD" in account.fixed
    with pytest.raises(ValueError, match="change it there"):
        account.change("a-long-password", "another long one")


def test_a_lockout_says_how_long_it_lasts():
    now = [100.0]
    counter = FailureCounter(limit=2, window=60, clock=lambda: now[0])
    assert counter.retry_after("a") == 0
    counter.fail("a")
    now[0] += 10
    counter.fail("a")
    assert 50 <= counter.retry_after("a") <= 51
    now[0] += 51
    assert counter.retry_after("a") == 0


def test_a_session_cookie_says_when_it_ends():
    now = [1000.0]
    signer = SessionSigner("a-secret-of-some-length", clock=lambda: now[0])
    assert signer.read(signer.issue("admin", seconds=60)) == ("admin", 1060)
    assert signer.read("nonsense") is None
