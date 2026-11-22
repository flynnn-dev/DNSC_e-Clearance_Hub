"""Password hashes can be checked without storing the password."""

from app.security.passwords import hash_password, verify_password


def test_hash_verifies_the_same_password():
    stored = hash_password("correct horse battery")
    assert "correct horse battery" not in stored
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong", stored)


def test_tampered_hash_is_rejected():
    assert not verify_password("secret", "not-a-hash")
