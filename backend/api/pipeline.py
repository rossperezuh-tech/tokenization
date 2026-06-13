import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import Lead, Pipeline, PipelineStage, get_db
from services.scoring import heat_label

router = APIRouter()

STAGES = [s.value for s in PipelineStage]


class StageUpdate(BaseModel):
    stage: str
    notes: Optional[str] = None
    deal_value: Optional[float] = None


def _fmt_pipeline(p: Pipeline) -> dict:
    lead = p.lead
    return {
        "pipeline_id": p.id,
        "lead_id": p.lead_id,
        "stage": p.stage,
        "deal_value": p.deal_value,
        "notes": p.notes,
        "stage_entered_at": p.stage_entered_at.isoformat() if p.stage_entered_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        # denormalized lead data for kanban cards
        "address": lead.address if lead else None,
        "city": lead.city if lead else None,
        "state": lead.state if lead else None,
        "property_type": lead.property_type if lead else None,
        "asking_price": lead.asking_price if lead else None,
        "score": lead.score if lead else None,
        "heat": heat_label(lead.score) if lead else None,
        "source": lead.source if lead else None,
        "seller_name": lead.seller_name if lead else None,
        "broker_name": lead.broker_name if lead else None,
        "days_on_market": lead.days_on_market if lead else None,
    }


@router.get("/")
def list_pipeline(db: Session = Depends(get_db)):
    items = db.query(Pipeline).join(Lead).order_by(Lead.score.desc()).all()
    by_stage: dict[str, list] = {s: [] for s in STAGES}
    total_value = 0.0
    for item in items:
        if item.stage in by_stage:
            by_stage[item.stage].append(_fmt_pipeline(item))
        if item.deal_value:
            total_value += item.deal_value
    return {
        "stages": STAGES,
        "by_stage": by_stage,
        "total_pipeline_value": total_value,
        "total_deals": len(items),
    }


@router.patch("/{pipeline_id}/stage")
def update_stage(pipeline_id: int, body: StageUpdate, db: Session = Depends(get_db)):
    if body.stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline record not found")
    p.stage = body.stage
    p.stage_entered_at = datetime.utcnow()
    if body.notes is not None:
        p.notes = body.notes
    if body.deal_value is not None:
        p.deal_value = body.deal_value
    if p.lead:
        p.lead.pipeline_stage = body.stage
    db.commit()
    return _fmt_pipeline(p)
