"""
Operator authentication.

Single-operator model: one shared ADMIN_PASSWORD logs in and receives a signed
session token (HS256 JWT). Admin/mutating endpoints depend on `require_operator`;
the public investor catalogue and KYC submission stay open.

The JWT is implemented with the standard library (hmac/hashlib) so there's no
dependency on a native crypto extension.

Env:
  ADMIN_PASSWORD   the operator login password (required for login to work)
  JWT_SECRET       signing secret for session tokens (set a strong random value)
  JWT_TTL_HOURS    token lifetime in hours (default 12)
"""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException


def _secret() -> bytes:
    return os.environ.get("JWT_SECRET", "dev-insecure-change-me").encode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(message: bytes) -> str:
    return _b64url(hmac.new(_secret(), message, hashlib.sha256).digest())


def verify_password(password: str) -> bool:
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        # No password configured -> login disabled (fail closed).
        return False
    return hmac.compare_digest(password, expected)


def create_token(sub: str = "operator") -> str:
    ttl = int(os.environ.get("JWT_TTL_HOURS", "12"))
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + ttl * 3600}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    return f"{h}.{p}.{_sign(signing_input)}"


def decode_token(token: str) -> dict:
    try:
        h, p, sig = token.split(".")
    except ValueError:
        raise ValueError("Malformed token")
    expected_sig = _sign(f"{h}.{p}".encode())
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Bad signature")
    payload = json.loads(_b64url_decode(p))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def require_operator(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: require a valid operator bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing operator token")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
