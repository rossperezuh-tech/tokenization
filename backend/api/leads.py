import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.database import Lead, Pipeline, PipelineStage, get_db
from services.scoring import heat_label

router = APIRouter()


def _fmt(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "source": lead.source,
        "address": lead.address,
        "city": lead.city,
        "state": lead.state,
        "zip_code": lead.zip_code,
        "property_type": lead.property_type,
        "asking_price": lead.asking_price,
        "sqft": lead.sqft,
        "cap_rate": lead.cap_rate,
        "noi": lead.noi,
        "days_on_market": lead.days_on_market,
        "had_price_reduction": lead.had_price_reduction,
        "seller_name": lead.seller_name,
        "seller_email": lead.seller_email,
        "seller_phone": lead.seller_phone,
        "broker_name": lead.broker_name,
        "broker_email": lead.broker_email,
        "broker_phone": lead.broker_phone,
        "reason_for_selling": lead.reason_for_selling,
        "score": lead.score,
        "heat": heat_label(lead.score),
        "score_breakdown": json.loads(lead.score_breakdown) if lead.score_breakdown else {},
        "in_pipeline": lead.in_pipeline,
        "pipeline_stage": lead.pipeline_stage,
        "latitude": lead.latitude,
        "longitude": lead.longitude,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "last_scraped_at": lead.last_scraped_at.isoformat() if lead.last_scraped_at else None,
    }


@router.get("/")
def list_leads(
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    in_pipeline: Optional[bool] = None,
    limit: int = Query(default=200, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Lead)
    if source:
        q = q.filter(Lead.source.ilike(f"%{source}%"))
    if min_score is not None:
        q = q.filter(Lead.score >= min_score)
    if in_pipeline is not None:
        q = q.filter(Lead.in_pipeline == in_pipeline)
    total = q.count()
    leads = q.order_by(Lead.score.desc()).offset(offset).limit(limit).all()
    return {"total": total, "leads": [_fmt(l) for l in leads]}


@router.get("/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _fmt(lead)


@router.post("/{lead_id}/to-pipeline")
def move_to_pipeline(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.pipeline_record:
        p = Pipeline(
            lead_id=lead.id,
            stage=PipelineStage.NEW_LEAD.value,
            deal_value=lead.asking_price,
        )
        db.add(p)
        lead.in_pipeline = True
        lead.pipeline_stage = PipelineStage.NEW_LEAD.value
        db.commit()
    return {"ok": True, "stage": lead.pipeline_stage}
