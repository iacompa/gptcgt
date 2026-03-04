import time

import jwt
import pytest

from src.auth.token_validation import verify_access_token


def test_verify_access_token_hs256_success():
    secret = "x" * 32
    token = jwt.encode(
        {
            "sub": "user_123",
            "email": "dev@example.com",
            "exp": int(time.time()) + 60,
        },
        secret,
        algorithm="HS256",
    )

    payload = verify_access_token(token, hs256_secret=secret)
    assert payload["sub"] == "user_123"
    assert payload["email"] == "dev@example.com"


def test_verify_access_token_hs256_without_secret_fails():
    secret = "x" * 32
    token = jwt.encode(
        {
            "sub": "user_123",
            "exp": int(time.time()) + 60,
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        verify_access_token(token, hs256_secret=None)
