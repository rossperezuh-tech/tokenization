"""
Subscription agreement e-sign API.

Investor flow:
  1. GET  /agreement/{offering_id}   → generated agreement text + sha256 to review
  2. POST /sign                      → records the clickwrap signature (requires
                                       KYC-approved wallet; hash must match)
  3. GET  /status/{offering_id}/{wallet} → gate for the app's buy button

Operator flow:
  - GET  /                (list, filterable)
  - POST /{id}/countersign
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import Investor, Subscription, TokenOffering, get_db
from services.auth import require_operator, require_investor, assert_wallet, normalize_wallet
from services.docgen import generate_subscription_agreement

router = APIRouter()


class SignBody(BaseModel):
    offering_id: int
    wallet_address: str
    investor_name: str = Field(min_length=2, max_length=200)
    investor_email: Optional[str] = Field(default=None, max_length=200)
    token_amount: float = Field(gt=0)
    signature_name: str = Field(min_length=2, max_length=200)
    consent: bool
    agreement_sha256: str   # hash of the text the investor reviewed


def _fmt(s: Subscription) -> dict:
    return {
        "id": s.id,
        "offering_id": s.offering_id,
        "wallet_address": s.wallet_address,
        "investor_name": s.investor_name,
        "token_amount": s.token_amount,
        "usd_amount": s.usd_amount,
        "status": s.status,
        "agreement_sha256": s.agreement_sha256,
        "signed_at": s.signed_at.isoformat() if s.signed_at else None,
        "countersigned_at": s.countersigned_at.isoformat() if s.countersigned_at else None,
    }


def _get_offering(offering_id: int, db: Session) -> TokenOffering:
    o = db.query(TokenOffering).filter(TokenOffering.id == offering_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Offering not found")
    return o


@router.get("/agreement/{offering_id}")
def preview_agreement(
    offering_id: int,
    wallet: str,
    name: str = "",
    tokens: float = 0,
    db: Session = Depends(get_db),
):
    o = _get_offering(offering_id, db)
    if not o.is_live:
        raise HTTPException(status_code=404, detail="Offering not found")
    doc = generate_subscription_agreement(
        o, (name or "[INVESTOR NAME]")[:200], normalize_wallet(wallet), max(tokens, 0)
    )
    return {
        "offering_id": offering_id,
        "text": doc["text"],
        "sha256": doc["sha256"],
        "usd_amount": doc["usd_amount"],
    }


@router.post("/sign")
def sign(
    body: SignBody,
    token_wallet: str = Depends(require_investor),
    db: Session = Depends(get_db),
):
    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent to electronic signature is required")

    # The signer must be signed in with the wallet the agreement is for —
    # otherwise anyone could "sign" on behalf of an approved investor.
    wallet = normalize_wallet(body.wallet_address)
    assert_wallet(token_wallet, wallet)

    o = _get_offering(body.offering_id, db)
    if not o.is_live:
        raise HTTPException(status_code=404, detail="Offering not found")
    if o.sale_tokens and body.token_amount > o.sale_tokens:
        raise HTTPException(status_code=400, detail="Token amount exceeds the offering size")

    inv = db.query(Investor).filter(Investor.wallet_address == wallet).first()
    if not inv or inv.kyc_status != "approved" or not inv.accredited:
        raise HTTPException(
            status_code=403,
            detail="Wallet is not verified and accredited by the transfer agent",
        )

    # Regenerate and require the hash to match what the investor reviewed —
    # guarantees the stored signature refers to exactly that text.
    doc = generate_subscription_agreement(o, body.investor_name, wallet, body.token_amount)
    if doc["sha256"] != body.agreement_sha256:
        raise HTTPException(
            status_code=409,
            detail="Agreement text changed since review — reload and sign again",
        )

    existing = (
        db.query(Subscription)
        .filter(
            Subscription.offering_id == body.offering_id,
            Subscription.wallet_address == wallet,
            Subscription.status.in_(["signed", "countersigned"]),
        )
        .first()
    )
    if existing:
        return _fmt(existing)

    sub = Subscription(
        offering_id=body.offering_id,
        wallet_address=wallet,
        investor_name=body.investor_name,
        investor_email=body.investor_email,
        token_amount=body.token_amount,
        usd_amount=doc["usd_amount"],
        agreement_sha256=doc["sha256"],
        signature_name=body.signature_name,
        consent=True,
        status="signed",
        signed_at=datetime.utcnow(),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return _fmt(sub)


@router.get("/status/{offering_id}/{wallet_address}")
def status(offering_id: int, wallet_address: str, db: Session = Depends(get_db)):
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.offering_id == offering_id,
            Subscription.wallet_address == normalize_wallet(wallet_address),
            Subscription.status.in_(["signed", "countersigned"]),
        )
        .first()
    )
    # Public gate flag only — the signer's name and amounts stay private.
    return {"signed": sub is not None, "status": sub.status if sub else None}


@router.get("/", dependencies=[Depends(require_operator)])
def list_subscriptions(offering_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Subscription)
    if offering_id:
        q = q.filter(Subscription.offering_id == offering_id)
    return {"subscriptions": [_fmt(s) for s in q.order_by(Subscription.signed_at.desc()).all()]}


@router.post("/{subscription_id}/countersign", dependencies=[Depends(require_operator)])
def countersign(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.status = "countersigned"
    sub.countersigned_at = datetime.utcnow()
    db.commit()
    return _fmt(sub)
