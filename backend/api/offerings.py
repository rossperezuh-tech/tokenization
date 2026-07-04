"""
Offerings API — the bridge between the Vesta internal pipeline and the
investor app.

A pipeline deal that reaches the "Token Offering" stage can be published as a
TokenOffering with its deployed contract addresses. The investor app reads
live offerings from here; on-chain balances/sales are read directly from the
contracts by the app (this API is the catalogue + economics, not the ledger).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import Lead, Pipeline, PipelineStage, TokenOffering, get_db
from services.auth import require_operator

router = APIRouter()


class OfferingCreate(BaseModel):
    lead_id: int
    name: Optional[str] = None
    symbol: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    chain: str = "base"
    token_address: Optional[str] = None
    sale_address: Optional[str] = None
    distribution_vault_address: Optional[str] = None
    secondary_market_address: Optional[str] = None
    usdc_address: Optional[str] = None
    total_tokens: Optional[float] = None
    sale_tokens: Optional[float] = None
    token_price_usdc: Optional[float] = None
    target_raise_usd: Optional[float] = None
    projected_yield: Optional[float] = None
    is_live: bool = True


class OfferingUpdate(BaseModel):
    summary: Optional[str] = None
    image_url: Optional[str] = None
    token_address: Optional[str] = None
    sale_address: Optional[str] = None
    distribution_vault_address: Optional[str] = None
    secondary_market_address: Optional[str] = None
    usdc_address: Optional[str] = None
    token_price_usdc: Optional[float] = None
    projected_yield: Optional[float] = None
    status: Optional[str] = None
    is_live: Optional[bool] = None


def _fmt(o: TokenOffering) -> dict:
    lead = o.lead
    return {
        "id": o.id,
        "lead_id": o.lead_id,
        "name": o.name or (lead.address if lead else None),
        "symbol": o.symbol,
        "summary": o.summary,
        "image_url": o.image_url,
        "chain": o.chain,
        "contracts": {
            "token": o.token_address,
            "sale": o.sale_address,
            "distribution_vault": o.distribution_vault_address,
            "secondary_market": o.secondary_market_address,
            "usdc": o.usdc_address,
        },
        "total_tokens": o.total_tokens,
        "sale_tokens": o.sale_tokens,
        "token_price_usdc": o.token_price_usdc,
        "target_raise_usd": o.target_raise_usd,
        "projected_yield": o.projected_yield,
        "status": o.status,
        "is_live": o.is_live,
        # property facts pulled from the lead
        "property": {
            "address": lead.address if lead else None,
            "city": lead.city if lead else None,
            "state": lead.state if lead else None,
            "property_type": lead.property_type if lead else None,
            "asking_price": lead.asking_price if lead else None,
            "cap_rate": lead.cap_rate if lead else None,
            "sqft": lead.sqft if lead else None,
            "latitude": lead.latitude if lead else None,
            "longitude": lead.longitude if lead else None,
            "score": lead.score if lead else None,
        },
    }


@router.get("/")
def list_offerings(live_only: bool = True, db: Session = Depends(get_db)):
    """Public catalogue consumed by the investor app."""
    q = db.query(TokenOffering)
    if live_only:
        q = q.filter(TokenOffering.is_live == True)
    return {"offerings": [_fmt(o) for o in q.order_by(TokenOffering.created_at.desc()).all()]}


@router.get("/candidates", dependencies=[Depends(require_operator)])
def offering_candidates(db: Session = Depends(get_db)):
    """Pipeline deals at the Token Offering stage that aren't published yet."""
    rows = (
        db.query(Pipeline).join(Lead)
        .filter(Pipeline.stage == PipelineStage.TOKEN_OFFERING.value)
        .all()
    )
    out = []
    for p in rows:
        existing = db.query(TokenOffering).filter(TokenOffering.lead_id == p.lead_id).first()
        if existing:
            continue
        out.append({
            "lead_id": p.lead_id,
            "address": p.lead.address if p.lead else None,
            "property_type": p.lead.property_type if p.lead else None,
            "deal_value": p.deal_value,
            "score": p.lead.score if p.lead else None,
        })
    return {"candidates": out}


@router.get("/{offering_id}")
def get_offering(offering_id: int, db: Session = Depends(get_db)):
    o = db.query(TokenOffering).filter(TokenOffering.id == offering_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Offering not found")
    return _fmt(o)


@router.post("/", dependencies=[Depends(require_operator)])
def create_offering(body: OfferingCreate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if db.query(TokenOffering).filter(TokenOffering.lead_id == body.lead_id).first():
        raise HTTPException(status_code=400, detail="Offering already exists for this lead")

    target = body.target_raise_usd
    if target is None and body.sale_tokens and body.token_price_usdc:
        target = body.sale_tokens * body.token_price_usdc

    o = TokenOffering(
        lead_id=body.lead_id,
        name=body.name or lead.address,
        symbol=body.symbol,
        summary=body.summary,
        image_url=body.image_url,
        chain=body.chain,
        token_address=body.token_address,
        sale_address=body.sale_address,
        distribution_vault_address=body.distribution_vault_address,
        secondary_market_address=body.secondary_market_address,
        usdc_address=body.usdc_address,
        total_tokens=body.total_tokens,
        sale_tokens=body.sale_tokens,
        token_price_usdc=body.token_price_usdc,
        target_raise_usd=target,
        projected_yield=body.projected_yield or lead.cap_rate,
        is_live=body.is_live,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _fmt(o)


class DeployConfig(BaseModel):
    lead_id: int
    symbol: str
    total_tokens: int = 100_000
    sale_tokens: int = 70_000
    token_price_usd: float = 25.0
    network: str = "baseSepolia"      # testnet by default — NOT live
    agent_address: Optional[str] = None


@router.post("/deploy-config", dependencies=[Depends(require_operator)])
def deploy_config(body: DeployConfig, db: Session = Depends(get_db)):
    """Generate the exact contract-deploy parameters + command for an offering.

    The operator runs the printed command on a machine with the deploy wallet;
    on testnet this is a safe dry run. (Real-money mainnet deploys wait until the
    LLC / legal structure is in place.)"""
    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    price_usdc_6dp = int(round(body.token_price_usd * 1_000_000))
    target_raise = body.sale_tokens * body.token_price_usd
    full_address = ", ".join(
        filter(None, [lead.address, lead.city, lead.state, lead.zip_code])
    )

    env = {
        "PROP_NAME": lead.address or body.symbol,
        "PROP_SYMBOL": body.symbol,
        "PROP_TOTAL_TOKENS": str(body.total_tokens),
        "PROP_SALE_TOKENS": str(body.sale_tokens),
        "PROP_ADDRESS": full_address,
        "PROP_TYPE": lead.property_type or "Commercial",
        "PROP_VALUATION_USD": str(int(lead.asking_price or target_raise)),
        "PROP_PRICE_USDC": str(price_usdc_6dp),
    }
    if body.agent_address:
        env["AGENT_ADDRESS"] = body.agent_address

    env_block = "\n".join(f"{k}={v}" for k, v in env.items())
    command = f"cd contracts && npm run deploy:{body.network}"

    return {
        "lead_id": body.lead_id,
        "network": body.network,
        "is_testnet": body.network != "base",
        "computed": {
            "token_price_usd": body.token_price_usd,
            "token_price_usdc_6dp": price_usdc_6dp,
            "target_raise_usd": target_raise,
        },
        "env": env,
        "env_block": env_block,
        "command": command,
        "next_step": "Run the command, then POST the printed addresses to /api/offerings to publish.",
    }


@router.patch("/{offering_id}", dependencies=[Depends(require_operator)])
def update_offering(offering_id: int, body: OfferingUpdate, db: Session = Depends(get_db)):
    o = db.query(TokenOffering).filter(TokenOffering.id == offering_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Offering not found")
    for field, value in body.dict(exclude_unset=True).items():
        setattr(o, field, value)
    db.commit()
    db.refresh(o)
    return _fmt(o)
