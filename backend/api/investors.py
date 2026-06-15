"""
Investor KYC / accreditation API.

Flow with a licensed transfer agent (TA):
  1. Investor connects wallet and submits KYC info        → POST /submit (pending)
  2. TA verifies identity + accreditation off-chain, then
     approves via webhook                                 → POST /{address}/approve
     (optionally pushes the on-chain whitelist if the platform holds the agent key)
  3. App/website gate buying on                           → GET  /{address}/status
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import Investor, get_db
from services.onchain import set_whitelisted
from services.auth import require_operator

router = APIRouter()


class KycSubmit(BaseModel):
    wallet_address: str
    full_name: str
    email: str
    phone: Optional[str] = None
    country: Optional[str] = None
    accredited: bool = False
    accreditation_method: Optional[str] = None


class ApprovePayload(BaseModel):
    approved: bool = True
    accredited: Optional[bool] = None
    transfer_agent_id: Optional[str] = None
    lockup_until: Optional[datetime] = None
    notes: Optional[str] = None


def _fmt(inv: Investor) -> dict:
    return {
        "wallet_address": inv.wallet_address,
        "full_name": inv.full_name,
        "email": inv.email,
        "country": inv.country,
        "kyc_status": inv.kyc_status,
        "accredited": inv.accredited,
        "accreditation_method": inv.accreditation_method,
        "transfer_agent_id": inv.transfer_agent_id,
        "onchain_whitelisted": inv.onchain_whitelisted,
        "lockup_until": inv.lockup_until.isoformat() if inv.lockup_until else None,
        "can_invest": inv.kyc_status == "approved" and inv.accredited,
        "approved_at": inv.approved_at.isoformat() if inv.approved_at else None,
    }


@router.post("/submit")
def submit_kyc(body: KycSubmit, db: Session = Depends(get_db)):
    """Investor submits (or updates) their KYC application. Status -> pending."""
    addr = body.wallet_address.lower()
    inv = db.query(Investor).filter(Investor.wallet_address == addr).first()
    if not inv:
        inv = Investor(wallet_address=addr)
        db.add(inv)
    inv.full_name = body.full_name
    inv.email = body.email
    inv.phone = body.phone
    inv.country = body.country
    inv.accredited = body.accredited
    inv.accreditation_method = body.accreditation_method
    # Re-submission resets to pending unless already approved
    if inv.kyc_status != "approved":
        inv.kyc_status = "pending"
    db.commit()
    db.refresh(inv)
    return _fmt(inv)


@router.get("/{wallet_address}/status")
def kyc_status(wallet_address: str, db: Session = Depends(get_db)):
    """Public gate check used by the app/website. Unknown wallet = not started."""
    inv = db.query(Investor).filter(Investor.wallet_address == wallet_address.lower()).first()
    if not inv:
        return {
            "wallet_address": wallet_address.lower(),
            "kyc_status": "not_started",
            "can_invest": False,
        }
    return _fmt(inv)


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
    if not expected or x_ta_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid transfer-agent secret")

    inv = db.query(Investor).filter(Investor.wallet_address == wallet_address.lower()).first()
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
        tx = set_whitelisted(inv.wallet_address, True)   # no-op if not configured
        inv.onchain_whitelisted = tx is not None
        result = {"approved": True, "onchain_tx": tx}
    else:
        inv.kyc_status = "rejected"
        set_whitelisted(inv.wallet_address, False)
        inv.onchain_whitelisted = False
        result = {"approved": False}

    db.commit()
    db.refresh(inv)
    return {**result, "investor": _fmt(inv)}


@router.get("/", dependencies=[Depends(require_operator)])
def list_investors(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Ops view: list investors, optionally filtered by KYC status."""
    q = db.query(Investor)
    if status:
        q = q.filter(Investor.kyc_status == status)
    return {"investors": [_fmt(i) for i in q.order_by(Investor.created_at.desc()).all()]}
