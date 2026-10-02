from datetime import timedelta

import pytest
from jose import JWTError

from app.core.jwt import create_access_token, decode_access_token
from app.core.security import hash_password, needs_rehash, verify_password


def test_password_is_hashed_with_argon2id():
    hashed = hash_password("sekret")

    assert hashed.startswith("$argon2id$")
    assert "sekret" not in hashed
    assert not needs_rehash(hashed)


def test_same_password_gets_a_different_hash_each_time():
    assert hash_password("sekret") != hash_password("sekret")


def test_verify_password():
    hashed = hash_password("sekret")

    assert verify_password("sekret", hashed)
    assert not verify_password("inne", hashed)


def test_verify_password_rejects_a_malformed_hash():
    assert not verify_password("sekret", "not-a-hash")


def test_token_round_trip():
    token = create_access_token({"sub": "abc"})

    assert decode_access_token(token)["sub"] == "abc"


def test_expired_token_is_rejected():
    token = create_access_token({"sub": "abc"}, expires_delta=timedelta(seconds=-1))

    with pytest.raises(JWTError):
        decode_access_token(token)
