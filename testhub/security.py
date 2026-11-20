"""Hand-rolled HS256 JWT + RBAC (demo grade, no external auth service)."""
import base64, hashlib, hmac, json, time, functools
from flask import request, jsonify
from . import config
from .db import connect


def _b64e(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(username, role, ttl=7200):
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": username, "role": role, "iat": int(time.time()), "exp": int(time.time()) + ttl}
    seg = _b64e(json.dumps(header, separators=(",", ":")).encode()) + "." +           _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(config.SECRET.encode(), seg.encode(), hashlib.sha256).digest())
    return seg + "." + sig


def parse_token(token):
    try:
        seg, sig = token.rsplit(".", 1)
        expect = _b64e(hmac.new(config.SECRET.encode(), seg.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(_b64d(seg.split(".")[1]))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def authenticate():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return parse_token(auth[7:])


def require_role(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            user = authenticate()
            if not user:
                return jsonify({"code": 401, "msg": "unauthorized"}), 401
            if user.get("role") not in roles:
                return jsonify({"code": 403, "msg": "forbidden"}), 403
            return fn(*a, **kw)
        return wrap
    return deco
