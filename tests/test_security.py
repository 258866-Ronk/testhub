import time
from testhub.security import make_token, parse_token


def test_roundtrip():
    t = make_token("op", "OPERATOR")
    p = parse_token(t)
    assert p and p["sub"] == "op" and p["role"] == "OPERATOR"


def test_tamper_rejected():
    t = make_token("op", "OPERATOR")
    assert parse_token(t + "x") is None
