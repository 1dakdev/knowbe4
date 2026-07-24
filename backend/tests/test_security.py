import pytest
from jose import jwt

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_secret,
    verify_secret,
)
from app.config import get_settings


def test_hash_and_verify_secret_roundtrip():
    hashed = hash_secret("1234")
    assert hashed != "1234"
    assert verify_secret("1234", hashed) is True
    assert verify_secret("wrong", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="42", role="teacher", expires_minutes=10)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "teacher"


def test_decode_rejects_tampered_token():
    token = create_access_token(subject="42", role="teacher", expires_minutes=10)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.JWTError):
        decode_access_token(tampered)


def test_create_access_token_with_extra_claims():
    token = create_access_token(
        subject="7", role="student", expires_minutes=10, extra_claims={"class_id": 3}
    )
    payload = decode_access_token(token)
    assert payload["class_id"] == 3
