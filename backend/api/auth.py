from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from services.auth import (
    verify_password, create_token, require_operator,
    check_login_allowed, record_login_failure, clear_login_failures,
    build_challenge, verify_challenge, create_investor_token,
)

router = APIRouter()


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request):
    check_login_allowed(request)
    if not verify_password(body.password):
        record_login_failure(request)
        raise HTTPException(status_code=401, detail="Invalid password")
    clear_login_failures(request)
    return {"token": create_token(), "token_type": "bearer"}


@router.get("/me")
def me(_=Depends(require_operator)):
    return {"ok": True, "role": "operator"}


# ── investor wallet sign-in ──────────────────────────────────────────────

class WalletVerifyBody(BaseModel):
    wallet_address: str
    issued_at: int
    nonce: str
    signature: str


@router.get("/wallet/challenge/{wallet_address}")
def wallet_challenge(wallet_address: str):
    """Step 1: get the message the wallet must sign."""
    return build_challenge(wallet_address)


@router.post("/wallet/verify")
def wallet_verify(body: WalletVerifyBody):
    """Step 2: submit the signature, receive a short-lived investor token."""
    wallet = verify_challenge(body.wallet_address, body.issued_at, body.nonce, body.signature)
    return {"token": create_investor_token(wallet), "token_type": "bearer", "wallet_address": wallet}
