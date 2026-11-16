"""
Investor KYC / accreditation API.

Flow with a licensed transfer agent (TA):
  1. Investor signs in with their wallet (see /api/auth/wallet/*) and submits
     KYC info                                             → POST /submit (pending)
  2. TA verifies identity + accreditation off-chain, then
     approves via webhook                                 → POST /{address}/approve
     (optionally pushes the on-chain whitelist if the platform holds the agent key)
  3. App/website gate buying on                           → GET  /{address}/status

Access rules:
  - /submit and /me require an investor token for that wallet, so nobody can
    file or overwrite an application for a wallet they don't control.
  - /status is public but returns ONLY the gate flags — never name, email or
    other personal data.
  - Accreditation that counts is set by the transfer agent. What the investor
    ticks on the form is stored separately as a self-attestation.
"""

import hmac
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import Investor, get_db
from services.onchain import set_whitelisted
from services.auth import require_operator, require_investor, assert_wallet, normalize_wallet

router = APIRouter()


class KycSubmit(BaseModel):
    wallet_address: str
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=50)
    country: Optional[str] = Field(default=None, max_length=80)
    accredited: bool = False                     # investor's SELF-attestation
    accreditation_method: Optional[str] = Field(default=None, max_length=120)


class ApprovePayload(BaseModel):
    approved: bool = True
    accredited: Optional[bool] = None            # the TA's VERIFIED determination
    transfer_agent_id: Optional[str] = None
    lockup_until: Optional[datetime] = None
    notes: Optional[str] = None


def _can_invest(inv: Investor) -> bool:
    return inv.kyc_status == "approved" and bool(inv.accredited)


def _public(inv: Investor) -> dict:
    """Safe to return to anyone: gate flags only, no personal data."""
    return {
        "wallet_address": inv.wallet_address,
        "kyc_status": inv.kyc_status,
        "can_invest": _can_invest(inv),
    }


def _full(inv: Investor) -> dict:
    """Full record — only for the investor themselves or the operator."""
    return {
        **_public(inv),
        "full_name": inv.full_name,
        "email": inv.email,
        "country": inv.country,
        "accredited": bool(inv.accredited),
        "accredited_self_attested": bool(inv.accredited_self_attested),
        "accreditation_method": inv.accreditation_method,
        "transfer_agent_id": inv.transfer_agent_id,
        "onchain_whitelisted": inv.onchain_whitelisted,
        "lockup_until": inv.lockup_until.isoformat() if inv.lockup_until else None,
        "approved_at": inv.approved_at.isoformat() if inv.approved_at else None,
    }


@router.post("/submit")
def submit_kyc(
    body: KycSubmit,
    token_wallet: str = Depends(require_investor),
    db: Session = Depends(get_db),
):
    """Investor submits (or updates) their KYC application. Status -> pending."""
    addr = normalize_wallet(body.wallet_address)
    assert_wallet(token_wallet, addr)

    inv = db.query(Investor).filter(Investor.wallet_address == addr).first()
    if inv and inv.kyc_status == "approved":
        # A verified record is the transfer agent's; it can't be self-edited.
        raise HTTPException(
            status_code=409,
            detail="This wallet is already verified. Contact support to update your details.",
        )
    if not inv:
        inv = Investor(wallet_address=addr)
        db.add(inv)

    inv.full_name = body.full_name.strip()
    inv.email = body.email.strip()
    inv.phone = body.phone
    inv.country = body.country
    inv.accredited_self_attested = body.accredited
    inv.accreditation_method = body.accreditation_method
    inv.kyc_status = "pending"
    db.commit()
    db.refresh(inv)
    return _full(inv)


@router.get("/me")
def my_record(token_wallet: str = Depends(require_investor), db: Session = Depends(get_db)):
    """The signed-in investor's own full record."""
    inv = db.query(Investor).filter(Investor.wallet_address == token_wallet).first()
    if not inv:
        return {"wallet_address": token_wallet, "kyc_status": "not_started", "can_invest": False}
    return _full(inv)


@router.get("/{wallet_address}/status")
def kyc_status(wallet_address: str, db: Session = Depends(get_db)):
    """Public gate check used by the app/website. Unknown wallet = not started."""
    addr = normalize_wallet(wallet_address)
    inv = db.query(Investor).filter(Investor.wallet_address == addr).first()
    if not inv:
        return {"wallet_address": addr, "kyc_status": "not_started", "can_invest": False}
    return _public(inv)


@router.post("/{wallet_address}/approve")
def approve_investor(
    wallet_address: str,
    body: ApprovePayload,
    db: Session = Depends(get_db),
    x_ta_secret: Optional[str] = Header(default=None),
):
    """Transfer-agent webhook: approve/reject an investor. Protected by the
    TA_WEBHOOK_SECRET shared secret (set it in the environment)."""
    expected = os.environ.get("TA_WEBHOOK_SECRET", "")
    if not expected or not x_ta_secret or not hmac.compare_digest(
        x_ta_secret.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid transfer-agent secret")

    addr = normalize_wallet(wallet_address)
    inv = db.query(Investor).filter(Investor.wallet_address == addr).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investor not found")

    if body.accredited is not None:
        inv.accredited = body.accredited
    if body.transfer_agent_id:
        inv.transfer_agent_id = body.transfer_agent_id
    if body.lockup_until:
        inv.lockup_until = body.lockup_until
    if body.notes:
        inv.notes = body.notes

    if body.approved:
        inv.kyc_status = "approved"
        inv.approved_at = datetime.utcnow()
        # Only whitelist on-chain when the investor can actually invest.
        tx = set_whitelisted(inv.wallet_address, True) if _can_invest(inv) else None
        inv.onchain_whitelisted = tx is not None
        result = {"approved": True, "onchain_tx": tx}
    else:
        inv.kyc_status = "rejected"
        inv.accredited = False
        set_whitelisted(inv.wallet_address, False)
        inv.onchain_whitelisted = False
        result = {"approved": False}

    db.commit()
    db.refresh(inv)
    return {**result, "investor": _full(inv)}


@router.get("/", dependencies=[Depends(require_operator)])
def list_investors(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Ops view: list investors, optionally filtered by KYC status."""
    q = db.query(Investor)
    if status:
        q = q.filter(Investor.kyc_status == status)
    return {"investors": [_full(i) for i in q.order_by(Investor.created_at.desc()).all()]}
