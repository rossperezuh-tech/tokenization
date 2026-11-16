"""
Authentication for the two kinds of caller.

OPERATOR  — one shared ADMIN_PASSWORD logs in and receives a signed session
            token with role "operator". Admin/mutating endpoints depend on
            `require_operator`.

INVESTOR  — proves control of a wallet by signing a server-issued challenge
            (personal_sign). The server recovers the signer address and issues a
            short-lived token with role "investor" bound to that wallet. Anything
            that reads or writes one investor's data depends on
            `require_investor` and compares the token's wallet to the request.

Tokens are HS256 JWTs implemented with the standard library, so there is no
dependency on a native crypto extension. The role claim is always checked: an
investor token can never satisfy `require_operator`.

Env:
  ADMIN_PASSWORD   operator login password (login is disabled when unset)
  JWT_SECRET       signing secret. When unset a random per-process secret is
                   used, so tokens stop working on restart instead of being
                   forgeable with a known default.
  JWT_TTL_HOURS    operator token lifetime in hours (default 12)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

_FALLBACK_SECRET = secrets.token_bytes(32)
_warned_secret = False

WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
CHALLENGE_TTL_SECONDS = 600
INVESTOR_TOKEN_TTL_SECONDS = 3600


def _secret() -> bytes:
    global _warned_secret
    configured = os.environ.get("JWT_SECRET", "")
    if configured:
        return configured.encode()
    if not _warned_secret:
        logger.warning(
            "JWT_SECRET is not set — using a random per-process secret. "
            "Sessions will not survive a restart. Set JWT_SECRET in production."
        )
        _warned_secret = True
    return _FALLBACK_SECRET


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(message: bytes) -> str:
    return _b64url(hmac.new(_secret(), message, hashlib.sha256).digest())


# ── tokens ───────────────────────────────────────────────────────────────

def _encode(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    return f"{h}.{p}.{_sign(f'{h}.{p}'.encode())}"


def create_token(sub: str = "operator") -> str:
    ttl = int(os.environ.get("JWT_TTL_HOURS", "12"))
    now = int(time.time())
    return _encode({"sub": sub, "role": "operator", "iat": now, "exp": now + ttl * 3600})


def create_investor_token(wallet: str) -> str:
    now = int(time.time())
    return _encode({
        "sub": wallet.lower(), "role": "investor",
        "iat": now, "exp": now + INVESTOR_TOKEN_TTL_SECONDS,
    })


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


def _bearer(authorization: str) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return decode_token(authorization.split(" ", 1)[1])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_operator(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: require a valid OPERATOR token."""
    payload = _bearer(authorization)
    if payload.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Operator access required")
    return payload


def require_investor(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: require a valid INVESTOR token. Returns the wallet
    address (lower-case) the token is bound to."""
    payload = _bearer(authorization)
    if payload.get("role") != "investor" or not payload.get("sub"):
        raise HTTPException(status_code=403, detail="Investor session required")
    return payload["sub"]


def assert_wallet(token_wallet: str, requested_wallet: str) -> None:
    """Reject a request that targets a wallet other than the signed-in one."""
    if token_wallet.lower() != requested_wallet.lower():
        raise HTTPException(status_code=403, detail="Token does not match this wallet")


# ── operator password + brute-force throttle ─────────────────────────────

def verify_password(password: str) -> bool:
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        # No password configured -> login disabled (fail closed).
        return False
    return hmac.compare_digest(password.encode(), expected.encode())


_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 8
_failures: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login_allowed(request: Request) -> None:
    """Raise 429 once a client has too many recent failed logins. In-memory, so
    it resets on restart and is per-process — a speed bump, not a WAF."""
    q = _failures[_client_key(request)]
    cutoff = time.time() - _LOGIN_WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= _LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed attempts — try again later")


def record_login_failure(request: Request) -> None:
    _failures[_client_key(request)].append(time.time())


def clear_login_failures(request: Request) -> None:
    _failures.pop(_client_key(request), None)


# ── investor wallet challenge ────────────────────────────────────────────

def normalize_wallet(wallet: str) -> str:
    if not wallet or not WALLET_RE.match(wallet):
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    return wallet.lower()


def _challenge_mac(wallet: str, issued_at: int) -> str:
    return _sign(f"challenge|{wallet}|{issued_at}".encode())[:32]


def build_challenge(wallet: str) -> dict:
    """A message for the wallet to sign. Stateless: the nonce is an HMAC over
    the wallet + issue time, so the server can re-derive and check it."""
    wallet = normalize_wallet(wallet)
    issued_at = int(time.time())
    nonce = _challenge_mac(wallet, issued_at)
    message = (
        "Vesta Invest — sign in\n\n"
        "Sign this message to prove you control this wallet. "
        "It does not send a transaction or cost gas.\n\n"
        f"Wallet: {wallet}\n"
        f"Issued: {issued_at}\n"
        f"Nonce: {nonce}"
    )
    return {"wallet_address": wallet, "issued_at": issued_at, "nonce": nonce, "message": message}


def verify_challenge(wallet: str, issued_at: int, nonce: str, signature: str) -> str:
    """Check the signed challenge and return the verified wallet (lower-case).

    Verifies with ecrecover, so it supports externally-owned accounts (MetaMask,
    Coinbase Wallet, thirdweb in-app wallets in their default EOA mode). Smart
    contract accounts sign via EIP-1271 and would need an on-chain check added.
    """
    wallet = normalize_wallet(wallet)
    age = int(time.time()) - int(issued_at)
    if age < -60 or age > CHALLENGE_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="Challenge expired — request a new one")
    if not hmac.compare_digest(nonce, _challenge_mac(wallet, int(issued_at))):
        raise HTTPException(status_code=401, detail="Invalid challenge")

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        raise HTTPException(status_code=503, detail="Wallet verification is not available on this server")

    message = (
        "Vesta Invest — sign in\n\n"
        "Sign this message to prove you control this wallet. "
        "It does not send a transaction or cost gas.\n\n"
        f"Wallet: {wallet}\n"
        f"Issued: {int(issued_at)}\n"
        f"Nonce: {nonce}"
    )
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid signature")
    if recovered.lower() != wallet:
        raise HTTPException(status_code=401, detail="Signature does not match this wallet")
    return wallet
